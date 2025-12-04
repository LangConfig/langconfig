# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
HTTP Bridge for Executor API Communication

This module provides asynchronous HTTP client utilities for communicating
with Executor API services, replacing the Celery task dispatch mechanism.

Supports multiple deployment environments:
- Kubernetes (internal DNS)
- Docker Compose (service names)
- Local development (direct URLs)
"""

import httpx
import asyncio
import os
import logging
from typing import Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ExecutorEnvironment(str, Enum):
    """Deployment environment types for executor discovery"""
    KUBERNETES = "kubernetes"
    DOCKER = "docker"
    LOCAL = "local"


# ============================================================================
# Configuration
# ============================================================================

# Retrieve the shared secret token from environment variables
EXECUTOR_API_SECRET = os.getenv("EXECUTOR_API_SECRET")
if not EXECUTOR_API_SECRET:
    logger.warning(
        "EXECUTOR_API_SECRET not set in Core API. "
        "Executor communication will fail. "
        "Set this environment variable for production use."
    )
    # Don't fail immediately - allow startup for development
    EXECUTOR_API_SECRET = "dev-secret-not-for-production"

# Deployment environment (kubernetes, docker, local)
EXECUTOR_ENVIRONMENT = os.getenv("EXECUTOR_ENVIRONMENT", "docker").lower()

# Base URL for local/development executors
EXECUTOR_BASE_URL = os.getenv("EXECUTOR_BASE_URL", "http://localhost:8080")

# Kubernetes namespace template
K8S_NAMESPACE_TEMPLATE = os.getenv("K8S_NAMESPACE_TEMPLATE", "langconfig-project-{project_id}")

# Kubernetes service name
K8S_SERVICE_NAME = os.getenv("K8S_SERVICE_NAME", "executor-api-svc")

# Docker Compose service name pattern
DOCKER_SERVICE_NAME = os.getenv("DOCKER_SERVICE_NAME", "executor-{project_id}")


# Configure retries for transient network issues
MAX_RETRIES = 3
RETRY_STATUS_CODES = [502, 503, 504]  # Bad Gateway, Service Unavailable, Gateway Timeout

# Configure timeouts (crucial for stability)
TIMEOUT_EXECUTION = httpx.Timeout(
    connect=10.0,  # 10 seconds to establish connection
    read=1800.0,   # 30 minutes for task execution
    write=10.0,    # 10 seconds for request writing
    pool=10.0      # 10 seconds for connection pool
)

TIMEOUT_VALIDATION = httpx.Timeout(
    connect=10.0,  # 10 seconds to establish connection
    read=600.0,    # 10 minutes for validation
    write=10.0,    # 10 seconds for request writing
    pool=10.0      # 10 seconds for connection pool
)

TIMEOUT_INDEX = httpx.Timeout(
    connect=10.0,  # 10 seconds to establish connection
    read=300.0,    # 5 minutes for indexing
    write=10.0,    # 10 seconds for request writing
    pool=10.0      # 10 seconds for connection pool
)


# ============================================================================
# Executor URL Resolution
# ============================================================================

def get_executor_url_kubernetes(project_id: int) -> str:
    """
    Determines the URL for Kubernetes-based executor.
    
    Uses Kubernetes internal DNS convention:
    <service-name>.<namespace>.svc.cluster.local
    
    Args:
        project_id: Project identifier
        
    Returns:
        Executor API base URL
    """
    namespace = K8S_NAMESPACE_TEMPLATE.format(project_id=project_id)
    service_name = K8S_SERVICE_NAME
    
    # Kubernetes internal DNS
    url = f"http://{service_name}.{namespace}.svc.cluster.local:8080/api/v1"
    
    logger.debug(f"Kubernetes executor URL for project {project_id}: {url}")
    return url


def get_executor_url_docker(project_id: int) -> str:
    """
    Determines the URL for Docker Compose-based executor.
    
    Uses Docker Compose service name resolution.
    
    Args:
        project_id: Project identifier
        
    Returns:
        Executor API base URL
    """
    service_name = DOCKER_SERVICE_NAME.format(project_id=project_id)
    
    # Docker Compose internal network
    url = f"http://{service_name}:8080/api/v1"
    
    logger.debug(f"Docker executor URL for project {project_id}: {url}")
    return url


def get_executor_url_local(project_id: int) -> str:
    """
    Determines the URL for local development executor.
    
    Uses configured base URL (typically localhost).
    
    Args:
        project_id: Project identifier
        
    Returns:
        Executor API base URL
    """
    # For local development, might use different ports per project
    # or a single executor with project routing
    url = f"{EXECUTOR_BASE_URL}/api/v1"
    
    logger.debug(f"Local executor URL for project {project_id}: {url}")
    return url


def get_executor_url(project_id: int, environment: Optional[str] = None) -> str:
    """
    Determines the URL for the target executor based on deployment environment.
    
    Args:
        project_id: Project identifier
        environment: Override environment (kubernetes, docker, local)
        
    Returns:
        Executor API base URL
        
    Raises:
        ValueError: If environment is invalid
    """
    env = environment or EXECUTOR_ENVIRONMENT
    
    if env == ExecutorEnvironment.KUBERNETES:
        return get_executor_url_kubernetes(project_id)
    elif env == ExecutorEnvironment.DOCKER:
        return get_executor_url_docker(project_id)
    elif env == ExecutorEnvironment.LOCAL:
        return get_executor_url_local(project_id)
    else:
        raise ValueError(f"Invalid executor environment: {env}")


# ============================================================================
# Retry Logic
# ============================================================================

class ExecutorError(Exception):
    """Base exception for executor-related errors"""
    def __init__(self, message: str, status_code: Optional[int] = None, detail: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class ExecutorConnectionError(ExecutorError):
    """Raised when connection to executor fails"""
    pass


class ExecutorTimeoutError(ExecutorError):
    """Raised when executor request times out"""
    pass


class ExecutorValidationError(ExecutorError):
    """Raised when executor returns validation error (4xx)"""
    pass


class ExecutorServerError(ExecutorError):
    """Raised when executor returns server error (5xx)"""
    pass


async def _retry_with_backoff(
    func,
    max_retries: int = MAX_RETRIES,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    retry_on_status: list[int] = None
):
    """
    Retry a function with exponential backoff.
    
    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        backoff_factor: Multiplier for delay between retries
        retry_on_status: List of HTTP status codes to retry on
        
    Returns:
        Result from function call
        
    Raises:
        Last exception if all retries fail
    """
    retry_on_status = retry_on_status or RETRY_STATUS_CODES
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return await func()
        except httpx.HTTPStatusError as e:
            last_exception = e
            
            # Check if we should retry this status code
            if e.response.status_code not in retry_on_status:
                raise
            
            if attempt < max_retries:
                delay = initial_delay * (backoff_factor ** attempt)
                logger.warning(
                    f"Retry {attempt + 1}/{max_retries} after {delay}s "
                    f"(status {e.response.status_code})"
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"All {max_retries} retries exhausted")
                raise
                
        except (httpx.RequestError, httpx.TimeoutException) as e:
            last_exception = e
            
            if attempt < max_retries:
                delay = initial_delay * (backoff_factor ** attempt)
                logger.warning(
                    f"Retry {attempt + 1}/{max_retries} after {delay}s "
                    f"(error: {type(e).__name__})"
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"All {max_retries} retries exhausted")
                raise
    
    raise last_exception


# ============================================================================
# HTTP Client Functions
# ============================================================================

async def call_executor_api(
    project_id: int,
    endpoint: str,
    payload: Dict[str, Any],
    timeout_config: httpx.Timeout,
    environment: Optional[str] = None,
    enable_retries: bool = True
) -> Dict[str, Any]:
    """
    Makes an asynchronous HTTP POST request to the Executor API.
    
    Args:
        project_id: Project identifier for URL resolution
        endpoint: API endpoint path (e.g., '/execute', '/validate')
        payload: Request body as dictionary
        timeout_config: HTTP timeout configuration
        environment: Optional environment override
        enable_retries: Whether to enable automatic retries
        
    Returns:
        Response JSON as dictionary
        
    Raises:
        ExecutorConnectionError: If connection to executor fails
        ExecutorTimeoutError: If request times out
        ExecutorValidationError: If executor returns 4xx error
        ExecutorServerError: If executor returns 5xx error
    """
    base_url = get_executor_url(project_id, environment)
    url = f"{base_url}{endpoint}"
    
    headers = {
        "X-Executor-Token": EXECUTOR_API_SECRET,
        "Content-Type": "application/json"
    }
    
    logger.info(f"[HTTP Bridge] Calling Executor API: POST {url}")
    logger.debug(f"[HTTP Bridge] Payload: {payload}")
    
    # Configure transport with connection pooling
    transport = httpx.AsyncHTTPTransport(
        retries=MAX_RETRIES if enable_retries else 0
    )
    
    async def _make_request():
        async with httpx.AsyncClient(
            timeout=timeout_config,
            transport=transport
        ) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()  # Raise exception for 4xx/5xx errors
                
                result = response.json()
                logger.info(f"[HTTP Bridge] Success: {response.status_code}")
                logger.debug(f"[HTTP Bridge] Response: {result}")
                
                return result
                
            except httpx.HTTPStatusError as e:
                # Extract detailed error information from response
                try:
                    error_response = e.response.json()
                    error_detail = error_response.get("detail", e.response.text)
                    
                    # Include additional error context if available
                    error_context = {
                        "status_code": e.response.status_code,
                        "detail": error_detail,
                        "url": str(e.request.url),
                        "method": e.request.method
                    }
                    
                    # Add executor-specific error info if present
                    if isinstance(error_response, dict):
                        if "error_type" in error_response:
                            error_context["error_type"] = error_response["error_type"]
                        if "traceback" in error_response:
                            error_context["traceback"] = error_response["traceback"]
                    
                except Exception:
                    error_detail = e.response.text
                    error_context = {
                        "status_code": e.response.status_code,
                        "detail": error_detail,
                        "url": str(e.request.url)
                    }
                
                logger.error(
                    f"[HTTP Bridge] CRITICAL: Executor API returned error: "
                    f"{e.response.status_code} - {error_detail}"
                )
                
                # Categorize error by status code
                if 400 <= e.response.status_code < 500:
                    raise ExecutorValidationError(
                        f"Executor validation error: {error_detail}",
                        status_code=e.response.status_code,
                        detail=str(error_context)
                    )
                else:
                    raise ExecutorServerError(
                        f"Executor server error: {error_detail}",
                        status_code=e.response.status_code,
                        detail=str(error_context)
                    )
                
            except httpx.TimeoutException as e:
                logger.error(
                    f"[HTTP Bridge] CRITICAL: Request timeout after {timeout_config.read}s: {e}"
                )
                raise ExecutorTimeoutError(
                    f"Executor timeout after {timeout_config.read}s. "
                    f"Task may still be running. Check executor logs.",
                    detail=str(e)
                )
                
            except httpx.RequestError as e:
                logger.error(
                    f"[HTTP Bridge] CRITICAL: Failed to connect to Executor API at {url}: {e}"
                )
                raise ExecutorConnectionError(
                    f"Executor connection error: {type(e).__name__}. "
                    f"Check K8s Service, Network Policies, and executor availability.",
                    detail=str(e)
                )
    
    # Execute with retry logic if enabled
    if enable_retries:
        return await _retry_with_backoff(_make_request)
    else:
        return await _make_request()


# ============================================================================
# High-Level API Functions
# ============================================================================

async def execute_development_task(
    project_id: int,
    task_id: int,
    directive: str,
    context_package: Optional[str] = None,
    classification: str = "CODE_ASSISTANT",
    feature_branch_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute a development task on the Executor API.
    
    Args:
        project_id: Project identifier
        task_id: Task identifier
        directive: Task directive/description
        context_package: Optional context data
        classification: Task classification
        feature_branch_name: Optional branch name
        
    Returns:
        Execution result dictionary
    """
    payload = {
        "task_id": task_id,
        "project_id": project_id,
        "directive": directive,
        "context_package": context_package,
        "classification": classification,
        "feature_branch_name": feature_branch_name
    }
    
    logger.info(
        f"[HTTP Bridge] Executing development task {task_id} "
        f"for project {project_id}"
    )
    
    return await call_executor_api(
        project_id=project_id,
        endpoint="/execute",
        payload=payload,
        timeout_config=TIMEOUT_EXECUTION
    )


