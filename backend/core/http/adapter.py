# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
HTTP Bridge Adapter for LangGraph Orchestration

This module provides an adapter layer that makes the HTTP bridge compatible
with the existing LangGraph orchestration structure, allowing seamless
replacement of the Celery bridge.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from .graph_state import WorkflowState
from .http_bridge import (
    execute_development_task,
    validate_code_changes,
    index_codebase,
    check_executor_health
)
from services.executor_manager import get_executor_manager, ExecutorInstance

logger = logging.getLogger(__name__)


class HttpBridgeError(Exception):
    """Base exception for HTTP bridge errors"""
    pass


class HttpBridgeTimeoutError(HttpBridgeError):
    """Raised when an HTTP request times out"""
    pass


class HttpBridgeFailureError(HttpBridgeError):
    """Raised when an HTTP request fails"""
    pass


class HttpBridgeAdapter:
    """
    Adapter for integrating HTTP bridge with LangGraph orchestration.
    
    Provides methods that match the Celery bridge interface but use
    HTTP communication with Executor API instead.
    """
    
    def __init__(self):
        """Initialize the HTTP bridge adapter"""
        self.executor_manager = get_executor_manager()
        logger.info("HTTP Bridge Adapter initialized")
    
    async def execute_code_execution_task_with_context(
        self,
        state: WorkflowState,
        context_package: str,
        timeout: float = 600.0
    ) -> Dict[str, Any]:
        """
        Execute code generation task via HTTP bridge.
        
        Args:
            state: Current workflow state
            context_package: Assembled context package
            timeout: Execution timeout in seconds
            
        Returns:
            Dict containing execution results
            
        Raises:
            HttpBridgeFailureError: If execution fails
            HttpBridgeTimeoutError: If execution times out
        """
        project_id = state["project_id"]
        task_id = state["task_id"]
        directive = state["current_directive"]
        feature_branch_name = state.get("feature_branch_name")
        classification = state.get("classification", "CODE_ASSISTANT")
        
        logger.info(
            f"Executing code task {task_id} for project {project_id} "
            f"via HTTP bridge"
        )
        
        # Register executor if not already registered
        executor = self.executor_manager.get_executor(project_id)
        if not executor:
            logger.info(f"Registering executor for project {project_id}")
            executor = self.executor_manager.register_executor(project_id)
        
        # Check executor availability
        if not executor.is_available():
            # Try to wait for executor to become available
            health_ok = await self.executor_manager.check_health(project_id)
            if not health_ok:
                raise HttpBridgeFailureError(
                    f"Executor for project {project_id} is not healthy"
                )
        
        # Mark task as started on executor
        executor.mark_task_started(task_id)
        
        start_time = datetime.now()
        
        try:
            # Call executor API
            result = await execute_development_task(
                project_id=project_id,
                task_id=task_id,
                directive=directive,
                context_package=context_package,
                classification=classification,
                feature_branch_name=feature_branch_name
            )
            
            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Mark task as completed successfully
            executor.mark_task_completed(
                task_id=task_id,
                success=True,
                execution_time=execution_time
            )
            
            logger.info(
                f"Code execution completed for task {task_id} "
                f"in {execution_time:.2f}s"
            )
            
            # Return result in format compatible with Celery bridge
            return {
                "status": "SUCCESS",
                "task_id": str(task_id),
                "result": result,
                "execution_time": execution_time
            }
            
        except Exception as e:
            # Calculate execution time even on failure
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Mark task as completed with failure
            executor.mark_task_completed(
                task_id=task_id,
                success=False,
                execution_time=execution_time
            )
            
            logger.error(f"Code execution failed for task {task_id}: {e}")
            
            # Convert exceptions to bridge-specific errors
            if "timeout" in str(e).lower():
                raise HttpBridgeTimeoutError(
                    f"Task {task_id} execution timed out: {e}"
                )
            else:
                raise HttpBridgeFailureError(
                    f"Task {task_id} execution failed: {e}"
                )
    
    async def execute_validation_task(
        self,
        state: WorkflowState,
        timeout: float = 300.0
    ) -> Dict[str, Any]:
        """
        Execute validation task via HTTP bridge.
        
        Args:
            state: Current workflow state
            timeout: Validation timeout in seconds
            
        Returns:
            Dict containing validation results
            
        Raises:
            HttpBridgeFailureError: If validation fails
            HttpBridgeTimeoutError: If validation times out
        """
        project_id = state["project_id"]
        task_id = state["task_id"]
        feature_branch_name = state.get("feature_branch_name")
        project_dna = state.get("project_dna")
        
        logger.info(
            f"Validating code for task {task_id} on branch {feature_branch_name} "
            f"via HTTP bridge"
        )
        
        # Get executor
        executor = self.executor_manager.get_executor(project_id)
        if not executor:
            raise HttpBridgeFailureError(
                f"No executor registered for project {project_id}"
            )
        
        start_time = datetime.now()
        
        try:
            # Call executor API
            result = await validate_code_changes(
                project_id=project_id,
                task_id=task_id,
                feature_branch_name=feature_branch_name,
                project_dna=project_dna
            )
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(
                f"Validation completed for task {task_id} "
                f"in {execution_time:.2f}s"
            )
            
            # Return result in format compatible with Celery bridge
            return {
                "status": "SUCCESS",
                "task_id": str(task_id),
                "result": result,
                "execution_time": execution_time
            }
            
        except Exception as e:
            logger.error(f"Validation failed for task {task_id}: {e}")
            
            # Convert exceptions to bridge-specific errors
            if "timeout" in str(e).lower():
                raise HttpBridgeTimeoutError(
                    f"Task {task_id} validation timed out: {e}"
                )
            else:
                raise HttpBridgeFailureError(
                    f"Task {task_id} validation failed: {e}"
                )
    
    async def execute_indexing_task(
        self,
        project_id: int,
        timeout: float = 300.0
    ) -> Dict[str, Any]:
        """
        Execute codebase indexing task via HTTP bridge.
        
        Args:
            project_id: Project identifier
            timeout: Indexing timeout in seconds
            
        Returns:
            Dict containing indexing results
            
        Raises:
            HttpBridgeFailureError: If indexing fails
            HttpBridgeTimeoutError: If indexing times out
        """
        logger.info(f"Indexing codebase for project {project_id} via HTTP bridge")
        
        # Get or register executor
        executor = self.executor_manager.get_executor(project_id)
        if not executor:
            logger.info(f"Registering executor for project {project_id}")
            executor = self.executor_manager.register_executor(project_id)
        
        start_time = datetime.now()
        
        try:
            # Call executor API
            result = await index_codebase(project_id=project_id)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(
                f"Indexing completed for project {project_id} "
                f"in {execution_time:.2f}s"
            )
            
            # Return result in format compatible with Celery bridge
            return {
                "status": "SUCCESS",
                "result": result,
                "execution_time": execution_time
            }
            
        except Exception as e:
            logger.error(f"Indexing failed for project {project_id}: {e}")
            
            # Convert exceptions to bridge-specific errors
            if "timeout" in str(e).lower():
                raise HttpBridgeTimeoutError(
                    f"Project {project_id} indexing timed out: {e}"
                )
            else:
                raise HttpBridgeFailureError(
                    f"Project {project_id} indexing failed: {e}"
                )
    
    async def check_executor_health(self, project_id: int) -> bool:
        """
        Check if executor is healthy.
        
        Args:
            project_id: Project identifier
            
        Returns:
            True if healthy, False otherwise
        """
        try:
            return await check_executor_health(project_id)
        except Exception as e:
            logger.error(f"Health check failed for project {project_id}: {e}")
            return False
    
    def get_executor_stats(self, project_id: int) -> Optional[Dict[str, Any]]:
        """
        Get executor statistics.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Dict with executor stats or None
        """
        return self.executor_manager.get_executor_stats(project_id)
    
    def get_global_stats(self) -> Dict[str, Any]:
        """
        Get global executor statistics.
        
        Returns:
            Dict with global stats
        """
        return self.executor_manager.get_global_stats()


