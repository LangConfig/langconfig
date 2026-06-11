# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Model Registry

Central registry for tracking model capabilities, costs, and performance characteristics.

This registry is used by the dynamic model routing system to select appropriate models
based on task requirements and optimization strategies.

Usage:
    from core.models.registry import model_registry

    # Check if model supports a feature
    if model_registry.supports_feature("claude-opus-4-8", "streaming"):
        ...

    # Find best model for requirements
    model = model_registry.find_best_model(
        requirements={"streaming": True, "tools": True},
        strategy="cost_optimized"
    )

    # Get model cost
    cost = model_registry.get_model_cost("gpt-5.4", input_tokens, output_tokens)

The registry is the single source of truth for model pricing. Legacy entries
(legacy=True) keep pricing/display data so historical execution costs stay
resolvable, but are excluded from routing/selection.
"""

from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Model Capability Enums
# =============================================================================

class ModelCapability(str, Enum):
    """Supported model capabilities."""
    STREAMING = "streaming"
    TOOLS = "tools"
    STRUCTURED_OUTPUT = "structured_output"
    FUNCTION_CALLING = "function_calling"
    PARALLEL_TOOLS = "parallel_tools"
    VISION = "vision"
    AUDIO = "audio"
    IMAGE_GENERATION = "image_generation"
    REASONING = "reasoning"  # Advanced reasoning like o1


class ModelProvider(str, Enum):
    """Model providers."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    LOCAL = "local"


# =============================================================================
# Model Information Dataclass
# =============================================================================

