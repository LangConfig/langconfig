# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Agent Configuration Schema V2

This module defines the V2 schema for agent configurations with unified tool structure.

Key Changes from V1:
- Consolidates separate tool arrays (native_tools, cli_tools, custom_tools, mcp_tools)
  into a single ToolConfig object
- Adds schema versioning for future migrations
- Provides backward compatibility utilities for v1 configs
- Enhanced validation and type safety

Migration Path:
- V1 configs are automatically normalized on load
- V2 configs are always saved in the new format
- Both formats supported during transition period
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Tool Configuration (V2 Schema)
# =============================================================================

class ToolConfig(BaseModel):
    """
    Unified tool configuration structure.

    Consolidates all tool types into a single, well-structured object
    for better organization and validation.
    """
    native: List[str] = Field(
        default_factory=list,
        description="Built-in native tools (e.g., 'file_read', 'web_search')"
    )
    cli: List[str] = Field(
        default_factory=list,
        description="CLI tool categories (e.g., 'git', 'docker')"
    )
    custom: List[str] = Field(
        default_factory=list,
        description="User-created custom tool IDs"
    )
    mcp: List[str] = Field(
        default_factory=list,
        description="Legacy MCP tools (deprecated, auto-migrated to native)"
    )

    @field_validator('native', 'cli', 'custom', 'mcp')
    @classmethod
    def validate_tool_lists(cls, v):
        """Ensure all tool lists contain only strings."""
        if not isinstance(v, list):
            raise ValueError(f"Tool list must be a list, got {type(v).__name__}")
        for item in v:
            if not isinstance(item, str):
                raise ValueError(f"Tool items must be strings, found {type(item).__name__}")
        return v

    def get_all_tools(self) -> List[str]:
        """Get all tools across all categories."""
        return self.native + self.cli + self.custom + self.mcp

    def has_tools(self) -> bool:
        """Check if any tools are configured."""
        return len(self.get_all_tools()) > 0

    def to_v1_format(self) -> Dict[str, List[str]]:
        """Convert to V1 format with separate arrays."""
        return {
            "native_tools": self.native,
            "cli_tools": self.cli,
            "custom_tools": self.custom,
            "mcp_tools": self.mcp
        }

    @classmethod
    def from_v1_format(
        cls,
        native_tools: Optional[List[str]] = None,
        cli_tools: Optional[List[str]] = None,
        custom_tools: Optional[List[str]] = None,
        mcp_tools: Optional[List[str]] = None
    ) -> "ToolConfig":
        """Create from V1 separate arrays."""
        return cls(
            native=native_tools or [],
            cli=cli_tools or [],
            custom=custom_tools or [],
            mcp=mcp_tools or []
        )


# =============================================================================
# Agent Configuration V2
# =============================================================================

class AgentConfigV2(BaseModel):
    """
    Agent Configuration Schema V2.

    Enhanced configuration with unified tool structure and better validation.
    """
    # Schema version for future migrations
    config_schema_version: int = Field(
        default=2,
        description="Configuration schema version"
    )

    # Base agent settings
    model: str = Field(
        default="claude-haiku-4-5-20251015",
        description="LLM model identifier"
    )
    temperature: float = Field(
        default=0.5,
        ge=0.0,
        le=2.0,
        description="Generation temperature"
    )
    max_tokens: Optional[int] = Field(
        default=30000,
        ge=1,
        le=500000,
        description="Maximum tokens to generate"
    )
    system_prompt: str = Field(
        default="You are a helpful AI assistant.",
        description="Agent system prompt"
    )

    # Unified tool configuration
    tools: ToolConfig = Field(
        default_factory=ToolConfig,
        description="Unified tool configuration"
    )

    # Execution configuration
    streaming: bool = Field(
        default=False,
        description="Enable streaming responses"
    )
    enable_parallel_tools: bool = Field(
        default=True,
        description="Enable parallel tool execution"
    )
    enable_memory: bool = Field(
        default=False,
        description="Enable agent memory"
    )
    long_term_memory: bool = Field(
        default=False,
        description="Enable long-term memory storage"
    )

    # Model routing (opt-in)
    enable_model_routing: bool = Field(
        default=False,
        description="Enable dynamic model routing based on task complexity"
    )
    routing_strategy: Optional[str] = Field(
        default="balanced",
        description="Routing strategy: cost_optimized, performance_optimized, balanced, adaptive"
    )

    # Middleware & hooks
    middleware: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Middleware configurations"
    )
    enable_default_middleware: bool = Field(
        default=True,
        description="Enable default middleware stack"
    )

    # Structured output
    enable_structured_output: bool = Field(
        default=False,
        description="Enable structured output mode"
    )
    output_schema: Optional[Any] = Field(
        default=None,
        description="Output schema for structured responses"
    )
    output_schema_name: Optional[str] = Field(
        default=None,
        description="Named output schema reference"
    )

    # HITL (Human-in-the-Loop)
    interrupt_before: Optional[List[str]] = Field(
        default=None,
        description="Node names to interrupt before execution"
    )
    interrupt_after: Optional[List[str]] = Field(
        default=None,
        description="Node names to interrupt after execution"
    )

    # Multimodal input configuration
    enable_multimodal_input: bool = Field(
        default=False,
        description="Enable multimodal input (images, documents, videos)"
    )
    supported_input_types: List[str] = Field(
        default_factory=lambda: ["image"],
        description="Supported input types: image, document, video, audio"
    )
    attachments: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Pre-configured attachments for this agent (URL or base64)"
    )

    # Fallback configuration
    fallback_models: List[str] = Field(
        default_factory=list,
        description="Fallback model identifiers"
    )

    # Additional custom configuration
    custom_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional custom configuration options"
    )

    @field_validator('temperature')
    @classmethod
    def validate_temperature(cls, v):
        """Validate temperature is within bounds."""
        if not (0.0 <= v <= 2.0):
            raise ValueError(f"temperature must be between 0.0 and 2.0, got {v}")
        return v

    @field_validator('max_tokens')
    @classmethod
    def validate_max_tokens(cls, v):
        """Validate max_tokens is reasonable."""
        if v is not None and not (1 <= v <= 500000):
            raise ValueError(f"max_tokens must be between 1 and 500000, got {v}")
        return v

    @field_validator('enable_structured_output')
    @classmethod
    def validate_structured_output_compatibility(cls, v, info):
        """Ensure structured output and tools aren't both enabled."""
        # This will be checked in full validation after all fields are set
        return v

    def model_post_init(self, __context):
        """Post-initialization validation."""
        # Check mutual exclusivity of structured output and tools
        if self.enable_structured_output and self.tools.has_tools():
            logger.warning(
                "Structured output and tools are mutually exclusive. "
                "Disabling structured output in favor of tools."
            )
            self.enable_structured_output = False