# ============================================================================
# Helper Functions (Compatible with existing Celery bridge interface)
# ============================================================================

async def execute_code_execution_task_with_context(
    bridge: HttpBridgeAdapter,
    state: WorkflowState,
    context_package: str,
    timeout: float = 600.0
) -> Dict[str, Any]:
    """
    Helper function to execute code task via HTTP bridge.
    
    Provides interface compatible with existing Celery bridge usage.
    """
    return await bridge.execute_code_execution_task_with_context(
        state=state,
        context_package=context_package,
        timeout=timeout
    )


async def execute_validation_task(
    bridge: HttpBridgeAdapter,
    state: WorkflowState,
    timeout: float = 300.0
) -> Dict[str, Any]:
    """
    Helper function to execute validation task via HTTP bridge.
    
    Provides interface compatible with existing Celery bridge usage.
    """
    return await bridge.execute_validation_task(
        state=state,
        timeout=timeout
    )


async def execute_indexing_task(
    bridge: HttpBridgeAdapter,
    project_id: int,
    timeout: float = 300.0
) -> Dict[str, Any]:
    """
    Helper function to execute indexing task via HTTP bridge.
    
    Provides interface compatible with existing Celery bridge usage.
    """
    return await bridge.execute_indexing_task(
        project_id=project_id,
        timeout=timeout
    )