@dataclass
class ModelInfo:
    """
    Comprehensive information about an LLM model.

    Attributes:
        model_id: Unique model identifier
        provider: Model provider
        display_name: Human-readable name
        capabilities: Set of supported capabilities
        max_context_tokens: Maximum context window size
        max_output_tokens: Maximum output tokens
        cost_per_1m_input: Cost per 1M input tokens (USD)
        cost_per_1m_output: Cost per 1M output tokens (USD)
        speed_rating: Relative speed (1=slowest, 5=fastest)
        quality_rating: Relative quality (1=lowest, 5=highest)
        notes: Additional notes or limitations
        legacy: Retired/deprecated model kept only so historical executions
            can still resolve pricing and display names; excluded from routing
    """
    model_id: str
    provider: ModelProvider
    display_name: str
    capabilities: Set[ModelCapability] = field(default_factory=set)
    max_context_tokens: int = 200000
    max_output_tokens: int = 8192
    cost_per_1m_input: float = 0.0
    cost_per_1m_output: float = 0.0
    speed_rating: int = 3  # 1-5
    quality_rating: int = 3  # 1-5
    notes: str = ""
    legacy: bool = False

    def supports(self, capability: ModelCapability) -> bool:
        """Check if model supports a capability."""
        return capability in self.capabilities

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for given token counts."""
        input_cost = (input_tokens / 1_000_000) * self.cost_per_1m_input
        output_cost = (output_tokens / 1_000_000) * self.cost_per_1m_output
        return input_cost + output_cost


# =============================================================================
# Model Registry
# =============================================================================

class ModelRegistry:
    """
    Central registry for model information and capabilities.

    Provides querying, filtering, and selection logic for models based on
    requirements and optimization strategies.
    """

    def __init__(self):
        """Initialize registry with known models."""
        self._models: Dict[str, ModelInfo] = {}
        self._initialize_registry()

    def _initialize_registry(self):
        """Populate registry with known models."""

        # Claude current generation (Anthropic)
        self.register(ModelInfo(
            model_id="claude-fable-5",
            provider=ModelProvider.ANTHROPIC,
            display_name="Claude Fable 5",
            capabilities={
                ModelCapability.STREAMING,
                ModelCapability.TOOLS,
                ModelCapability.STRUCTURED_OUTPUT,
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.PARALLEL_TOOLS,
                ModelCapability.VISION,
                ModelCapability.REASONING
            },
            max_context_tokens=1000000,
            max_output_tokens=128000,
            cost_per_1m_input=10.0,
            cost_per_1m_output=50.0,
            speed_rating=2,
            quality_rating=5,
            notes="Anthropic frontier tier above Opus. Rejects temperature/top_p/top_k; thinking is always on"
        ))

        self.register(ModelInfo(
            model_id="claude-opus-4-8",
            provider=ModelProvider.ANTHROPIC,
            display_name="Claude Opus 4.8",
            capabilities={
                ModelCapability.STREAMING,
                ModelCapability.TOOLS,
                ModelCapability.STRUCTURED_OUTPUT,
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.PARALLEL_TOOLS,
                ModelCapability.VISION
            },
            max_context_tokens=1000000,
            max_output_tokens=128000,
            cost_per_1m_input=5.0,
            cost_per_1m_output=25.0,
            speed_rating=3,
            quality_rating=5,
            notes="Highest capability Claude model, best for complex reasoning"
        ))

        self.register(ModelInfo(
            model_id="claude-sonnet-4-6",
            provider=ModelProvider.ANTHROPIC,
            display_name="Claude Sonnet 4.6",
            capabilities={
                ModelCapability.STREAMING,
                ModelCapability.TOOLS,
                ModelCapability.STRUCTURED_OUTPUT,
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.PARALLEL_TOOLS,
                ModelCapability.VISION
            },
            max_context_tokens=1000000,
            max_output_tokens=64000,
            cost_per_1m_input=3.0,
            cost_per_1m_output=15.0,
            speed_rating=4,
            quality_rating=4,
            notes="Balanced Claude model, great for most tasks"
        ))

        self.register(ModelInfo(
            model_id="claude-haiku-4-5",
            provider=ModelProvider.ANTHROPIC,
            display_name="Claude Haiku 4.5",
            capabilities={
                ModelCapability.STREAMING,
                ModelCapability.TOOLS,
                ModelCapability.STRUCTURED_OUTPUT,
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.PARALLEL_TOOLS,
                ModelCapability.VISION
            },
            max_context_tokens=200000,
            max_output_tokens=64000,
            cost_per_1m_input=1.0,
            cost_per_1m_output=5.0,
            speed_rating=5,
            quality_rating=3,
            notes="Fast and cost-effective Claude model"
        ))

        # OpenAI GPT-5 frontier models
        self.register(ModelInfo(
            model_id="gpt-5.5",
            provider=ModelProvider.OPENAI,
            display_name="GPT-5.5",
            capabilities={
                ModelCapability.STREAMING,
                ModelCapability.TOOLS,
                ModelCapability.STRUCTURED_OUTPUT,
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.PARALLEL_TOOLS,
                ModelCapability.VISION,
                ModelCapability.REASONING
            },
            max_context_tokens=1000000,
            max_output_tokens=128000,
            cost_per_1m_input=5.0,
            cost_per_1m_output=30.0,
            speed_rating=3,
            quality_rating=5,
            notes="Latest GPT model with advanced reasoning capabilities"
        ))

        self.register(ModelInfo(
            model_id="gpt-5.4",
            provider=ModelProvider.OPENAI,
            display_name="GPT-5.4",
            capabilities={
                ModelCapability.STREAMING,
                ModelCapability.TOOLS,
                ModelCapability.STRUCTURED_OUTPUT,
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.PARALLEL_TOOLS,
                ModelCapability.VISION
            },
            max_context_tokens=1000000,
            max_output_tokens=128000,
            cost_per_1m_input=2.5,
            cost_per_1m_output=15.0,
            speed_rating=4,
            quality_rating=4,
            notes="Balanced GPT-5.4 model"
        ))

        self.register(ModelInfo(
            model_id="gpt-5.4-mini",
            provider=ModelProvider.OPENAI,
            display_name="GPT-5.4 Mini",
            capabilities={
                ModelCapability.STREAMING,
                ModelCapability.TOOLS,
                ModelCapability.STRUCTURED_OUTPUT,
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.PARALLEL_TOOLS,
                ModelCapability.VISION
            },
            max_context_tokens=400000,
            max_output_tokens=128000,
            cost_per_1m_input=0.75,
            cost_per_1m_output=4.5,
            speed_rating=5,
            quality_rating=4,
            notes="Cost-efficient GPT-5.4 model for subagents and well-scoped tasks"
        ))

        self.register(ModelInfo(
            model_id="gpt-5.4-nano",
            provider=ModelProvider.OPENAI,
            display_name="GPT-5.4 Nano",
            capabilities={
                ModelCapability.STREAMING,
                ModelCapability.TOOLS,
                ModelCapability.STRUCTURED_OUTPUT,
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.PARALLEL_TOOLS,
                ModelCapability.VISION
            },
            max_context_tokens=400000,
            max_output_tokens=128000,
            cost_per_1m_input=0.20,
            cost_per_1m_output=1.25,
            speed_rating=5,
            quality_rating=3,
            notes="Lowest-cost GPT-5.4 model for extraction, routing, and classification"
        ))

        # Google Gemini Models (current)
        self.register(ModelInfo(
            model_id="gemini-3.1-pro-preview",
            provider=ModelProvider.GOOGLE,
            display_name="Gemini 3.1 Pro",
            capabilities={
                ModelCapability.STREAMING,
                ModelCapability.TOOLS,
                ModelCapability.STRUCTURED_OUTPUT,
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.PARALLEL_TOOLS,
                ModelCapability.VISION,
                ModelCapability.REASONING
            },
            max_context_tokens=1048576,
            max_output_tokens=65536,
            cost_per_1m_input=2.0,
            cost_per_1m_output=12.0,
            speed_rating=3,
            quality_rating=5,
            notes="Google's flagship Gemini 3.1 model"
        ))

        self.register(ModelInfo(
            model_id="gemini-2.5-flash",
            provider=ModelProvider.GOOGLE,
            display_name="Gemini 2.5 Flash",
            capabilities={
                ModelCapability.STREAMING,
                ModelCapability.TOOLS,
                ModelCapability.STRUCTURED_OUTPUT,
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.PARALLEL_TOOLS,
                ModelCapability.VISION
            },
            max_context_tokens=1000000,
            max_output_tokens=65536,
            cost_per_1m_input=0.30,
            cost_per_1m_output=2.50,
            speed_rating=5,
            quality_rating=4,
            notes="Fast Gemini workhorse model"
        ))

        self.register(ModelInfo(
            model_id="gemini-2.5-flash-lite",
            provider=ModelProvider.GOOGLE,
            display_name="Gemini 2.5 Flash Lite",
            capabilities={
                ModelCapability.STREAMING,
                ModelCapability.TOOLS,
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.VISION
            },
            max_context_tokens=1000000,
            max_output_tokens=65536,
            cost_per_1m_input=0.10,
            cost_per_1m_output=0.40,
            speed_rating=5,
            quality_rating=3,
            notes="Lowest-cost Gemini model"
        ))

        self._register_legacy_models()

        logger.info(f"✓ Model registry initialized with {len(self._models)} models")

    def _register_legacy_models(self):
        """
        Register retired/deprecated models with legacy=True.

        These keep pricing and display names resolvable for historical
        execution cost views, but are never returned by routing/selection.
        Format: (model_id, provider, display_name, $/1M input, $/1M output)
        """
        legacy_models = [
            # OpenAI
            ("gpt-5.2", ModelProvider.OPENAI, "GPT-5.2", 5.0, 20.0),
            ("gpt-5.1", ModelProvider.OPENAI, "GPT-5.1", 3.0, 12.0),
            ("gpt-5", ModelProvider.OPENAI, "GPT-5", 1.25, 10.0),
            ("gpt-4o", ModelProvider.OPENAI, "GPT-4o", 2.50, 10.0),
            ("gpt-4o-mini", ModelProvider.OPENAI, "GPT-4o Mini", 0.15, 0.60),
            ("o1-preview", ModelProvider.OPENAI, "o1 Preview", 15.0, 60.0),
            ("o1-mini", ModelProvider.OPENAI, "o1 Mini", 3.0, 12.0),
            ("o3", ModelProvider.OPENAI, "o3", 20.0, 80.0),
            ("o3-mini", ModelProvider.OPENAI, "o3 Mini", 4.0, 16.0),
            ("o4-mini", ModelProvider.OPENAI, "o4 Mini", 3.0, 12.0),
            # Anthropic
            ("claude-opus-4-5", ModelProvider.ANTHROPIC, "Claude Opus 4.5", 5.0, 25.0),
            ("claude-sonnet-4-5", ModelProvider.ANTHROPIC, "Claude Sonnet 4.5", 3.0, 15.0),
            ("claude-sonnet-4-5-20250929", ModelProvider.ANTHROPIC, "Claude Sonnet 4.5", 3.0, 15.0),
            ("claude-3-5-sonnet-20241022", ModelProvider.ANTHROPIC, "Claude 3.5 Sonnet", 3.0, 15.0),
            ("claude-3-5-haiku-20241022", ModelProvider.ANTHROPIC, "Claude 3.5 Haiku", 0.80, 4.0),
            ("claude-3-opus-20240229", ModelProvider.ANTHROPIC, "Claude 3 Opus", 15.0, 75.0),
            # Google (gemini-3-pro-preview shut down 2026-03-09; gemini-2.0-flash 2026-06-01)
            ("gemini-3-pro-preview", ModelProvider.GOOGLE, "Gemini 3 Pro", 2.0, 12.0),
            ("gemini-2.5-pro", ModelProvider.GOOGLE, "Gemini 2.5 Pro", 1.25, 5.0),
            ("gemini-2.0-flash", ModelProvider.GOOGLE, "Gemini 2.0 Flash", 0.075, 0.30),
            ("gemini-2.0-flash-exp", ModelProvider.GOOGLE, "Gemini 2.0 Flash Experimental", 0.0, 0.0),
            ("gemini-exp-1206", ModelProvider.GOOGLE, "Gemini Experimental 1206", 0.0, 0.0),
            ("gemini-1.5-pro", ModelProvider.GOOGLE, "Gemini 1.5 Pro", 1.25, 5.0),
            ("gemini-1.5-flash", ModelProvider.GOOGLE, "Gemini 1.5 Flash", 0.075, 0.30),
        ]
        for model_id, provider, display_name, cost_in, cost_out in legacy_models:
            self.register(ModelInfo(
                model_id=model_id,
                provider=provider,
                display_name=display_name,
                capabilities={ModelCapability.STREAMING, ModelCapability.TOOLS},
                cost_per_1m_input=cost_in,
                cost_per_1m_output=cost_out,
                notes="Legacy model kept for historical cost/display resolution",
                legacy=True,
            ))

    def register(self, model: ModelInfo):
        """Register a new model or update existing."""
        self._models[model.model_id] = model
        logger.debug(f"Registered model: {model.model_id} ({model.display_name})")

    def get_model(self, model_id: str) -> Optional[ModelInfo]:
        """Get model information by ID."""
        return self._models.get(model_id)

    def resolve_model_id(self, model_str: str) -> Optional[str]:
        """Resolve a possibly prefixed/decorated model string to a registry ID.

        Tries an exact match first, then falls back to the LONGEST registered
        ID that appears as a substring (so 'openai:gpt-5.4-mini' resolves to
        'gpt-5.4-mini', not 'gpt-5.4'). Returns None when nothing matches.
        """
        model_str = (model_str or "").lower()
        if not model_str:
            return None
        if model_str in self._models:
            return model_str
        matches = [known_id for known_id in self._models if known_id in model_str]
        if not matches:
            return None
        return max(matches, key=len)

    def list_models(self, provider: Optional[ModelProvider] = None) -> List[ModelInfo]:
        """List all models, optionally filtered by provider."""
        models = list(self._models.values())
        if provider:
            models = [m for m in models if m.provider == provider]
        return sorted(models, key=lambda m: m.display_name)

    def supports_feature(self, model_id: str, capability: ModelCapability) -> bool:
        """Check if a model supports a specific capability."""
        model = self.get_model(model_id)
        return model.supports(capability) if model else False

    def find_models_with_capabilities(
        self,
        required_capabilities: Set[ModelCapability],
        provider: Optional[ModelProvider] = None
    ) -> List[ModelInfo]:
        """Find all models that support required capabilities."""
        matching = []
        for model in self._models.values():
            # Legacy models stay resolvable for pricing/display but are never routed to
            if model.legacy:
                continue
            # Check provider filter
            if provider and model.provider != provider:
                continue
            # Check if all required capabilities are supported
            if required_capabilities.issubset(model.capabilities):
                matching.append(model)
        return matching

    def find_best_model(
        self,
        requirements: Dict[str, Any],
        strategy: str = "balanced"
    ) -> Optional[str]:
        """
        Find the best model based on requirements and strategy.

        Args:
            requirements: Dictionary of requirements:
                - streaming: bool
                - tools: bool
                - structured_output: bool
                - vision: bool
                - reasoning: bool
                - min_context_tokens: int
                - max_cost_per_1m_input: float
                - provider: ModelProvider
            strategy: Selection strategy:
                - "cost_optimized": Cheapest model meeting requirements
                - "performance_optimized": Highest quality model
                - "balanced": Best quality/cost ratio
                - "fastest": Fastest model

        Returns:
            Model ID of best match, or None if no model meets requirements
        """
        # Build required capabilities from requirements
        required_caps = set()
        if requirements.get("streaming"):
            required_caps.add(ModelCapability.STREAMING)
        if requirements.get("tools"):
            required_caps.add(ModelCapability.TOOLS)
        if requirements.get("structured_output"):
            required_caps.add(ModelCapability.STRUCTURED_OUTPUT)
        if requirements.get("vision"):
            required_caps.add(ModelCapability.VISION)
        if requirements.get("reasoning"):
            required_caps.add(ModelCapability.REASONING)

        # Find matching models
        provider = requirements.get("provider")
        candidates = self.find_models_with_capabilities(required_caps, provider)

        if not candidates:
            logger.warning(f"No models found matching requirements: {requirements}")
            return None

        # Apply additional filters
        min_context = requirements.get("min_context_tokens", 0)
        candidates = [m for m in candidates if m.max_context_tokens >= min_context]

        max_cost = requirements.get("max_cost_per_1m_input")
        if max_cost:
            candidates = [m for m in candidates if m.cost_per_1m_input <= max_cost]

        if not candidates:
            logger.warning("No models remaining after applying filters")
            return None

        # Select best based on strategy
        if strategy == "cost_optimized":
            # Sort by cost (input + output averaged)
            candidates.sort(key=lambda m: m.cost_per_1m_input + m.cost_per_1m_output)
        elif strategy == "performance_optimized":
            # Sort by quality rating (descending)
            candidates.sort(key=lambda m: m.quality_rating, reverse=True)
        elif strategy == "fastest":
            # Sort by speed rating (descending)
            candidates.sort(key=lambda m: m.speed_rating, reverse=True)
        else:  # balanced
            # Sort by quality/cost ratio
            def score(m):
                avg_cost = (m.cost_per_1m_input + m.cost_per_1m_output) / 2
                if avg_cost == 0:
                    return m.quality_rating * 1000  # Free models get high score
                return m.quality_rating / avg_cost
            candidates.sort(key=score, reverse=True)

        best = candidates[0]
        logger.info(f"Selected model '{best.model_id}' using strategy '{strategy}'")
        return best.model_id

    def get_model_cost(self, model_id: str, input_tokens: int = 0, output_tokens: int = 0) -> Optional[float]:
        """Get estimated cost for a model with given token counts."""
        model = self.get_model(model_id)
        if not model:
            return None
        return model.estimate_cost(input_tokens, output_tokens)

    def get_blended_cost_per_1m(self, model_id: str, default: float = 9.0) -> float:
        """
        Blended (input+output averaged) USD cost per 1M tokens.

        Accepts either an exact registry ID or a prefixed/decorated model
        string (e.g. 'openai:gpt-5.4-mini'), resolved via resolve_model_id.
        Used by consumers that only track a total token count rather than an
        input/output split. Unknown models get the provided default.
        """
        model = self.get_model(model_id)
        if not model:
            resolved = self.resolve_model_id(model_id)
            model = self.get_model(resolved) if resolved else None
        if not model:
            return default
        return (model.cost_per_1m_input + model.cost_per_1m_output) / 2

    def get_blended_cost_per_1k(self, model_id: str, default: float = 0.009) -> float:
        """Blended USD cost per 1K tokens (see get_blended_cost_per_1m)."""
        return self.get_blended_cost_per_1m(model_id, default * 1000) / 1000


# =============================================================================
# Global Registry Instance
# =============================================================================

# Singleton instance
model_registry = ModelRegistry()


# =============================================================================
# Utility Functions
# =============================================================================

def get_supported_models() -> List[str]:
    """Get list of all supported model IDs."""
    return list(model_registry._models.keys())


def is_model_supported(model_id: str) -> bool:
    """Check if a model is supported."""
    return model_id in model_registry._models


def get_model_capabilities(model_id: str) -> Set[ModelCapability]:
    """Get capabilities for a model."""
    model = model_registry.get_model(model_id)
    return model.capabilities if model else set()