async def validate_code_changes(
    project_id: int,
    task_id: int,
    feature_branch_name: str,
    project_dna: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validate code changes using Guardian Agent.
    
    Args:
        project_id: Project identifier
        task_id: Task identifier
        feature_branch_name: Branch to validate
        project_dna: Optional Project DNA for validation
        
    Returns:
        Validation result dictionary
    """
    payload = {
        "project_id": project_id,
        "task_id": task_id,
        "feature_branch_name": feature_branch_name,
        "project_dna": project_dna
    }
    
    logger.info(
        f"[HTTP Bridge] Validating code for task {task_id} "
        f"on branch {feature_branch_name}"
    )
    
    return await call_executor_api(
        project_id=project_id,
        endpoint="/validate",
        payload=payload,
        timeout_config=TIMEOUT_VALIDATION
    )


async def index_codebase(
    project_id: int
) -> Dict[str, Any]:
    """
    Index codebase for RAG pipeline.
    
    Args:
        project_id: Project identifier
        
    Returns:
        Indexing result dictionary with nodes and DNA
    """
    payload = {
        "project_id": project_id
    }
    
    logger.info(f"[HTTP Bridge] Indexing codebase for project {project_id}")
    
    return await call_executor_api(
        project_id=project_id,
        endpoint="/index",
        payload=payload,
        timeout_config=TIMEOUT_INDEX
    )


# ============================================================================
# Health Check
# ============================================================================

async def check_executor_health(
    project_id: int,
    environment: Optional[str] = None
) -> bool:
    """
    Check if executor is healthy and responding.
    
    Args:
        project_id: Project identifier
        environment: Optional environment override
        
    Returns:
        True if healthy, False otherwise
    """
    base_url = get_executor_url(project_id, environment)
    # Health endpoint is at root, not /api/v1
    url = base_url.replace("/api/v1", "/health")
    
    logger.debug(f"[HTTP Bridge] Checking executor health: {url}")
    
    timeout = httpx.Timeout(connect=5.0, read=5.0)
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            result = response.json()
            is_healthy = result.get("status") == "healthy"
            
            logger.debug(f"[HTTP Bridge] Executor health: {is_healthy}")
            return is_healthy
            
    except Exception as e:
        logger.warning(f"[HTTP Bridge] Health check failed: {e}")
        return False


# ============================================================================
# Batch Operations
# ============================================================================

async def execute_tasks_parallel(
    tasks: list[Dict[str, Any]],
    max_concurrent: int = 5
) -> list[Dict[str, Any]]:
    """
    Execute multiple tasks in parallel with concurrency limit.
    
    Args:
        tasks: List of task dictionaries with execution parameters
        max_concurrent: Maximum concurrent executions
        
    Returns:
        List of execution results
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def execute_with_semaphore(task: Dict[str, Any]) -> Dict[str, Any]:
        async with semaphore:
            return await execute_development_task(**task)
    
    logger.info(f"[HTTP Bridge] Executing {len(tasks)} tasks in parallel (max {max_concurrent})")
    
    results = await asyncio.gather(
        *[execute_with_semaphore(task) for task in tasks],
        return_exceptions=True
    )
    
    return results
