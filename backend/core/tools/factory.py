# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Tool Factory - Dynamic Custom Tool Creation
============================================

Creates LangChain tools dynamically from user configurations.
Supports multiple tool types: API, Notification, Image/Video, Database, Data Transform.

Pattern: Mirrors AgentFactory architecture for consistency.
"""

import logging
from typing import Dict, Any, List, Optional, Callable
from pydantic import BaseModel, Field, ValidationError, create_model
from urllib.parse import urlparse
import httpx
import json
import re
import os
import asyncio
import base64
from datetime import datetime

from langchain_core.tools import StructuredTool, BaseTool
from pydantic import BaseModel as PydanticBaseModel, create_model as create_pydantic_model, Field as PydanticField

from models.custom_tool import ToolType, ToolTemplateType
from config import settings

logger = logging.getLogger(__name__)

# Thread-safe artifact storage using a module-level dict
# ContextVar doesn't work across async boundaries in LangChain callbacks
import threading
_artifact_lock = threading.Lock()
_pending_artifacts: List[Dict[str, Any]] = []


def get_pending_artifacts() -> List[Dict[str, Any]]:
    """Get and clear any pending artifacts from the last tool execution."""
    global _pending_artifacts
    with _artifact_lock:
        artifacts = _pending_artifacts.copy()
        _pending_artifacts = []
        return artifacts


def store_artifact(artifact: Dict[str, Any]) -> None:
    """Store an artifact from a tool execution for later retrieval."""
    global _pending_artifacts
    with _artifact_lock:
        _pending_artifacts.append(artifact)
        logger.info(f"Artifact stored, pending count: {len(_pending_artifacts)}")


# =============================================================================
# Tool Type Constants
# =============================================================================

class ToolTypes:
    """Constants for tool types - replaces magic strings"""
    API = "api"
    NOTIFICATION = "notification"
    IMAGE_VIDEO = "image_video"
    DATABASE = "database"
    DATA_TRANSFORM = "data_transform"


# =============================================================================
# Validation Result Model
# =============================================================================

class ValidationResult(BaseModel):
    """Result of tool configuration validation"""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    langchain_compatible: bool = True


# =============================================================================
# LangChain Requirements
# =============================================================================

class LangChainRequirements:
    """Required fields for LangChain tool compatibility"""

    REQUIRED_FIELDS = {
        "tool_id": str,
        "name": str,
        "description": str,
        "input_schema": dict
    }

    RECOMMENDED_FIELDS = {
        "output_format": str,
        "error_handling": dict
    }

    @staticmethod
    def validate(tool_config: Dict[str, Any]) -> ValidationResult:
        """
        Validate tool configuration against LangChain requirements.

        Returns:
            ValidationResult with validation details
        """
        result = ValidationResult(is_valid=True, langchain_compatible=True)

        # Check required fields
        for field_name, field_type in LangChainRequirements.REQUIRED_FIELDS.items():
            if field_name not in tool_config:
                result.errors.append(f"Missing required field: {field_name}")
                result.is_valid = False
                result.langchain_compatible = False
            elif not isinstance(tool_config[field_name], field_type):
                result.errors.append(f"Field '{field_name}' must be of type {field_type.__name__}")
                result.is_valid = False

        # Check recommended fields
        for field_name, field_type in LangChainRequirements.RECOMMENDED_FIELDS.items():
            if field_name not in tool_config:
                result.warnings.append(f"Recommended field missing: {field_name}")

        # Validate tool_id format (alphanumeric + underscores)
        if "tool_id" in tool_config:
            if not re.match(r'^[a-zA-Z0-9_]+$', tool_config["tool_id"]):
                result.errors.append("tool_id must contain only letters, numbers, and underscores")
                result.is_valid = False

        # Validate description is not empty
        if "description" in tool_config:
            if not tool_config["description"].strip():
                result.errors.append("description cannot be empty (required for LLM understanding)")
                result.is_valid = False
                result.langchain_compatible = False

        # Validate input_schema structure
        if "input_schema" in tool_config:
            schema = tool_config["input_schema"]
            if not isinstance(schema, dict):
                result.errors.append("input_schema must be a dictionary (JSON Schema format)")
                result.is_valid = False
            elif "properties" not in schema:
                result.warnings.append("input_schema should have 'properties' field")

        return result


# =============================================================================
# Tool Factory Core
# =============================================================================

class ToolFactory:
    """
    Factory for creating custom LangChain tools dynamically.

    Follows AgentFactory pattern for consistency.
    """

    # Class-level cache for Pydantic schemas
    # Key: hash of (tool_id + input_schema), Value: Pydantic model class
    _schema_cache: Dict[str, type] = {}

    @staticmethod
    async def create_tool(
        tool_config: Dict[str, Any],
        project_id: Optional[int] = None
    ) -> BaseTool:
        """
        Create a LangChain tool from configuration.

        Args:
            tool_config: Tool configuration dictionary
            project_id: Optional project ID for scoping

        Returns:
            Configured LangChain BaseTool instance

        Raises:
            ValueError: If configuration is invalid
            NotImplementedError: If tool type is not supported
        """
        # Validate configuration
        validation_result = ToolFactory.validate_tool_config(tool_config)
        if not validation_result.is_valid:
            raise ValueError(f"Invalid tool configuration: {', '.join(validation_result.errors)}")

        # Validate implementation-specific configuration
        impl_config = tool_config.get("implementation_config", {})
        impl_errors = ToolFactory._validate_tool_implementation(tool_config, impl_config)
        if impl_errors:
            raise ValueError(f"Invalid implementation config: {', '.join(impl_errors)}")

        # Extract tool type
        tool_type = tool_config.get("tool_type", "api")
        template_type = tool_config.get("template_type", "custom")

        logger.info(f"Creating custom tool: {tool_config['name']} (type: {tool_type})")

        # Route to appropriate tool creator based on type
        if tool_type == ToolTypes.API:
            return await ToolFactory._create_api_tool(tool_config, project_id)
        elif tool_type == ToolTypes.NOTIFICATION:
            return await ToolFactory._create_notification_tool(tool_config, project_id)
        elif tool_type == ToolTypes.IMAGE_VIDEO:
            return await ToolFactory._create_image_video_tool(tool_config, project_id)
        elif tool_type == ToolTypes.DATABASE:
            return await ToolFactory._create_database_tool(tool_config, project_id)
        elif tool_type == ToolTypes.DATA_TRANSFORM:
            return await ToolFactory._create_data_transform_tool(tool_config, project_id)
        else:
            raise NotImplementedError(f"Tool type '{tool_type}' is not yet implemented")

    @staticmethod
    def validate_tool_config(tool_config: Dict[str, Any]) -> ValidationResult:
        """
        Validate tool configuration.

        Args:
            tool_config: Tool configuration to validate

        Returns:
            ValidationResult with details
        """
        # Use LangChain requirements validator
        return LangChainRequirements.validate(tool_config)

    @staticmethod
    def get_langchain_requirements() -> Dict[str, Any]:
        """
        Get LangChain compatibility requirements.

        Returns:
            Dictionary of required and recommended fields
        """
        return {
            "required_fields": LangChainRequirements.REQUIRED_FIELDS,
            "recommended_fields": LangChainRequirements.RECOMMENDED_FIELDS,
            "description": "Fields required for LangChain tool compatibility"
        }

    @staticmethod
    def _create_pydantic_args_schema(input_schema: Dict[str, Any], tool_name: str) -> type:
        """
        Create a Pydantic model from JSON Schema for tool arguments.

        Uses caching to avoid recreating the same schema multiple times.

        Args:
            input_schema: JSON Schema definition
            tool_name: Name of the tool (for model naming)

        Returns:
            Pydantic model class (cached if possible)
        """
        # Generate cache key from tool_name and input_schema
        import hashlib
        schema_str = json.dumps(input_schema, sort_keys=True)
        cache_key = f"{tool_name}:{hashlib.md5(schema_str.encode()).hexdigest()}"

        # Check cache first
        if cache_key in ToolFactory._schema_cache:
            logger.debug(f"Using cached Pydantic schema for {tool_name}")
            return ToolFactory._schema_cache[cache_key]

        # Extract properties from JSON Schema
        properties = input_schema.get("properties", {})
        required_fields = input_schema.get("required", [])

        # Build Pydantic field definitions
        field_definitions = {}
        for field_name, field_spec in properties.items():
            field_type = field_spec.get("type", "string")
            description = field_spec.get("description", "")

            # Map JSON Schema types to Python types
            python_type = {
                "string": str,
                "integer": int,
                "number": float,
                "boolean": bool,
                "array": list,
                "object": dict
            }.get(field_type, str)

            # Determine if field is optional
            is_required = field_name in required_fields

            if is_required:
                field_definitions[field_name] = (python_type, PydanticField(..., description=description))
            else:
                default_value = field_spec.get("default", None)
                field_definitions[field_name] = (python_type, PydanticField(default=default_value, description=description))

        # Create Pydantic model dynamically
        model_name = f"{tool_name.title().replace('_', '')}Args"
        try:
            # Create Pydantic model using create_model helper
            args_model = create_pydantic_model(model_name, **field_definitions)

            # Store in cache for future use
            ToolFactory._schema_cache[cache_key] = args_model
            logger.debug(f"Cached Pydantic schema for {tool_name} (cache size: {len(ToolFactory._schema_cache)})")

            return args_model
        except Exception as e:
            logger.warning(f"Failed to create Pydantic model for {tool_name}: {e}. Using generic args.")
            # Fallback: create a simple model (don't cache fallback schemas)
            fallback_model = create_pydantic_model(model_name, **{"input": (str, PydanticField(..., description="Tool input"))})
            return fallback_model

    @staticmethod
    def _build_auth_headers(auth_config: Dict[str, Any]) -> Dict[str, str]:
        """
        Build authorization headers from authentication configuration.

        Supports:
        - API Key (header or query string)
        - Bearer token
        - Basic authentication

        Args:
            auth_config: Authentication configuration dict

        Returns:
            Dictionary of headers with authentication
        """
        import base64

        headers = {"Content-Type": "application/json"}

        auth_type = auth_config.get("type", "")

        if auth_type == "api_key":
            if auth_config.get("location") == "header":
                key_name = auth_config.get("key", "Authorization")
                key_value = auth_config.get("value", "")
                headers[key_name] = key_value
        elif auth_type == "bearer":
            token = auth_config.get("token", "")
            headers["Authorization"] = f"Bearer {token}"
        elif auth_type == "basic":
            username = auth_config.get("username", "")
            password = auth_config.get("password", "")
            credentials = f"{username}:{password}"
            encoded = base64.b64encode(credentials.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"

        return headers

    @staticmethod
    def _format_error(error: Exception, context: str = "") -> str:
        """
        Format error messages consistently across all tools.

        Args:
            error: The exception that occurred
            context: Optional context about where/why the error occurred

        Returns:
            Formatted error string
        """
        error_msg = str(error)
        if context:
            return f"Error: {error_msg} ({context})"
        return f"Error: {error_msg}"

    @staticmethod
    def _validate_tool_implementation(tool_config: Dict[str, Any], impl_config: Dict[str, Any]) -> List[str]:
        """
        Validate implementation configuration before tool creation.

        Performs tool-type-specific validation to catch configuration errors early.

        Args:
            tool_config: Tool configuration dictionary
            impl_config: Implementation-specific configuration

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        tool_type = tool_config.get("tool_type", "")

        if tool_type == ToolTypes.API:
            if not impl_config.get("url"):
                errors.append("API tool requires 'url' in implementation_config")
            if not impl_config.get("method"):
                errors.append("API tool requires 'method' in implementation_config")

        elif tool_type == ToolTypes.NOTIFICATION:
            provider = impl_config.get("provider", "")
            if provider == "slack":
                if not impl_config.get("webhook_url"):
                    errors.append("Slack notification requires 'webhook_url'")
            elif provider == "discord":
                if not impl_config.get("webhook_url") and not impl_config.get("webhooks"):
                    errors.append("Discord notification requires 'webhook_url' or 'webhooks' dict")
            elif provider == "wordpress":
                if not impl_config.get("site_url") or not impl_config.get("username") or not impl_config.get("app_password"):
                    errors.append("WordPress tool requires 'site_url', 'username', and 'app_password'")

        elif tool_type == ToolTypes.DATABASE:
            if not impl_config.get("connection_string"):
                errors.append("Database tool requires 'connection_string'")
            db_type = impl_config.get("db_type", "")
            if db_type not in ["postgres", "postgresql", "mysql", "mongodb"]:
                errors.append(f"Unsupported database type: {db_type}")

        elif tool_type == ToolTypes.IMAGE_VIDEO:
            if not impl_config.get("provider"):
                errors.append("Image/video tool requires 'provider' (openai, google)")
            if not impl_config.get("model"):
                errors.append("Image/video tool requires 'model'")

        elif tool_type == ToolTypes.DATA_TRANSFORM:
            if not impl_config.get("input_format") or not impl_config.get("output_format"):
                errors.append("Data transform tool requires 'input_format' and 'output_format'")

        return errors

    @staticmethod
    def _validate_url_ssrf(url: str) -> bool:
        """
        Validate URL to prevent Server-Side Request Forgery (SSRF) attacks.

        Blocks requests to:
        - Private IP ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
        - Localhost (127.0.0.0/8, ::1)
        - Cloud metadata endpoints (169.254.169.254, metadata.google.internal)

        Args:
            url: URL to validate

        Returns:
            True if URL is safe, False if it should be blocked

        Raises:
            ValueError: If URL targets internal/private resources
        """
        import ipaddress
        import socket

        try:
            parsed = urlparse(url)
            hostname = parsed.hostname

            if not hostname:
                raise ValueError("Invalid URL: No hostname found")

            # Block cloud metadata endpoints
            if hostname in ["169.254.169.254", "metadata.google.internal", "metadata", "169.254.169.254"]:
                raise ValueError(f"SSRF Protection: Access to cloud metadata endpoint blocked: {hostname}")

            # Resolve hostname to IP
            try:
                ip = socket.gethostbyname(hostname)
                ip_obj = ipaddress.ip_address(ip)

                # Block private IP ranges
                if ip_obj.is_private:
                    raise ValueError(f"SSRF Protection: Access to private IP address blocked: {ip}")

                # Block localhost
                if ip_obj.is_loopback:
                    raise ValueError(f"SSRF Protection: Access to localhost blocked: {ip}")

                # Block link-local addresses
                if ip_obj.is_link_local:
                    raise ValueError(f"SSRF Protection: Access to link-local address blocked: {ip}")

            except socket.gaierror:
                # If DNS resolution fails, allow it (might be valid external domain with temporary DNS issues)
                logger.warning(f"Could not resolve hostname for SSRF check: {hostname}")

            return True

        except ValueError as e:
            logger.error(f"SSRF validation failed for URL {url}: {e}")
            raise

    @staticmethod
    def _validate_mongodb_query(query: Dict[str, Any]) -> bool:
        """
        Validate MongoDB query to prevent injection attacks.

        Blocks dangerous operators:
        - $where (allows arbitrary JavaScript execution)
        - $function (allows arbitrary JavaScript)
        - $accumulator (allows arbitrary JavaScript)

        Args:
            query: MongoDB query dictionary

        Returns:
            True if query is safe

        Raises:
            ValueError: If query contains dangerous operators
        """
        dangerous_operators = ["$where", "$function", "$accumulator"]

        def check_dict(d: Any) -> None:
            """Recursively check dictionary for dangerous operators"""
            if isinstance(d, dict):
                for key, value in d.items():
                    if key in dangerous_operators:
                        raise ValueError(f"MongoDB query validation failed: Dangerous operator '{key}' not allowed")
                    check_dict(value)
            elif isinstance(d, list):
                for item in d:
                    check_dict(item)

        try:
            check_dict(query)
            return True
        except ValueError as e:
            logger.error(f"MongoDB query validation failed: {e}")
            raise

    # =============================================================================
    # API Tool Creator
    # =============================================================================

    @staticmethod
    async def _create_api_tool(
        tool_config: Dict[str, Any],
        project_id: Optional[int]
    ) -> BaseTool:
        """Create an API/Webhook tool"""
        impl_config = tool_config["implementation_config"]

        # Route WordPress tools to specialized handler
        if impl_config.get("provider") == "wordpress":
            return await ToolFactory._create_wordpress_tool(tool_config, impl_config)

        # Extract API configuration
        method = impl_config.get("method", "GET")
        url_template = impl_config.get("url", "")
        headers = impl_config.get("headers", {})
        auth_config = impl_config.get("auth", {})
        body_template = impl_config.get("body_template", None)
        timeout = impl_config.get("timeout", 30)

        # SSRF Protection: Validate base URL (template without parameters)
        # Extract base URL by removing template variables for validation
        base_url_for_validation = url_template.split("{")[0] if "{" in url_template else url_template
        if base_url_for_validation:
            try:
                ToolFactory._validate_url_ssrf(base_url_for_validation)
            except ValueError as e:
                logger.error(f"API tool URL failed SSRF validation: {e}")
                raise ValueError(f"URL validation failed: {e}")

        # Create async function for API call with polling support
        async def api_call_impl(**kwargs) -> str:
            """Execute the API call with provided parameters.

            Supports long-running operations with polling:
            - Auto-detects 202 Accepted responses with Location header (Smart Polling)
            - Manual polling configuration via polling config
            - Configurable timeout and poll intervals
            """
            import asyncio
            import time

            # Extract polling configuration
            polling_config = impl_config.get("polling", {})
            poll_url_template = polling_config.get("url", "")
            poll_interval = polling_config.get("interval", 5)
            poll_timeout = polling_config.get("timeout", 300)
            completion_condition = polling_config.get("completion_condition", "")

            try:
                # Substitute variables in URL
                url = url_template.format(**kwargs)

                # Substitute variables in headers
                formatted_headers = {}
                for key, value in headers.items():
                    formatted_headers[key] = value.format(**kwargs) if isinstance(value, str) else value

                # Handle authentication
                if auth_config.get("type") == "api_key":
                    if auth_config.get("location") == "header":
                        formatted_headers[auth_config.get("key", "Authorization")] = auth_config.get("value", "")
                elif auth_config.get("type") == "bearer":
                    formatted_headers["Authorization"] = f"Bearer {auth_config.get('token', '')}"

                # Prepare body if POST/PUT/PATCH
                body = None
                if method in ["POST", "PUT", "PATCH"] and body_template:
                    if isinstance(body_template, str):
                        body = body_template.format(**kwargs)
                    else:
                        body = json.dumps(body_template)

                # Make the initial request
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=formatted_headers,
                        content=body if isinstance(body, str) else None,
                        json=body if isinstance(body, dict) else None
                    )

                    # Check for errors
                    response.raise_for_status()

                    # If no polling configured, return result immediately
                    if not polling_config:
                        # Check for "Smart Polling" (202 Accepted)
                        if response.status_code == 202:
                            location = response.headers.get("location") or response.headers.get("Location")
                            if location:
                                logger.info(f"Smart Polling: Detected 202 Accepted with Location header. Starting auto-polling.")
                                # Configure ad-hoc polling
                                poll_url_template = location
                                # If location is relative, construct absolute URL
                                if poll_url_template.startswith("/"):
                                    parsed_base = urlparse(url)
                                    base_url = f"{parsed_base.scheme}://{parsed_base.netloc}"
                                    poll_url_template = f"{base_url}{poll_url_template}"

                                poll_interval = 2  # Default to 2s for smart polling
                                poll_timeout = 300 # Default to 5m
                                completion_condition = "status_code != 202" # Stop when not 202

                                # Proceed to polling logic below
                                polling_config = {"smart": True}
                            else:
                                # 202 but no location, return as is
                                return response.text
                        else:
                            # Standard response
                            response_parser = impl_config.get("response_parser", {})
                            if response_parser.get("type") == "json_path":
                                json_data = response.json()
                                path = response_parser.get("path", "")
                                # Simple JSON path extraction (e.g., "data.result")
                                result = json_data
                                for key in path.split("."):
                                    result = result.get(key, {})
                                return str(result)
                            else:
                                return response.text

                    # --- Polling Logic ---
                    logger.info(f"API call successful, starting polling (timeout={poll_timeout}s)")
                    start_time = time.time()

                    # Helper to check completion condition
                    def check_completion(data: Any, status: int, condition: str) -> bool:
                        # Smart polling condition
                        if condition == "status_code != 202":
                            return status != 202

                        # Simple implementation: "field == value"
                        if "==" in condition:
                            key, value = condition.split("==", 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")

                            # Extract key from data
                            current = data
                            for k in key.split("."):
                                if isinstance(current, dict):
                                    current = current.get(k)
                                else:
                                    return False

                            return str(current) == value
                        return False

                    # Polling loop
                    while time.time() - start_time < poll_timeout:
                        # Wait before next poll (wait first for 202s to give time)
                        await asyncio.sleep(poll_interval)

                        # Make polling request
                        # For smart polling, the URL is fixed from Location header
                        # For manual polling, re-format template
                        if polling_config.get("smart"):
                            poll_url = poll_url_template
                        else:
                            poll_url = poll_url_template.format(**kwargs) if poll_url_template else url

                        async with httpx.AsyncClient(timeout=timeout) as poll_client:
                            response = await poll_client.get(
                                url=poll_url,
                                headers=formatted_headers
                            )
                            # Don't raise for status immediately on smart polling as 202 is expected
                            if not polling_config.get("smart"):
                                response.raise_for_status()

                        try:
                            json_data = response.json()
                        except:
                            json_data = {}

                        # Check if complete
                        if check_completion(json_data, response.status_code, completion_condition):
                            logger.info("Polling complete: Condition met")

                            # Parse final response
                            response_parser = impl_config.get("response_parser", {})
                            if response_parser.get("type") == "json_path":
                                path = response_parser.get("path", "")
                                result = json_data
                                for key in path.split("."):
                                    result = result.get(key, {})
                                return str(result)
                            else:
                                return response.text

                    return "Error: Polling timed out before completion condition was met"
            except httpx.TimeoutException:
                logger.error(f"API call timed out after {timeout}s")
                return f"Error: Request timed out after {timeout} seconds"
            except Exception as e:
                logger.error(f"API call failed: {e}")
                return f"Error: {str(e)}"

        # Create args schema
        args_schema = ToolFactory._create_pydantic_args_schema(
            tool_config["input_schema"],
            tool_config["tool_id"]
        )

        # Create the tool
        tool = StructuredTool.from_function(
            coroutine=api_call_impl,
            name=tool_config["tool_id"],
            description=tool_config["description"],
            args_schema=args_schema,
            handle_tool_error=True  # Allow agent to recover from tool errors
        )

        logger.info(f"Created API tool: {tool_config['name']}")
        return tool

    # =============================================================================
    # Notification Tool Creator
    # =============================================================================

    @staticmethod
    async def _create_notification_tool(
        tool_config: Dict[str, Any],
        project_id: Optional[int]
    ) -> BaseTool:
        """Create a Notification tool (Slack/Discord)"""
        impl_config = tool_config["implementation_config"]
        provider = impl_config.get("provider", "slack")

        if provider == "slack":
            return await ToolFactory._create_slack_notification_tool(tool_config, impl_config)
        elif provider == "discord":
            return await ToolFactory._create_discord_notification_tool(tool_config, impl_config)
        else:
            raise ValueError(f"Unsupported notification provider: {provider}")

    @staticmethod
    async def _create_slack_notification_tool(
        tool_config: Dict[str, Any],
        impl_config: Dict[str, Any]
    ) -> BaseTool:
        """Create a Slack notification tool"""
        # Fallback to SLACK_WEBHOOK_URL from environment if not in config
        webhook_url = impl_config.get("webhook_url") or os.getenv("SLACK_WEBHOOK_URL") or ""
        default_channel = impl_config.get("channel", "#general")
        message_template = impl_config.get("message_template", "{message}")
        username = impl_config.get("username", "LangConfig Bot")
        icon_emoji = impl_config.get("icon_emoji", ":robot_face:")
        timeout = impl_config.get("timeout", 10)

        if not webhook_url:
            raise ValueError("Slack webhook_url is required. Set SLACK_WEBHOOK_URL in .env or configure in tool settings.")

        async def send_slack_message(
            message: str,
            channel: Optional[str] = None,
            priority: str = "normal"
        ) -> str:
            """Send a message to Slack via webhook"""
            try:
                # Format the message template
                formatted_message = message_template.format(message=message)

                # Add priority indicators
                if priority == "high":
                    formatted_message = f"⚠️ *HIGH PRIORITY*\n{formatted_message}"
                elif priority == "urgent":
                    formatted_message = f"🚨 *URGENT*\n{formatted_message}"

                # Prepare Slack payload
                payload = {
                    "text": formatted_message,
                    "username": username,
                    "icon_emoji": icon_emoji
                }

                # Override channel if specified
                if channel:
                    payload["channel"] = channel
                elif default_channel:
                    payload["channel"] = default_channel

                # Send to Slack
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        webhook_url,
                        json=payload
                    )

                    response.raise_for_status()

                    logger.info(f"Slack notification sent successfully to {channel or default_channel}")
                    return f"Message sent to Slack ({channel or default_channel})"

            except httpx.HTTPStatusError as e:
                error_msg = f"Slack API error {e.response.status_code}: {e.response.text}"
                logger.error(error_msg)
                return f"Error: {error_msg}"
            except httpx.TimeoutException:
                error_msg = f"Slack notification timed out after {timeout}s"
                logger.error(error_msg)
                return f"Error: {error_msg}"
            except Exception as e:
                error_msg = f"Failed to send Slack notification: {str(e)}"
                logger.error(error_msg)
                return f"Error: {error_msg}"

        # Create args schema
        args_schema = ToolFactory._create_pydantic_args_schema(
            tool_config["input_schema"],
            tool_config["tool_id"]
        )

        # Create the tool
        tool = StructuredTool.from_function(
            coroutine=send_slack_message,
            name=tool_config["tool_id"],
            description=tool_config["description"],
            args_schema=args_schema,
            handle_tool_error=True  # Allow agent to recover from tool errors
        )

        logger.info(f"Created Slack notification tool: {tool_config['name']}")
        return tool

    @staticmethod
    async def _create_discord_notification_tool(
        tool_config: Dict[str, Any],
        impl_config: Dict[str, Any]
    ) -> BaseTool:
        """Create a Discord notification tool (supports multiple channels via webhooks)"""
        # Support both single webhook and multi-channel webhooks
        # Fallback to DISCORD_WEBHOOK_URL from environment if not in config
        default_webhook_url = impl_config.get("webhook_url") or os.getenv("DISCORD_WEBHOOK_URL") or ""
        webhooks = impl_config.get("webhooks", {})  # Dict of channel_name -> webhook_url
        default_channel = impl_config.get("default_channel", "default")

        default_username = impl_config.get("username", "LangConfig Bot")
        avatar_url = impl_config.get("avatar_url", "")
        message_template = impl_config.get("message_template", "{message}")
        use_embeds = impl_config.get("use_embeds", True)
        default_embed_color = impl_config.get("embed_color", "#5865F2")
        timeout = impl_config.get("timeout", 10)

        # Require at least one webhook configured
        if not default_webhook_url and not webhooks:
            raise ValueError("Discord webhook_url or webhooks dictionary is required. Set DISCORD_WEBHOOK_URL in .env or configure in tool settings.")

        async def send_discord_message(
            message: str,
            channel: str = "default",
            title: Optional[str] = None,
            color: Optional[str] = None,
            username: Optional[str] = None
        ) -> str:
            """Send a message to Discord via webhook

            Args:
                message: Message content to send
                channel: Channel name (if using multi-channel setup) or "default"
                title: Embed title (if using embeds)
                color: Embed color in hex (e.g., #FF0000)
                username: Override bot username for this message
            """
            try:
                # Determine which webhook URL to use
                target_webhook = None

                # First, check if channel is specified and exists in webhooks dict
                if channel and channel != "default" and channel in webhooks:
                    target_webhook = webhooks[channel]
                    logger.info(f"Using webhook for channel: {channel}")
                # Otherwise, check if default_channel is in webhooks
                elif default_channel in webhooks:
                    target_webhook = webhooks[default_channel]
                    channel = default_channel
                    logger.info(f"Using default channel webhook: {default_channel}")
                # Fall back to single webhook_url
                elif default_webhook_url:
                    target_webhook = default_webhook_url
                    logger.info("Using default webhook_url")
                else:
                    raise ValueError(
                        f"No webhook configured for channel '{channel}'. "
                        f"Available channels: {', '.join(webhooks.keys()) if webhooks else 'none'}"
                    )

                # Format the message template
                formatted_message = message_template.format(message=message)

                # Prepare Discord payload
                # Use provided username parameter or fall back to default username from config
                payload = {
                    "username": username or default_username,
                    "content": "" if use_embeds else formatted_message
                }

                if avatar_url:
                    payload["avatar_url"] = avatar_url

                # Use embeds if enabled
                if use_embeds:
                    embed_color_value = int((color or default_embed_color).replace("#", ""), 16)

                    embed = {
                        "description": formatted_message,
                        "color": embed_color_value,
                        "timestamp": datetime.utcnow().isoformat()
                    }

                    if title:
                        embed["title"] = title

                    payload["embeds"] = [embed]

                # Send to Discord
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        target_webhook,
                        json=payload
                    )

                    response.raise_for_status()

                    channel_info = f" to channel '{channel}'" if channel != "default" else ""
                    logger.info(f"Discord notification sent successfully{channel_info}")
                    return f"Message sent to Discord{channel_info}"

            except httpx.HTTPStatusError as e:
                error_msg = f"Discord API error {e.response.status_code}: {e.response.text}"
                logger.error(error_msg)
                return f"Error: {error_msg}"
            except httpx.TimeoutException:
                error_msg = f"Discord notification timed out after {timeout}s"
                logger.error(error_msg)
                return f"Error: {error_msg}"
            except ValueError as e:
                error_msg = f"Invalid configuration or color format: {e}"
                logger.error(error_msg)
                return f"Error: {error_msg}"
            except Exception as e:
                error_msg = f"Failed to send Discord notification: {str(e)}"
                logger.error(error_msg)
                return f"Error: {error_msg}"

        # Create args schema
        args_schema = ToolFactory._create_pydantic_args_schema(
            tool_config["input_schema"],
            tool_config["tool_id"]
        )

        # Create the tool
        tool = StructuredTool.from_function(
            coroutine=send_discord_message,
            name=tool_config["tool_id"],
            description=tool_config["description"],
            args_schema=args_schema,
            handle_tool_error=True  # Allow agent to recover from tool errors
        )

        logger.info(f"Created Discord notification tool: {tool_config['name']}")
        return tool

    @staticmethod
    async def _create_wordpress_tool(
        tool_config: Dict[str, Any],
        impl_config: Dict[str, Any]
    ) -> BaseTool:
        """Create a WordPress CMS tool using REST API"""
        import base64

        site_url = impl_config.get("site_url", "").rstrip('/')
        username = impl_config.get("username", "")
        app_password = impl_config.get("app_password", "")
        default_author_id = impl_config.get("default_author_id", 1)
        default_status = impl_config.get("default_status", "draft")
        timeout = impl_config.get("timeout", 30)

        if not site_url or not username or not app_password:
            raise ValueError("WordPress site_url, username, and app_password are required")

        # Create Basic Auth header
        auth_string = f"{username}:{app_password}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        auth_header = f"Basic {auth_b64}"

        async def wordpress_action(
            action: str,
            title: Optional[str] = None,
            content: Optional[str] = None,
            excerpt: Optional[str] = "",
            status: str = "draft",
            post_id: Optional[int] = None,
            categories: Optional[list] = None,
            tags: Optional[list] = None,
            featured_image_url: Optional[str] = "",
            author_id: Optional[int] = None
        ) -> str:
            """Execute WordPress REST API actions

            Args:
                action: create_post, update_post, publish_post, delete_post, get_post
                title: Post title
                content: Post content (HTML or plain text)
                excerpt: Post excerpt
                status: Post status (draft, publish, pending, private)
                post_id: Post ID for update/publish/delete
                categories: List of category names or IDs
                tags: List of tag names
                featured_image_url: URL of featured image
                author_id: Author ID
            """
            try:
                headers = {
                    "Authorization": auth_header,
                    "Content-Type": "application/json"
                }

                # Base API URL
                api_base = f"{site_url}/wp-json/wp/v2"

                if action == "create_post":
                    # Create new post
                    payload = {
                        "title": title or "Untitled",
                        "content": content or "",
                        "status": status or default_status,
                        "author": author_id or default_author_id
                    }

                    if excerpt:
                        payload["excerpt"] = excerpt

                    # Handle categories (convert names to IDs if needed)
                    if categories:
                        cat_ids = await _resolve_categories(categories, headers, api_base)
                        if cat_ids:
                            payload["categories"] = cat_ids

                    # Handle tags (convert names to IDs if needed)
                    if tags:
                        tag_ids = await _resolve_tags(tags, headers, api_base)
                        if tag_ids:
                            payload["tags"] = tag_ids

                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.post(
                            f"{api_base}/posts",
                            headers=headers,
                            json=payload
                        )
                        response.raise_for_status()
                        result = response.json()

                        post_id = result.get("id")
                        post_link = result.get("link", "")
                        logger.info(f"Created WordPress post ID {post_id}: {title}")
                        return f"Post created successfully! ID: {post_id}, Status: {status}, Link: {post_link}"

                elif action == "update_post":
                    if not post_id:
                        return "Error: post_id is required for update_post action"

                    payload = {}
                    if title:
                        payload["title"] = title
                    if content:
                        payload["content"] = content
                    if excerpt:
                        payload["excerpt"] = excerpt
                    if status:
                        payload["status"] = status

                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.post(
                            f"{api_base}/posts/{post_id}",
                            headers=headers,
                            json=payload
                        )
                        response.raise_for_status()
                        result = response.json()

                        logger.info(f"Updated WordPress post ID {post_id}")
                        return f"Post {post_id} updated successfully! Link: {result.get('link', '')}"

                elif action == "publish_post":
                    if not post_id:
                        return "Error: post_id is required for publish_post action"

                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.post(
                            f"{api_base}/posts/{post_id}",
                            headers=headers,
                            json={"status": "publish"}
                        )
                        response.raise_for_status()
                        result = response.json()

                        logger.info(f"Published WordPress post ID {post_id}")
                        return f"Post {post_id} published successfully! Link: {result.get('link', '')}"

                elif action == "delete_post":
                    if not post_id:
                        return "Error: post_id is required for delete_post action"

                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.delete(
                            f"{api_base}/posts/{post_id}",
                            headers=headers
                        )
                        response.raise_for_status()

                        logger.info(f"Deleted WordPress post ID {post_id}")
                        return f"Post {post_id} moved to trash successfully"

                elif action == "get_post":
                    if not post_id:
                        return "Error: post_id is required for get_post action"

                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.get(
                            f"{api_base}/posts/{post_id}",
                            headers=headers
                        )
                        response.raise_for_status()
                        result = response.json()

                        return f"Post {post_id}: {result.get('title', {}).get('rendered', 'No title')}\nStatus: {result.get('status')}\nLink: {result.get('link', '')}"

                else:
                    return f"Error: Unknown action '{action}'"

            except httpx.HTTPStatusError as e:
                error_msg = f"WordPress API error {e.response.status_code}: {e.response.text}"
                logger.error(error_msg)
                return f"Error: {error_msg}"
            except httpx.TimeoutException:
                error_msg = f"WordPress API timed out after {timeout}s"
                logger.error(error_msg)
                return f"Error: {error_msg}"
            except Exception as e:
                error_msg = f"Failed to execute WordPress action: {str(e)}"
                logger.error(error_msg)
                return f"Error: {error_msg}"

        async def _resolve_categories(category_names, headers, api_base):
            """Convert category names to IDs"""
            try:
                cat_ids = []
                async with httpx.AsyncClient(timeout=timeout) as client:
                    for cat in category_names:
                        if isinstance(cat, int):
                            cat_ids.append(cat)
                        else:
                            # Search for category by name
                            response = await client.get(
                                f"{api_base}/categories",
                                headers=headers,
                                params={"search": cat}
                            )
                            results = response.json()
                            if results:
                                cat_ids.append(results[0]["id"])
                return cat_ids
            except Exception as e:
                logger.warning(f"Failed to resolve categories: {e}")
                return []

        async def _resolve_tags(tag_names, headers, api_base):
            """Convert tag names to IDs, creating new tags if needed"""
            try:
                tag_ids = []
                async with httpx.AsyncClient(timeout=timeout) as client:
                    for tag in tag_names:
                        if isinstance(tag, int):
                            tag_ids.append(tag)
                        else:
                            # Search for tag by name
                            response = await client.get(
                                f"{api_base}/tags",
                                headers=headers,
                                params={"search": tag}
                            )
                            results = response.json()
                            if results:
                                tag_ids.append(results[0]["id"])
                            else:
                                # Create new tag
                                create_response = await client.post(
                                    f"{api_base}/tags",
                                    headers=headers,
                                    json={"name": tag}
                                )
                                if create_response.status_code == 201:
                                    tag_ids.append(create_response.json()["id"])
                return tag_ids
            except Exception as e:
                logger.warning(f"Failed to resolve tags: {e}")
                return []

        # Create args schema
        args_schema = ToolFactory._create_pydantic_args_schema(
            tool_config["input_schema"],
            tool_config["tool_id"]
        )

        # Create the tool
        tool = StructuredTool.from_function(
            coroutine=wordpress_action,
            name=tool_config["tool_id"],
            description=tool_config["description"],
            args_schema=args_schema,
            handle_tool_error=True  # Allow agent to recover from tool errors
        )

        logger.info(f"Created WordPress tool: {tool_config['name']}")
        return tool

    # =============================================================================
    # Image/Video Tool Creator
    # =============================================================================

    @staticmethod
    async def _create_image_video_tool(
        tool_config: Dict[str, Any],
        project_id: Optional[int]
    ) -> BaseTool:
        """Create an Image/Video generation tool"""
        impl_config = tool_config["implementation_config"]
        provider = impl_config.get("provider", "openai")
        model = impl_config.get("model", "dall-e-3")
        template_type = tool_config.get("template_type", "")

        # Route to appropriate generator
        if provider == "openai":
            if "dalle" in model.lower():
                return await ToolFactory._create_openai_dalle_tool(tool_config, impl_config)
            elif "sora" in model.lower():
                return await ToolFactory._create_openai_sora_tool(tool_config, impl_config)
        elif provider == "google":
            # Nano Banana (Gemini 2.5 Flash Image), Imagen 3, and Veo all use the same routing
            if "imagen" in model.lower() or "gemini" in model.lower() or "flash" in model.lower():
                return await ToolFactory._create_gemini_imagen_tool(tool_config, impl_config)
            elif "veo" in model.lower():
                return await ToolFactory._create_gemini_veo_tool(tool_config, impl_config)

        raise ValueError(f"Unsupported image/video provider/model: {provider}/{model}")

    @staticmethod
    async def _create_openai_dalle_tool(
        tool_config: Dict[str, Any],
        impl_config: Dict[str, Any]
    ) -> BaseTool:
        """Create OpenAI DALL-E 3 image generation tool"""
        # Fallback to OPENAI_API_KEY from environment if not in config
        api_key = impl_config.get("api_key") or os.getenv("OPENAI_API_KEY") or ""
        model = impl_config.get("model", "dall-e-3")
        default_size = impl_config.get("size", "1024x1024")
        default_quality = impl_config.get("quality", "standard")
        default_style = impl_config.get("style", "vivid")
        timeout = impl_config.get("timeout", 60)

        if not api_key:
            raise ValueError("OpenAI API key is required for DALL-E 3. Set OPENAI_API_KEY in .env or configure in tool settings.")

        async def generate_dalle_image(
            prompt: str,
            size: Optional[str] = None,
            quality: Optional[str] = None
        ) -> str:
            """Generate an image using DALL-E 3"""
            try:
                # Prepare request payload
                payload = {
                    "model": model,
                    "prompt": prompt,
                    "n": 1,
                    "size": size or default_size,
                    "quality": quality or default_quality,
                    "style": default_style
                }

                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }

                # Call OpenAI API
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        "https://api.openai.com/v1/images/generations",
                        json=payload,
                        headers=headers
                    )

                    response.raise_for_status()
                    data = response.json()

                    # Extract image URL
                    if data.get("data") and len(data["data"]) > 0:
                        image_url = data["data"][0]["url"]
                        logger.info(f"DALL-E 3 image generated successfully")
                        return f"Image generated successfully: {image_url}"
                    else:
                        return "Error: No image was generated"

            except httpx.HTTPStatusError as e:
                error_data = e.response.json() if e.response.headers.get("content-type") == "application/json" else {}
                error_msg = error_data.get("error", {}).get("message", str(e))
                logger.error(f"DALL-E 3 API error: {error_msg}")
                return f"Error: {error_msg}"
            except httpx.TimeoutException:
                logger.error(f"DALL-E 3 request timed out")
                return f"Error: Request timed out after {timeout}s"
            except Exception as e:
                logger.error(f"DALL-E 3 generation failed: {e}")
                return f"Error: {str(e)}"

        # Create args schema
        args_schema = ToolFactory._create_pydantic_args_schema(
            tool_config["input_schema"],
            tool_config["tool_id"]
        )

        tool = StructuredTool.from_function(
            coroutine=generate_dalle_image,
            name=tool_config["tool_id"],
            description=tool_config["description"],
            args_schema=args_schema,
            handle_tool_error=True  # Allow agent to recover from tool errors
        )

        logger.info(f"Created DALL-E 3 tool: {tool_config['name']}")
        return tool

    @staticmethod
    async def _create_openai_sora_tool(
        tool_config: Dict[str, Any],
        impl_config: Dict[str, Any]
    ) -> BaseTool:
        """Create OpenAI Sora video generation tool"""
        # Fallback to OPENAI_API_KEY from environment if not in config
        api_key = impl_config.get("api_key") or os.getenv("OPENAI_API_KEY") or ""
        model = impl_config.get("model", "sora")
        default_duration = impl_config.get("duration", 5)
        default_resolution = impl_config.get("resolution", "1080p")
        timeout = impl_config.get("timeout", 120)

        if not api_key:
            raise ValueError("OpenAI API key is required for Sora. Set OPENAI_API_KEY in .env or configure in tool settings.")

        async def generate_sora_video(
            prompt: str,
            duration: Optional[int] = None
        ) -> str:
            """Generate a video using Sora"""
            try:
                # Note: Sora API endpoint may vary - adjust when API is public
                payload = {
                    "model": model,
                    "prompt": prompt,
                    "duration": duration or default_duration,
                    "resolution": default_resolution
                }

                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }

                # Call OpenAI Sora API (endpoint subject to change)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        "https://api.openai.com/v1/videos/generations",
                        json=payload,
                        headers=headers
                    )

                    response.raise_for_status()
                    data = response.json()

                    # Extract video URL
                    if data.get("data") and len(data["data"]) > 0:
                        video_url = data["data"][0]["url"]
                        logger.info(f"Sora video generated successfully")
                        return f"Video generated successfully: {video_url}"
                    else:
                        return "Error: No video was generated"

            except httpx.HTTPStatusError as e:
                error_data = e.response.json() if e.response.headers.get("content-type") == "application/json" else {}
                error_msg = error_data.get("error", {}).get("message", str(e))
                logger.error(f"Sora API error: {error_msg}")
                return f"Error: {error_msg}"
            except httpx.TimeoutException:
                logger.error(f"Sora request timed out")
                return f"Error: Request timed out after {timeout}s"
            except Exception as e:
                logger.error(f"Sora generation failed: {e}")
                return f"Error: {str(e)}"

        args_schema = ToolFactory._create_pydantic_args_schema(
            tool_config["input_schema"],
            tool_config["tool_id"]
        )

        tool = StructuredTool.from_function(
            coroutine=generate_sora_video,
            name=tool_config["tool_id"],
            description=tool_config["description"],
            args_schema=args_schema,
            handle_tool_error=True  # Allow agent to recover from tool errors
        )

        logger.info(f"Created Sora tool: {tool_config['name']}")
        return tool

    @staticmethod
    async def _create_gemini_imagen_tool(
        tool_config: Dict[str, Any],
        impl_config: Dict[str, Any]
    ) -> BaseTool:
        """Create Google Gemini Imagen 3 / Nano Banana (Gemini 2.5 Flash Image) generation tool"""
        # Fallback chain: tool config -> settings -> env vars
        api_key = (
            impl_config.get("api_key") or
            settings.GOOGLE_API_KEY or
            os.getenv("GEMINI_API_KEY") or
            os.getenv("GOOGLE_API_KEY") or
            ""
        )
        model = impl_config.get("model", "gemini-3-pro-image-preview")
        default_aspect_ratio = impl_config.get("aspect_ratio", "1:1")
        num_images = impl_config.get("num_images", 1)
        safety_filter = impl_config.get("safety_filter_level", "block_most")
        timeout = impl_config.get("timeout", 60)

        if not api_key:
            raise ValueError("Google API key is required for Imagen/Nano Banana. Set GEMINI_API_KEY in .env or configure in tool settings.")

        # Log which model is being used
        logger.info(f"Creating Google image generation tool: {model} (API key source: {'config' if impl_config.get('api_key') else 'environment'})")

        async def generate_imagen_image(
            prompt: str,
            aspect_ratio: Optional[str] = None,
            style: Optional[str] = None,
            quality: Optional[str] = None,
            negative_prompt: Optional[str] = None
        ) -> str:
            """Generate an image using Imagen 3 or Nano Banana (Gemini 2.5 Flash Image)

            Args:
                prompt: Description of the image to generate
                aspect_ratio: Image aspect ratio (1:1, 16:9, 9:16, 4:3, 3:4)
                style: Optional style modifier (e.g., 'vivid', 'natural', 'photorealistic')
                quality: Optional quality setting (e.g., 'standard', 'hd')
                negative_prompt: Elements to avoid in the generated image
            """
            try:
                # Enhance prompt with style if provided
                enhanced_prompt = prompt
                if style:
                    enhanced_prompt = f"{prompt}, {style} style"
                if negative_prompt:
                    enhanced_prompt = f"{enhanced_prompt}. Avoid: {negative_prompt}"

                # Use Google AI Studio API for Gemini models (Nano Banana)
                if "gemini" in model.lower() or "flash" in model.lower() or model == "gemini-2.5-flash-image":
                    # Google AI Studio endpoint for Gemini image generation
                    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

                    payload = {
                        "contents": [{
                            "parts": [{
                                "text": enhanced_prompt
                            }]
                        }],
                        "generationConfig": {
                            "responseModalities": ["TEXT", "IMAGE"],
                            "temperature": 0.4,
                            "candidateCount": num_images,
                            "maxOutputTokens": 8192,
                        }
                    }

                    headers = {
                        "Content-Type": "application/json"
                    }

                    # Add API key as query parameter for Google AI Studio
                    url = f"{endpoint}?key={api_key}"

                else:
                    # Use Vertex AI endpoint for Imagen 3
                    endpoint = "https://us-central1-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/us-central1/publishers/google/models/imagegeneration:predict"

                    payload = {
                        "instances": [
                            {
                                "prompt": enhanced_prompt
                            }
                        ],
                        "parameters": {
                            "sampleCount": num_images,
                            "aspectRatio": aspect_ratio or default_aspect_ratio,
                            "safetyFilterLevel": safety_filter
                        }
                    }

                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    }

                    url = endpoint

                # Call the appropriate API
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        url,
                        json=payload,
                        headers=headers
                    )

                    response.raise_for_status()
                    data = response.json()

                    # Log the raw response for debugging
                    logger.info(f"Gemini API response keys: {data.keys() if isinstance(data, dict) else type(data)}")

                    # Extract image URL/data based on response format
                    if "gemini" in model.lower() or "flash" in model.lower():
                        # Google AI Studio response format
                        if data.get("candidates") and len(data["candidates"]) > 0:
                            candidate = data["candidates"][0]
                            if candidate.get("content", {}).get("parts"):
                                # Extract image data from response
                                parts = candidate["content"]["parts"]
                                logger.info(f"Gemini response has {len(parts)} parts, types: {[list(p.keys()) for p in parts]}")

                                # Collect both text and image from parts
                                image_data_uri = None
                                text_content = None
                                img_size_kb = 0

                                for part in parts:
                                    if "inlineData" in part:
                                        # Found image data
                                        img_data = part["inlineData"]["data"]
                                        mime_type = part["inlineData"]["mimeType"]
                                        image_data_uri = f"data:{mime_type};base64,{img_data}"
                                        img_size_kb = len(img_data) * 3 // 4 // 1024  # Approximate decoded size
                                        logger.info(f"Found image: {mime_type}, size: ~{img_size_kb}KB")
                                    elif "text" in part:
                                        text_content = part["text"]
                                        logger.info(f"Found text: {text_content[:100] if text_content else 'empty'}...")

                                # Return text to LLM, store image as artifact for UI
                                if image_data_uri:
                                    # Store image artifact for event emitter to pick up
                                    store_artifact({
                                        "type": "image",
                                        "data": img_data,
                                        "mimeType": mime_type
                                    })
                                    logger.info(f"Stored image artifact ({img_size_kb}KB) for UI display")
                                    # Return only text to LLM (avoids token limit issues)
                                    return f"Image generated successfully ({img_size_kb}KB). The image has been created and is displayed to the user."
                                elif text_content:
                                    # No image generated, just text response
                                    logger.warning(f"Gemini returned text only (no image): {text_content[:200]}")
                                    return text_content

                        logger.error(f"No valid image found in Gemini response: {data}")
                        return "Error: No image generated"

                    elif data.get("predictions") and len(data["predictions"]) > 0:
                        # Imagen returns base64 or GCS URLs depending on configuration
                        image_data = data["predictions"][0]
                        logger.info(f"Imagen 3 image generated successfully")
                        return f"Image generated successfully: {image_data}"
                    else:
                        return "Error: No image was generated"

            except httpx.HTTPStatusError as e:
                error_msg = f"Imagen API error {e.response.status_code}"
                logger.error(error_msg)
                return f"Error: {error_msg}"
            except httpx.TimeoutException:
                logger.error(f"Imagen request timed out")
                return f"Error: Request timed out after {timeout}s"
            except Exception as e:
                logger.error(f"Imagen generation failed: {e}")
                return f"Error: {str(e)}"

        args_schema = ToolFactory._create_pydantic_args_schema(
            tool_config["input_schema"],
            tool_config["tool_id"]
        )

        tool = StructuredTool.from_function(
            coroutine=generate_imagen_image,
            name=tool_config["tool_id"],
            description=tool_config["description"],
            args_schema=args_schema,
            handle_tool_error=True  # Allow agent to recover from tool errors
        )

        logger.info(f"✓ Created Google image tool: {tool_config['name']} (model: {model})")
        return tool

    @staticmethod
    async def _create_gemini_veo_tool(
        tool_config: Dict[str, Any],
        impl_config: Dict[str, Any]
    ) -> BaseTool:
        """Create Google Gemini Veo 3/3.1 video generation tool

        Supports three modes:
        1. Text-to-video: Generate video from text prompt only
        2. Image-to-video: Animate an image using prompt + image_url
        3. Video extension: Continue an existing video using prompt + video_url
        """
        # Fallback chain: tool config -> settings -> env vars
        api_key = (
            impl_config.get("api_key") or
            settings.GOOGLE_API_KEY or
            os.getenv("GEMINI_API_KEY") or
            os.getenv("GOOGLE_API_KEY") or
            ""
        )
        model = impl_config.get("model", "veo-3.1-fast-generate-preview")
        default_duration = impl_config.get("duration", 8)
        default_resolution = impl_config.get("resolution", "720p")
        default_fps = impl_config.get("fps", 24)
        default_aspect_ratio = impl_config.get("aspect_ratio", "16:9")
        generate_audio = impl_config.get("generate_audio", True)
        timeout = impl_config.get("timeout", 180)  # Video generation can take time

        if not api_key:
            raise ValueError("Google API key is required for Veo. Set GEMINI_API_KEY in .env or configure in tool settings.")

        logger.info(f"Creating Veo tool: {model} (API key source: {'config' if impl_config.get('api_key') else 'environment'})")

        async def generate_veo_video(
            prompt: str,
            image_url: Optional[str] = None,
            video_url: Optional[str] = None,
            duration: Optional[int] = None,
            aspect_ratio: Optional[str] = None,
            negative_prompt: Optional[str] = None
        ) -> str:
            """Generate a video using Veo 3.1

            Args:
                prompt: Text description of the video to generate
                image_url: Optional URL/base64 of an image to animate (image-to-video mode)
                video_url: Optional URL of a Veo-generated video to extend (video extension mode)
                duration: Video duration in seconds (4, 6, or 8)
                aspect_ratio: Video aspect ratio (16:9 or 9:16)
                negative_prompt: Elements to avoid in the video
            """
            try:
                # Determine generation mode
                if video_url:
                    mode = "video_extension"
                    logger.info(f"Veo mode: Video extension from existing video")
                elif image_url:
                    mode = "image_to_video"
                    logger.info(f"Veo mode: Image-to-video animation")
                else:
                    mode = "text_to_video"
                    logger.info(f"Veo mode: Text-to-video generation")

                # Build the prompt with negative prompt if provided
                full_prompt = prompt
                if negative_prompt:
                    full_prompt = f"{prompt}. Avoid: {negative_prompt}"

                # Google AI Studio API endpoint for Veo - uses predictLongRunning, NOT generateContent
                base_url = "https://generativelanguage.googleapis.com/v1beta"
                endpoint = f"{base_url}/models/{model}:predictLongRunning"

                # Build instance based on mode - Veo uses "instances" format, not "contents"
                instance = {"prompt": full_prompt}

                # Add aspectRatio and duration to the generation config
                generation_config = {
                    "aspectRatio": aspect_ratio or default_aspect_ratio,
                    "numberOfVideos": 1
                }

                # Note: Duration is handled by the model, Veo 3.1 generates 8s videos

                if image_url:
                    # Add image for image-to-video mode
                    if image_url.startswith("data:"):
                        # Base64 encoded image - extract MIME type and data
                        mime_match = image_url.split(";")[0].split(":")[1] if ";" in image_url else "image/jpeg"
                        base64_data = image_url.split(",")[1] if "," in image_url else image_url
                        instance["image"] = {
                            "bytesBase64Encoded": base64_data,
                            "mimeType": mime_match
                        }
                    else:
                        # URL reference
                        instance["image"] = {"imageUrl": image_url}

                if video_url:
                    # Add video for extension mode
                    instance["video"] = {"videoUrl": video_url}

                payload = {
                    "instances": [instance],
                    "parameters": generation_config
                }

                headers = {
                    "Content-Type": "application/json",
                    "x-goog-api-key": api_key  # API key in header, not URL
                }

                logger.info(f"Calling Veo API: mode={mode}, model={model}, endpoint=predictLongRunning")

                # Call Google AI Studio API - this starts an async operation
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.post(
                        endpoint,
                        json=payload,
                        headers=headers
                    )

                    response.raise_for_status()
                    data = response.json()

                    # Log response structure for debugging
                    logger.info(f"Veo API response keys: {data.keys() if isinstance(data, dict) else type(data)}")

                    # Response contains operation name for polling
                    if data.get("name"):
                        operation_name = data["name"]
                        logger.info(f"Veo video generation started: {operation_name}")

                        # Poll for completion (video gen can take 1-3 minutes)
                        poll_url = f"{base_url}/{operation_name}"
                        max_polls = 30  # Up to 5 minutes of polling (10s intervals)

                        for poll_count in range(max_polls):
                            await asyncio.sleep(10)  # Wait 10 seconds between polls

                            poll_response = await client.get(poll_url, headers=headers)
                            poll_data = poll_response.json()

                            is_done = poll_data.get("done", False)
                            logger.info(f"Veo poll {poll_count + 1}/{max_polls}: done={is_done}")

                            if is_done:
                                # Extract video from completed operation
                                gen_response = poll_data.get("response", {}).get("generateVideoResponse", {})
                                samples = gen_response.get("generatedSamples", [])

                                if samples:
                                    video_info = samples[0].get("video", {})
                                    video_uri = video_info.get("uri", "")

                                    if video_uri:
                                        # Download the video
                                        video_response = await client.get(
                                            video_uri,
                                            headers={"x-goog-api-key": api_key},
                                            follow_redirects=True
                                        )
                                        video_data = base64.b64encode(video_response.content).decode("utf-8")
                                        video_size_mb = len(video_response.content) / 1024 / 1024

                                        # Store video artifact for UI display
                                        store_artifact({
                                            "type": "video",
                                            "data": video_data,
                                            "mimeType": "video/mp4"
                                        })

                                        logger.info(f"Veo video generated: ~{video_size_mb:.1f}MB")
                                        return f"Video generated successfully ({video_size_mb:.1f}MB, ~8s). The video has been created and is displayed to the user."

                                # Check for errors in response
                                error = poll_data.get("error")
                                if error:
                                    logger.error(f"Veo generation error: {error}")
                                    return f"Error: {error.get('message', str(error))}"

                                logger.warning(f"Veo completed but no video found: {poll_data}")
                                return "Error: Video generation completed but no video was returned"

                        # Timeout - operation still in progress
                        return f"Video generation is still in progress. Operation ID: {operation_name}. Please try again in a few minutes."

                    # Unexpected response format
                    logger.warning(f"Unexpected Veo response format: {data}")
                    return "Error: Unexpected response format from Veo API"

            except httpx.HTTPStatusError as e:
                error_msg = f"Veo API error {e.response.status_code}"
                try:
                    error_detail = e.response.json()
                    if "error" in error_detail:
                        error_msg = f"{error_msg}: {error_detail['error'].get('message', str(error_detail))}"
                except:
                    pass
                logger.error(error_msg)
                return f"Error: {error_msg}"
            except httpx.TimeoutException:
                logger.error(f"Veo request timed out after {timeout}s")
                return f"Error: Request timed out after {timeout}s. Video generation can take up to 3 minutes."
            except Exception as e:
                logger.error(f"Veo generation failed: {e}")
                return f"Error: {str(e)}"

        args_schema = ToolFactory._create_pydantic_args_schema(
            tool_config["input_schema"],
            tool_config["tool_id"]
        )

        tool = StructuredTool.from_function(
            coroutine=generate_veo_video,
            name=tool_config["tool_id"],
            description=tool_config["description"],
            args_schema=args_schema,
            handle_tool_error=True  # Allow agent to recover from tool errors
        )

        logger.info(f"✓ Created Veo tool: {tool_config['name']} (model: {model})")
        return tool

    # =============================================================================
    # Database Tool Creator
    # =============================================================================

    @staticmethod
    async def _create_database_tool(
        tool_config: Dict[str, Any],
        project_id: Optional[int]
    ) -> BaseTool:
        """Create a Database query tool"""
        impl_config = tool_config["implementation_config"]
        db_type = impl_config.get("db_type", "postgres")

        if db_type in ["postgres", "postgresql"]:
            return await ToolFactory._create_postgres_tool(tool_config, impl_config)
        elif db_type == "mysql":
            return await ToolFactory._create_mysql_tool(tool_config, impl_config)
        elif db_type == "mongodb":
            return await ToolFactory._create_mongodb_tool(tool_config, impl_config)
        else:
            raise ValueError(f"Unsupported database type: {db_type}")

    @staticmethod
    async def _create_postgres_tool(
        tool_config: Dict[str, Any],
        impl_config: Dict[str, Any]
    ) -> BaseTool:
        """Create PostgreSQL query tool"""
        connection_string = impl_config.get("connection_string", "")
        query_template = impl_config.get("query_template", "SELECT * FROM {table}")
        read_only = impl_config.get("read_only", True)
        max_rows = impl_config.get("max_rows", 100)
        timeout = impl_config.get("timeout", 30)

        if not connection_string:
            raise ValueError("PostgreSQL connection_string is required")

        async def execute_postgres_query(**kwargs) -> str:
            """Execute a PostgreSQL query"""
            conn = None
            try:
                # Import asyncpg for PostgreSQL
                import asyncpg

                # Format the query with provided parameters
                query = query_template.format(**kwargs)

                # Check if read-only mode is enforced
                if read_only:
                    query_upper = query.upper().strip()
                    dangerous_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE"]
                    if any(keyword in query_upper for keyword in dangerous_keywords):
                        return f"Error: Read-only mode enabled. Query contains forbidden keyword."

                # Connect and execute
                conn = await asyncpg.connect(connection_string, timeout=timeout)

                # Limit rows
                if "LIMIT" not in query.upper():
                    query = f"{query} LIMIT {max_rows}"

                rows = await conn.fetch(query)

                # Format results
                if not rows:
                    return "Query executed successfully. No results returned."

                # Convert to list of dicts
                results = [dict(row) for row in rows]
                logger.info(f"PostgreSQL query returned {len(results)} rows")
                return json.dumps(results, indent=2, default=str)

            except Exception as e:
                logger.error(f"PostgreSQL query failed: {e}")
                return f"Error: {str(e)}"
            finally:
                if conn:
                    await conn.close()

        args_schema = ToolFactory._create_pydantic_args_schema(
            tool_config["input_schema"],
            tool_config["tool_id"]
        )

        tool = StructuredTool.from_function(
            coroutine=execute_postgres_query,
            name=tool_config["tool_id"],
            description=tool_config["description"],
            args_schema=args_schema,
            handle_tool_error=True  # Allow agent to recover from tool errors
        )

        logger.info(f"Created PostgreSQL tool: {tool_config['name']}")
        return tool

    @staticmethod
    async def _create_mysql_tool(
        tool_config: Dict[str, Any],
        impl_config: Dict[str, Any]
    ) -> BaseTool:
        """Create MySQL query tool"""
        connection_string = impl_config.get("connection_string", "")
        query_template = impl_config.get("query_template", "SELECT * FROM {table}")
        read_only = impl_config.get("read_only", True)
        max_rows = impl_config.get("max_rows", 100)
        timeout = impl_config.get("timeout", 30)

        if not connection_string:
            raise ValueError("MySQL connection_string is required")

        async def execute_mysql_query(**kwargs) -> str:
            """Execute a MySQL query"""
            conn = None
            try:
                # Import aiomysql for MySQL
                import aiomysql

                # Format the query
                query = query_template.format(**kwargs)

                # Read-only check
                if read_only:
                    query_upper = query.upper().strip()
                    dangerous_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE"]
                    if any(keyword in query_upper for keyword in dangerous_keywords):
                        return f"Error: Read-only mode enabled. Query contains forbidden keyword."

                # Parse connection string for aiomysql
                # Format: mysql://user:pass@host:port/database
                parsed = urlparse(connection_string)

                conn = await aiomysql.connect(
                    host=parsed.hostname,
                    port=parsed.port or 3306,
                    user=parsed.username,
                    password=parsed.password,
                    db=parsed.path.lstrip('/'),
                    connect_timeout=timeout
                )

                # Limit rows
                if "LIMIT" not in query.upper():
                    query = f"{query} LIMIT {max_rows}"

                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(query)
                    rows = await cursor.fetchall()

                if not rows:
                    return "Query executed successfully. No results returned."

                logger.info(f"MySQL query returned {len(rows)} rows")
                return json.dumps(rows, indent=2, default=str)

            except Exception as e:
                logger.error(f"MySQL query failed: {e}")
                return f"Error: {str(e)}"
            finally:
                if conn:
                    conn.close()

        args_schema = ToolFactory._create_pydantic_args_schema(
            tool_config["input_schema"],
            tool_config["tool_id"]
        )

        tool = StructuredTool.from_function(
            coroutine=execute_mysql_query,
            name=tool_config["tool_id"],
            description=tool_config["description"],
            args_schema=args_schema,
            handle_tool_error=True  # Allow agent to recover from tool errors
        )

        logger.info(f"Created MySQL tool: {tool_config['name']}")
        return tool

    @staticmethod
    async def _create_mongodb_tool(
        tool_config: Dict[str, Any],
        impl_config: Dict[str, Any]
    ) -> BaseTool:
        """Create MongoDB query tool"""
        connection_string = impl_config.get("connection_string", "")
        query_template = impl_config.get("query_template", "{}")
        read_only = impl_config.get("read_only", True)
        max_rows = impl_config.get("max_rows", 100)
        timeout = impl_config.get("timeout", 30)

        if not connection_string:
            raise ValueError("MongoDB connection_string is required")

        async def execute_mongodb_query(**kwargs) -> str:
            """Execute a MongoDB query"""
            client = None
            try:
                # Import motor for async MongoDB
                from motor.motor_asyncio import AsyncIOMotorClient

                # Format the query template
                query_str = query_template.format(**kwargs)
                query = json.loads(query_str) if isinstance(query_str, str) else query_str

                # Validate query for security (prevent injection attacks)
                try:
                    ToolFactory._validate_mongodb_query(query)
                except ValueError as e:
                    logger.error(f"MongoDB query validation failed: {e}")
                    return f"Error: Query validation failed - {str(e)}"

                # Collection and database from kwargs or config
                database_name = kwargs.get("database", impl_config.get("database", ""))
                collection_name = kwargs.get("collection", impl_config.get("collection", ""))

                if not database_name or not collection_name:
                    return "Error: database and collection parameters are required"

                # Connect to MongoDB
                client = AsyncIOMotorClient(connection_string, serverSelectionTimeoutMS=timeout * 1000)
                db = client[database_name]
                collection = db[collection_name]

                # Execute query
                cursor = collection.find(query).limit(max_rows)
                results = await cursor.to_list(length=max_rows)

                # Convert ObjectId to string for JSON serialization
                for doc in results:
                    if '_id' in doc:
                        doc['_id'] = str(doc['_id'])

                if not results:
                    return "Query executed successfully. No results returned."

                logger.info(f"MongoDB query returned {len(results)} documents")
                return json.dumps(results, indent=2, default=str)

            except Exception as e:
                logger.error(f"MongoDB query failed: {e}")
                return f"Error: {str(e)}"
            finally:
                if client:
                    client.close()  # Motor's close() is synchronous

        args_schema = ToolFactory._create_pydantic_args_schema(
            tool_config["input_schema"],
            tool_config["tool_id"]
        )

        tool = StructuredTool.from_function(
            coroutine=execute_mongodb_query,
            name=tool_config["tool_id"],
            description=tool_config["description"],
            args_schema=args_schema,
            handle_tool_error=True  # Allow agent to recover from tool errors
        )

        logger.info(f"Created MongoDB tool: {tool_config['name']}")
        return tool

    # =============================================================================
    # Data Transform Tool Creator
    # =============================================================================

    @staticmethod
    async def _create_data_transform_tool(
        tool_config: Dict[str, Any],
        project_id: Optional[int]
    ) -> BaseTool:
        """Create a Data transformation tool"""
        impl_config = tool_config["implementation_config"]
        input_format = impl_config.get("input_format", "json")
        output_format = impl_config.get("output_format", "csv")
        validate_output = impl_config.get("validate_output", True)

        async def transform_data(
            data: str,
            output_format_override: Optional[str] = None
        ) -> str:
            """Transform data between formats"""
            try:
                target_format = output_format_override or output_format

                # Parse input data
                parsed_data = None
                if input_format == "json":
                    parsed_data = json.loads(data)
                elif input_format == "csv":
                    import csv
                    import io
                    reader = csv.DictReader(io.StringIO(data))
                    parsed_data = list(reader)
                elif input_format == "xml":
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(data)
                    # Simple XML to dict conversion
                    parsed_data = ToolFactory._xml_to_dict(root)
                elif input_format == "yaml":
                    import yaml
                    parsed_data = yaml.safe_load(data)
                else:
                    return f"Error: Unsupported input format: {input_format}"

                # Transform to output format
                result = None
                if target_format == "json":
                    result = json.dumps(parsed_data, indent=2)
                elif target_format == "csv":
                    import csv
                    import io
                    if isinstance(parsed_data, list) and len(parsed_data) > 0:
                        output = io.StringIO()
                        if isinstance(parsed_data[0], dict):
                            # List of dicts
                            fieldnames = parsed_data[0].keys()
                            writer = csv.DictWriter(output, fieldnames=fieldnames)
                            writer.writeheader()
                            writer.writerows(parsed_data)
                        else:
                            # List of values
                            writer = csv.writer(output)
                            for row in parsed_data:
                                writer.writerow([row] if not isinstance(row, list) else row)
                        result = output.getvalue()
                    else:
                        return "Error: CSV output requires a list of objects"
                elif target_format == "xml":
                    import xml.etree.ElementTree as ET
                    root = ToolFactory._dict_to_xml("root", parsed_data)
                    result = ET.tostring(root, encoding='unicode')
                elif target_format == "yaml":
                    import yaml
                    result = yaml.dump(parsed_data, default_flow_style=False)
                else:
                    return f"Error: Unsupported output format: {target_format}"

                logger.info(f"Data transformed from {input_format} to {target_format}")
                return result

            except json.JSONDecodeError as e:
                return f"Error: Invalid JSON input - {str(e)}"
            except Exception as e:
                logger.error(f"Data transformation failed: {e}")
                return f"Error: {str(e)}"

        args_schema = ToolFactory._create_pydantic_args_schema(
            tool_config["input_schema"],
            tool_config["tool_id"]
        )

        tool = StructuredTool.from_function(
            coroutine=transform_data,
            name=tool_config["tool_id"],
            description=tool_config["description"],
            args_schema=args_schema,
            handle_tool_error=True  # Allow agent to recover from tool errors
        )

        logger.info(f"Created Data Transform tool: {tool_config['name']}")
        return tool

    @staticmethod
    def _xml_to_dict(element):
        """Convert XML element to dictionary"""
        result = {}
        if element.attrib:
            result.update(element.attrib)
        if element.text and element.text.strip():
            if len(result) == 0:
                return element.text.strip()
            result["_text"] = element.text.strip()
        for child in element:
            child_data = ToolFactory._xml_to_dict(child)
            if child.tag in result:
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(child_data)
            else:
                result[child.tag] = child_data
        return result

    @staticmethod
    def _dict_to_xml(tag, data):
        """Convert dictionary to XML element"""
        import xml.etree.ElementTree as ET
        element = ET.Element(tag)
        if isinstance(data, dict):
            for key, val in data.items():
                if key.startswith("_"):
                    continue
                child = ToolFactory._dict_to_xml(key, val)
                element.append(child)
        elif isinstance(data, list):
            for item in data:
                child = ToolFactory._dict_to_xml("item", item)
                element.append(child)
        else:
            element.text = str(data)
        return element
