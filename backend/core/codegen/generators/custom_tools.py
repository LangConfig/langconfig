# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Custom tool generators for the Executable Workflow Exporter.

Generates custom tool implementations defined by users.
"""

import logging
from textwrap import dedent
from typing import Any, Dict, Set

logger = logging.getLogger(__name__)


class CustomToolGenerators:
    """Generators for custom tool implementations."""

    @staticmethod
    def generate_api_tool(safe_name: str, name: str, description: str, config: Dict) -> str:
        """Generate an API request tool."""
        url = config.get("url", "https://example.com/api")
        method = config.get("method", "GET")
        headers = config.get("headers", {})

        return dedent(f'''
            async def {safe_name}_func(input_str: str) -> str:
                """{description}"""
                import httpx

                try:
                    async with httpx.AsyncClient(timeout=30) as client:
                        response = await client.request(
                            method="{method}",
                            url="{url}",
                            headers={repr(headers)},
                            json={{"input": input_str}} if "{method}" in ("POST", "PUT") else None,
                            params={{"q": input_str}} if "{method}" == "GET" else None
                        )
                        response.raise_for_status()
                        return response.text
                except Exception as e:
                    return f"API error: {{str(e)}}"

            {safe_name}_tool = StructuredTool.from_function(
                func={safe_name}_func,
                name="{name}",
                description="{description}",
                coroutine={safe_name}_func
            )
        ''').strip()

    @staticmethod
    def generate_code_tool(safe_name: str, name: str, description: str, config: Dict) -> str:
        """Generate a code execution tool."""
        code = config.get("code", "return input_str")

        return dedent(f'''
            def {safe_name}_func(input_str: str) -> str:
                """{description}"""
                try:
                    # User-defined code
                    {code}
                except Exception as e:
                    return f"Execution error: {{str(e)}}"

            {safe_name}_tool = StructuredTool.from_function(
                func={safe_name}_func,
                name="{name}",
                description="{description}"
            )
        ''').strip()

    @staticmethod
    def generate_image_video_tool(safe_name: str, name: str, description: str, config: Dict) -> str:
        """Generate an image/video generation tool (Gemini, DALL-E, etc.)."""
        provider = config.get("provider", "google")
        model = config.get("model", "gemini-3-pro-image-preview")
        timeout = config.get("timeout", 60)

        if provider == "google":
            return dedent(f'''
                from contextvars import ContextVar
                from typing import Optional, List, Dict, Any

                _{safe_name}_artifacts: ContextVar[List[Dict[str, Any]]] = ContextVar('{safe_name}_artifacts', default=[])

                def get_{safe_name}_artifacts() -> List[Dict[str, Any]]:
                    """Get and clear pending artifacts from image generation."""
                    artifacts = _{safe_name}_artifacts.get()
                    _{safe_name}_artifacts.set([])
                    return artifacts

                async def {safe_name}_func(
                    prompt: str,
                    aspect_ratio: Optional[str] = "1:1",
                    style: Optional[str] = None
                ) -> str:
                    """{description}

                    Args:
                        prompt: Description of the image to generate
                        aspect_ratio: Image aspect ratio (1:1, 16:9, 9:16, 4:3, 3:4)
                        style: Optional style modifier (vivid, natural, photorealistic)

                    Returns:
                        Success message (image stored as artifact for UI display)
                    """
                    import httpx
                    import os

                    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
                    if not api_key:
                        return "Error: GEMINI_API_KEY or GOOGLE_API_KEY not set in environment"

                    model = "{model}"
                    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{{model}}:generateContent"

                    enhanced_prompt = prompt
                    if style:
                        enhanced_prompt = f"{{prompt}}, {{style}} style"

                    payload = {{
                        "contents": [{{
                            "parts": [{{"text": enhanced_prompt}}]
                        }}],
                        "generationConfig": {{
                            "responseModalities": ["TEXT", "IMAGE"],
                            "temperature": 0.4,
                            "candidateCount": 1,
                            "maxOutputTokens": 8192,
                        }}
                    }}

                    try:
                        async with httpx.AsyncClient(timeout={timeout}) as client:
                            response = await client.post(
                                f"{{endpoint}}?key={{api_key}}",
                                json=payload,
                                headers={{"Content-Type": "application/json"}}
                            )
                            response.raise_for_status()
                            data = response.json()

                            if data.get("candidates"):
                                parts = data["candidates"][0].get("content", {{}}).get("parts", [])
                                for part in parts:
                                    if "inlineData" in part:
                                        img_data = part["inlineData"]["data"]
                                        mime_type = part["inlineData"]["mimeType"]
                                        img_size_kb = len(img_data) * 3 // 4 // 1024

                                        current = _{safe_name}_artifacts.get()
                                        _{safe_name}_artifacts.set(current + [{{
                                            "type": "image",
                                            "data": img_data,
                                            "mimeType": mime_type
                                        }}])

                                        return f"Image generated successfully ({{img_size_kb}}KB). The image has been created and is displayed to the user."

                            return "Error: No image in response"

                    except httpx.HTTPStatusError as e:
                        return f"API error: {{e.response.status_code}}"
                    except Exception as e:
                        return f"Error: {{str(e)}}"

                {safe_name}_tool = StructuredTool.from_function(
                    coroutine={safe_name}_func,
                    name="{name}",
                    description="{description}"
                )
            ''').strip()

        elif provider == "openai":
            return dedent(f'''
                async def {safe_name}_func(
                    prompt: str,
                    size: str = "1024x1024",
                    quality: str = "standard"
                ) -> str:
                    """{description}

                    Args:
                        prompt: Description of the image to generate
                        size: Image size (1024x1024, 1792x1024, 1024x1792)
                        quality: Image quality (standard, hd)

                    Returns:
                        URL of the generated image
                    """
                    import httpx
                    import os

                    api_key = os.getenv("OPENAI_API_KEY")
                    if not api_key:
                        return "Error: OPENAI_API_KEY not set in environment"

                    try:
                        async with httpx.AsyncClient(timeout={timeout}) as client:
                            response = await client.post(
                                "https://api.openai.com/v1/images/generations",
                                headers={{
                                    "Authorization": f"Bearer {{api_key}}",
                                    "Content-Type": "application/json"
                                }},
                                json={{
                                    "model": "dall-e-3",
                                    "prompt": prompt,
                                    "n": 1,
                                    "size": size,
                                    "quality": quality
                                }}
                            )
                            response.raise_for_status()
                            data = response.json()

                            if data.get("data") and len(data["data"]) > 0:
                                image_url = data["data"][0].get("url")
                                return f"Image generated successfully: {{image_url}}"

                            return "Error: No image in response"

                    except httpx.HTTPStatusError as e:
                        return f"API error: {{e.response.status_code}}"
                    except Exception as e:
                        return f"Error: {{str(e)}}"

                {safe_name}_tool = StructuredTool.from_function(
                    coroutine={safe_name}_func,
                    name="{name}",
                    description="{description}"
                )
            ''').strip()

        else:
            return dedent(f'''
                async def {safe_name}_func(prompt: str) -> str:
                    """{description}"""
                    return f"Image generation not implemented for provider: {provider}"

                {safe_name}_tool = StructuredTool.from_function(
                    coroutine={safe_name}_func,
                    name="{name}",
                    description="{description}"
                )
            ''').strip()

    @staticmethod
    def generate_notification_tool(safe_name: str, name: str, description: str, config: Dict) -> str:
        """Generate a notification tool (Slack, Discord, etc.)."""
        provider = config.get("provider", "discord")
        webhook_url = config.get("webhook_url", "")

        if provider == "discord":
            return dedent(f'''
                async def {safe_name}_func(message: str, username: str = "Workflow Bot") -> str:
                    """{description}

                    Args:
                        message: The message to send
                        username: Bot username to display

                    Returns:
                        Success or error message
                    """
                    import httpx
                    import os

                    webhook_url = os.getenv("DISCORD_WEBHOOK_URL") or "{webhook_url}"
                    if not webhook_url:
                        return "Error: DISCORD_WEBHOOK_URL not configured"

                    try:
                        async with httpx.AsyncClient(timeout=30) as client:
                            response = await client.post(
                                webhook_url,
                                json={{"content": message, "username": username}}
                            )
                            response.raise_for_status()
                            return "Message sent successfully to Discord"
                    except Exception as e:
                        return f"Discord error: {{str(e)}}"

                {safe_name}_tool = StructuredTool.from_function(
                    coroutine={safe_name}_func,
                    name="{name}",
                    description="{description}"
                )
            ''').strip()

        elif provider == "slack":
            return dedent(f'''
                async def {safe_name}_func(message: str, channel: str = "#general") -> str:
                    """{description}

                    Args:
                        message: The message to send
                        channel: Slack channel to post to

                    Returns:
                        Success or error message
                    """
                    import httpx
                    import os

                    webhook_url = os.getenv("SLACK_WEBHOOK_URL") or "{webhook_url}"
                    if not webhook_url:
                        return "Error: SLACK_WEBHOOK_URL not configured"

                    try:
                        async with httpx.AsyncClient(timeout=30) as client:
                            response = await client.post(
                                webhook_url,
                                json={{"text": message, "channel": channel}}
                            )
                            response.raise_for_status()
                            return "Message sent successfully to Slack"
                    except Exception as e:
                        return f"Slack error: {{str(e)}}"

                {safe_name}_tool = StructuredTool.from_function(
                    coroutine={safe_name}_func,
                    name="{name}",
                    description="{description}"
                )
            ''').strip()

        else:
            return dedent(f'''
                async def {safe_name}_func(message: str) -> str:
                    """{description}"""
                    return f"Notification not implemented for provider: {provider}"

                {safe_name}_tool = StructuredTool.from_function(
                    coroutine={safe_name}_func,
                    name="{name}",
                    description="{description}"
                )
            ''').strip()

    @staticmethod
    def generate_default_tool(safe_name: str, name: str, description: str) -> str:
        """Generate a default placeholder tool."""
        return dedent(f'''
            def {safe_name}_func(input_str: str) -> str:
                """{description}"""
                # TODO: Implement custom logic
                return f"Custom tool '{name}' executed with input: {{input_str}}"

            {safe_name}_tool = StructuredTool.from_function(
                func={safe_name}_func,
                name="{name}",
                description="{description}"
            )
        ''').strip()

    @staticmethod
    def generate_custom_tool_code(custom_tool, sanitize_name_func) -> str:
        """Generate code for a single custom tool."""
        safe_name = sanitize_name_func(custom_tool.tool_id)
        name = custom_tool.name
        description = custom_tool.description or "Custom tool"
        impl_config = custom_tool.implementation_config or {}

        # Generate based on tool type
        tool_type = custom_tool.tool_type.value if hasattr(custom_tool.tool_type, "value") else str(custom_tool.tool_type)

        if tool_type == "api_request":
            return CustomToolGenerators.generate_api_tool(safe_name, name, description, impl_config)
        elif tool_type == "code_execution":
            return CustomToolGenerators.generate_code_tool(safe_name, name, description, impl_config)
        elif tool_type == "image_video":
            return CustomToolGenerators.generate_image_video_tool(safe_name, name, description, impl_config)
        elif tool_type == "notification":
            return CustomToolGenerators.generate_notification_tool(safe_name, name, description, impl_config)
        else:
            return CustomToolGenerators.generate_default_tool(safe_name, name, description)

    @staticmethod
    async def generate_custom_tools_module(
        used_custom_tools: Set[str],
        sanitize_name_func
    ) -> str:
        """
        Generate tools/custom.py with custom tool implementations.

        Args:
            used_custom_tools: Set of custom tool IDs used in the workflow
            sanitize_name_func: Function to sanitize tool names
        """
        custom_tool_code = []

        if used_custom_tools:
            try:
                from db.database import SessionLocal
                from models.custom_tool import CustomTool

                db = SessionLocal()
                try:
                    for tool_id in used_custom_tools:
                        custom_tool = db.query(CustomTool).filter(
                            CustomTool.tool_id == tool_id
                        ).first()

                        if custom_tool:
                            code = CustomToolGenerators.generate_custom_tool_code(
                                custom_tool, sanitize_name_func
                            )
                            custom_tool_code.append(code)
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"Failed to fetch custom tools: {e}")

        tools_code = "\n\n\n".join(custom_tool_code) if custom_tool_code else "# No custom tools"

        # Build registry
        registry_entries = []
        for tool_id in used_custom_tools:
            safe_name = sanitize_name_func(tool_id)
            registry_entries.append(f'    "{tool_id}": {safe_name}_tool,')
        registry_str = "\n".join(registry_entries) if registry_entries else "    # No tools"

        header = '''"""Custom tools defined by the user."""

import logging
from langchain_core.tools import StructuredTool

logger = logging.getLogger(__name__)


'''
        footer = f'''


# Custom tool registry
CUSTOM_TOOLS = {{
{registry_str}
}}
'''
        return header + tools_code + footer