# =============================================================================
# Migration Utilities
# =============================================================================

def normalize_agent_config_v1_to_v2(v1_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a V1 config to V2 format.

    Args:
        v1_config: V1 configuration dictionary

    Returns:
        V2 configuration dictionary
    """
    # If already V2, return as-is
    if v1_config.get("config_schema_version") == 2:
        return v1_config

    v2_config = v1_config.copy()

    # Consolidate tool arrays into ToolConfig
    tool_config = ToolConfig.from_v1_format(
        native_tools=v1_config.get("native_tools", []),
        cli_tools=v1_config.get("cli_tools", []),
        custom_tools=v1_config.get("custom_tools", []),
        mcp_tools=v1_config.get("mcp_tools", [])
    )

    # Remove old tool fields
    for old_field in ["native_tools", "cli_tools", "custom_tools", "mcp_tools", "tools"]:
        v2_config.pop(old_field, None)

    # Add new tool config
    v2_config["tools"] = tool_config.model_dump()

    # Set schema version
    v2_config["config_schema_version"] = 2

    logger.debug(f"Migrated config from V1 to V2: {len(tool_config.get_all_tools())} tools consolidated")

    return v2_config


def normalize_agent_config_v2_to_v1(v2_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a V2 config back to V1 format for backward compatibility.

    Args:
        v2_config: V2 configuration dictionary

    Returns:
        V1 configuration dictionary
    """
    v1_config = v2_config.copy()

    # Extract tool config
    tools = v2_config.get("tools", {})
    if isinstance(tools, dict):
        v1_config["native_tools"] = tools.get("native", [])
        v1_config["cli_tools"] = tools.get("cli", [])
        v1_config["custom_tools"] = tools.get("custom", [])
        v1_config["mcp_tools"] = tools.get("mcp", [])
    else:
        # Tools might be a ToolConfig instance
        if hasattr(tools, 'to_v1_format'):
            v1_format = tools.to_v1_format()
            v1_config.update(v1_format)

    # Remove V2-specific fields
    v1_config.pop("tools", None)
    v1_config.pop("config_schema_version", None)
    v1_config.pop("routing_strategy", None)

    logger.debug("Converted config from V2 to V1 format for backward compatibility")

    return v1_config


def ensure_config_v2(config: Dict[str, Any]) -> AgentConfigV2:
    """
    Ensure a configuration is in V2 format and return as AgentConfigV2 instance.

    Args:
        config: Configuration dictionary (V1 or V2)

    Returns:
        AgentConfigV2 instance
    """
    # Normalize to V2 if needed
    v2_dict = normalize_agent_config_v1_to_v2(config)

    # Create and validate AgentConfigV2 instance
    try:
        return AgentConfigV2(**v2_dict)
    except Exception as e:
        logger.error(f"Failed to create AgentConfigV2 from config: {e}")
        raise ValueError(f"Invalid agent configuration: {e}")


# =============================================================================
# Backward Compatibility Helper
# =============================================================================

class ConfigNormalizer:
    """
    Helper class for normalizing agent configurations across schema versions.

    Usage:
        normalizer = ConfigNormalizer()
        v2_config = normalizer.normalize(raw_config)
    """

    @staticmethod
    def normalize(config: Dict[str, Any], target_version: int = 2) -> Dict[str, Any]:
        """
        Normalize configuration to target version.

        Args:
            config: Raw configuration dictionary
            target_version: Target schema version (default: 2)

        Returns:
            Normalized configuration
        """
        current_version = config.get("config_schema_version", 1)

        if current_version == target_version:
            return config

        if target_version == 2:
            return normalize_agent_config_v1_to_v2(config)
        elif target_version == 1:
            return normalize_agent_config_v2_to_v1(config)
        else:
            raise ValueError(f"Unsupported target version: {target_version}")

    @staticmethod
    def detect_version(config: Dict[str, Any]) -> int:
        """
        Detect configuration schema version.

        Args:
            config: Configuration dictionary

        Returns:
            Detected schema version (1 or 2)
        """
        # Explicit version field
        if "config_schema_version" in config:
            return config["config_schema_version"]

        # Detect by structure: V2 has "tools" as dict, V1 has separate arrays
        if "tools" in config and isinstance(config["tools"], dict):
            return 2

        # Default to V1
        return 1
