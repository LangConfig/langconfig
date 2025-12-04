# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
LangChain v1.0 Middleware Presets

Provides pre-configured middleware stacks for different use cases.
Makes it easy for users to select appropriate middleware without deep knowledge.

Preset Categories:
- Development: Verbose logging, debugging tools
- Production: Performance, cost tracking, security
- Secure: PII redaction, validation, HITL gates
- Cost-Optimized: Minimal middleware, caching, summarization
- Research: Web access, reasoning traces, extensive logging
"""

from typing import Dict, List, Any
from enum import Enum


class MiddlewarePreset(str, Enum):
    """Available middleware presets."""
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    SECURE = "secure"
    COST_OPTIMIZED = "cost_optimized"
    RESEARCH = "research"
    MINIMAL = "minimal"
    CUSTOM = "custom"


# =============================================================================
# Preset Configurations
# =============================================================================

PRESET_CONFIGS: Dict[str, Dict[str, Any]] = {
    "development": {
        "name": "Development Mode",
        "description": "Verbose logging and debugging for development",
        "icon": "🔧",
        "recommended_for": ["Local development", "Debugging", "Testing new features"],
        "middleware": [
            {"type": "timestamp", "timezone": "UTC"},
            {"type": "project_context"},
            {"type": "logging", "log_inputs": True, "log_outputs": True, "max_log_length": 1000},
            {"type": "validation", "min_length": 10},
        ],
        "enable_default_middleware": True,
        "performance_impact": "Low",
        "cost_impact": "None",
    },

    "production": {
        "name": "Production Mode",
        "description": "Balanced performance, monitoring, and cost tracking",
        "icon": "🚀",
        "recommended_for": ["Production deployments", "Live user traffic", "Mission-critical workflows"],
        "middleware": [
            {"type": "timestamp"},
            {"type": "project_context"},
            {"type": "logging", "log_inputs": False, "log_outputs": True, "max_log_length": 500},
            {"type": "cost_tracking"},
            {"type": "validation", "min_length": 10, "max_length": 10000},
            {"type": "tool_retry", "max_retries": 2, "backoff_factor": 1.5},
        ],
        "enable_default_middleware": False,  # Custom stack
        "performance_impact": "Low",
        "cost_impact": "Minimal (cost tracking)",
    },

    "secure": {
        "name": "Secure Mode",
        "description": "Maximum security with PII redaction and human approval",
        "icon": "🔒",
        "recommended_for": ["Handling sensitive data", "Healthcare/Finance", "Compliance requirements"],
        "middleware": [
            {"type": "timestamp"},
            {"type": "pii", "patterns": ["email", "phone", "ssn", "credit_card", "api_key"], "replacement": "[REDACTED]"},
            {"type": "validation", "prohibited_patterns": ["DELETE FROM", "DROP TABLE", "rm -rf", "os.system"]},
            {"type": "hitl", "interrupt_on": {"send_email": True, "delete_file": True, "execute_code": True, "make_payment": True}},
            {"type": "logging", "log_inputs": True, "log_outputs": True},
        ],
        "enable_default_middleware": False,
        "performance_impact": "Medium (PII scanning)",
        "cost_impact": "None",
    },

    "cost_optimized": {
        "name": "Cost-Optimized Mode",
        "description": "Minimize costs with summarization and efficient middleware",
        "icon": "💰",
        "recommended_for": ["High-volume workflows", "Budget constraints", "Long conversations"],
        "middleware": [
            {"type": "timestamp"},
            {"type": "summarization", "model": "gpt-4o-mini", "max_tokens_before_summary": 800, "keep_last_n_messages": 3},
            {"type": "cost_tracking"},
            {"type": "logging", "log_inputs": False, "log_outputs": False},  # Minimal logging
        ],
        "enable_default_middleware": False,
        "performance_impact": "Medium (summarization)",
        "cost_impact": "Reduced 30-50% on long conversations",
    },

    "research": {
        "name": "Research Mode",
        "description": "Extensive logging, reasoning traces, and tool monitoring",
        "icon": "🔬",
        "recommended_for": ["Research projects", "Academic work", "Complex analysis"],
        "middleware": [
            {"type": "timestamp"},
            {"type": "project_context"},
            {"type": "logging", "log_inputs": True, "log_outputs": True, "max_log_length": 2000},
            {"type": "validation", "min_length": 50},  # Expect detailed responses
            {"type": "tool_retry", "max_retries": 3, "backoff_factor": 2.0},
        ],
        "enable_default_middleware": True,
        "performance_impact": "Low",
        "cost_impact": "None",
    },

    "minimal": {
        "name": "Minimal Mode",
        "description": "Bare minimum middleware for maximum performance",
        "icon": "⚡",
        "recommended_for": ["High-performance needs", "Simple workflows", "Benchmarking"],
        "middleware": [],
        "enable_default_middleware": False,
        "performance_impact": "None",
        "cost_impact": "None",
    },
}


# =============================================================================
# Individual Middleware Metadata
# =============================================================================

MIDDLEWARE_CATALOG: Dict[str, Dict[str, Any]] = {
    "timestamp": {
        "name": "Timestamp",
        "description": "Inject current time into agent context",
        "icon": "🕐",
        "category": "Context",
        "configurable": True,
        "fields": [
            {
                "name": "timezone",
                "type": "select",
                "options": ["UTC", "EST", "PST", "CST", "MST"],
                "default": "UTC",
                "description": "Timezone for timestamp"
            },
            {
                "name": "format",
                "type": "text",
                "default": "%Y-%m-%d %H:%M:%S",
                "description": "Python strftime format"
            }
        ],
        "performance_impact": "Negligible",
        "cost_impact": "None",
    },

    "project_context": {
        "name": "Project Context",
        "description": "Add project/task metadata to context",
        "icon": "📁",
        "category": "Context",
        "configurable": False,
        "fields": [],
        "performance_impact": "Negligible",
        "cost_impact": "None",
    },

    "pii": {
        "name": "PII Redaction",
        "description": "Automatically redact sensitive information",
        "icon": "🔒",
        "category": "Security",
        "configurable": True,
        "fields": [
            {
                "name": "patterns",
                "type": "multiselect",
                "options": [
                    {"label": "Email Addresses", "value": "email"},
                    {"label": "Phone Numbers", "value": "phone"},
                    {"label": "SSN", "value": "ssn"},
                    {"label": "Credit Cards", "value": "credit_card"},
                    {"label": "API Keys", "value": "api_key"},
                    {"label": "IP Addresses", "value": "ip_address"},
                    {"label": "URLs with Tokens", "value": "url_token"},
                    {"label": "Passwords", "value": "password"},
                ],
                "default": ["email", "phone"],
                "description": "PII patterns to detect and redact"
            },
            {
                "name": "replacement",
                "type": "text",
                "default": "[REDACTED]",
                "description": "Replacement text for redacted PII"
            },
            {
                "name": "store_mappings",
                "type": "boolean",
                "default": False,
                "description": "Store redaction mappings for restoration"
            }
        ],
        "performance_impact": "Low (regex matching)",
        "cost_impact": "None",
    },

    "summarization": {
        "name": "Conversation Summarization",
        "description": "Auto-summarize long conversations",
        "icon": "📝",
        "category": "Performance",
        "configurable": True,
        "fields": [
            {
                "name": "model",
                "type": "select",
                "options": ["gpt-4o-mini", "gpt-4o", "claude-3-5-haiku-20241022"],
                "default": "gpt-4o-mini",
                "description": "Model for summarization (cheaper is better)"
            },
            {
                "name": "max_tokens_before_summary",
                "type": "number",
                "default": 1000,
                "min": 500,
                "max": 5000,
                "description": "Trigger summarization at this token count"
            },
            {
                "name": "keep_last_n_messages",
                "type": "number",
                "default": 5,
                "min": 1,
                "max": 20,
                "description": "Keep recent N messages without summarizing"
            }
        ],
        "performance_impact": "Medium (LLM call for summarization)",
        "cost_impact": "Small cost per summary (~0.01 USD)",
    },

    "hitl": {
        "name": "Human-in-the-Loop",
        "description": "Require approval for sensitive actions",
        "icon": "👤",
        "category": "Safety",
        "configurable": True,
        "fields": [
            {
                "name": "interrupt_on",
                "type": "tags",
                "default": ["send_email", "delete_file"],
                "description": "Tool names requiring approval (comma-separated)"
            },
            {
                "name": "description",
                "type": "text",
                "default": "Human approval required",
                "description": "Message shown to human reviewer"
            }
        ],
        "performance_impact": "None (pauses execution)",
        "cost_impact": "None",
        "requires_checkpointing": True,
    },

    "validation": {
        "name": "Output Validation",
        "description": "Validate model outputs for quality",
        "icon": "✅",
        "category": "Quality",
        "configurable": True,
        "fields": [
            {
                "name": "min_length",
                "type": "number",
                "default": 10,
                "min": 0,
                "max": 10000,
                "description": "Minimum response length"
            },
            {
                "name": "max_length",
                "type": "number",
                "default": None,
                "min": 100,
                "max": 100000,
                "description": "Maximum response length (optional)"
            },
            {
                "name": "prohibited_patterns",
                "type": "tags",
                "default": [],
                "description": "Dangerous patterns to block (comma-separated)"
            },
            {
                "name": "required_patterns",
                "type": "tags",
                "default": [],
                "description": "Required patterns (comma-separated)"
            }
        ],
        "performance_impact": "Negligible",
        "cost_impact": "None",
    },

    "logging": {
        "name": "Logging",
        "description": "Log inputs/outputs for monitoring",
        "icon": "📋",
        "category": "Observability",
        "configurable": True,
        "fields": [
            {
                "name": "log_inputs",
                "type": "boolean",
                "default": True,
                "description": "Log model inputs"
            },
            {
                "name": "log_outputs",
                "type": "boolean",
                "default": True,
                "description": "Log model outputs"
            },
            {
                "name": "max_log_length",
                "type": "number",
                "default": 500,
                "min": 100,
                "max": 5000,
                "description": "Maximum characters to log"
            }
        ],
        "performance_impact": "Negligible",
        "cost_impact": "None",
    },

    "cost_tracking": {
        "name": "Cost Tracking",
        "description": "Track estimated model costs",
        "icon": "💵",
        "category": "Observability",
        "configurable": False,
        "fields": [],
        "performance_impact": "Negligible",
        "cost_impact": "None",
    },

    "tool_retry": {
        "name": "Tool Retry",
        "description": "Automatically retry failed tool calls",
        "icon": "🔄",
        "category": "Reliability",
        "configurable": True,
        "fields": [
            {
                "name": "max_retries",
                "type": "number",
                "default": 3,
                "min": 1,
                "max": 5,
                "description": "Maximum retry attempts"
            },
            {
                "name": "backoff_factor",
                "type": "number",
                "default": 2.0,
                "min": 1.0,
                "max": 5.0,
                "step": 0.5,
                "description": "Exponential backoff multiplier"
            }
        ],
        "performance_impact": "None (only on failures)",
        "cost_impact": "None",
    },
}


# =============================================================================
# Helper Functions
# =============================================================================

def get_preset_config(preset: MiddlewarePreset) -> Dict[str, Any]:
    """
    Get configuration for a preset.

    Args:
        preset: Preset enum value

    Returns:
        Preset configuration dictionary
    """
    return PRESET_CONFIGS.get(preset.value, PRESET_CONFIGS["development"])


def get_all_presets() -> List[Dict[str, Any]]:
    """
    Get all available presets with metadata.

    Returns:
        List of preset configurations
    """
    return [
        {"id": preset_id, **config}
        for preset_id, config in PRESET_CONFIGS.items()
    ]


def get_middleware_catalog() -> Dict[str, Dict[str, Any]]:
    """
    Get catalog of all available middleware with metadata.

    Returns:
        Dictionary mapping middleware type to metadata
    """
    return MIDDLEWARE_CATALOG


def create_middleware_config_from_preset(
    preset: MiddlewarePreset,
    overrides: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Create agent config with middleware from preset, allowing overrides.

    Args:
        preset: Preset to use as base
        overrides: Optional overrides to apply

    Returns:
        Agent config with middleware configuration
    """
    config = get_preset_config(preset)

    result = {
        "middleware": config["middleware"].copy(),
        "enable_default_middleware": config["enable_default_middleware"],
    }

    if overrides:
        result.update(overrides)

    return result


# =============================================================================
# Preset Recommendations
# =============================================================================

def recommend_preset(
    has_sensitive_data: bool = False,
    is_production: bool = False,
    needs_cost_optimization: bool = False,
    is_research: bool = False,
) -> MiddlewarePreset:
    """
    Recommend a preset based on use case characteristics.

    Args:
        has_sensitive_data: Handles PII or sensitive information
        is_production: Running in production environment
        needs_cost_optimization: Budget constraints
        is_research: Research or experimental workflow

    Returns:
        Recommended preset
    """
    if has_sensitive_data:
        return MiddlewarePreset.SECURE
    elif is_production:
        return MiddlewarePreset.PRODUCTION
    elif needs_cost_optimization:
        return MiddlewarePreset.COST_OPTIMIZED
    elif is_research:
        return MiddlewarePreset.RESEARCH
    else:
        return MiddlewarePreset.DEVELOPMENT
