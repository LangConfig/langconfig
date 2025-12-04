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
    if model_registry.supports_feature("claude-opus-4-5-20250514", "streaming"):
        ...

    # Find best model for requirements
    model = model_registry.find_best_model(
        requirements={"streaming": True, "tools": True},
        strategy="cost_optimized"
    )

    # Get model cost
    cost = model_registry.get_model_cost("gpt-5-turbo")
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

        # Claude 4.x Models (Anthropic)
        self.register(ModelInfo(
            model_id="claude-opus-4-5-20250514",
            provider=ModelProvider.ANTHROPIC,
            display_name="Claude Opus 4.5",
            capabilities={
                ModelCapability.STREAMING,
                ModelCapability.TOOLS,
                ModelCapability.STRUCTURED_OUTPUT,
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.PARALLEL_TOOLS,
                ModelCapability.VISION
            },
            max_context_tokens=200000,
            max_output_tokens=16384,
            cost_per_1m_input=15.0,
            cost_per_1m_output=75.0,
            speed_rating=3,
            quality_rating=5,
            notes="Highest capability Claude model, best for complex reasoning"
        ))

        self.register(ModelInfo(
            model_id="claude-sonnet-4-5-20250514",
            provider=ModelProvider.ANTHROPIC,
            display_name="Claude Sonnet 4.5",
            capabilities={
                ModelCapability.STREAMING,
                ModelCapability.TOOLS,
                ModelCapability.STRUCTURED_OUTPUT,
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.PARALLEL_TOOLS,
                ModelCapability.VISION
            },
            max_context_tokens=200000,
            max_output_tokens=8192,
            cost_per_1m_input=3.0,
            cost_per_1m_output=15.0,
            speed_rating=4,
            quality_rating=4,
            notes="Balanced Claude model, great for most tasks"
        ))

        self.register(ModelInfo(
            model_id="claude-haiku-4-5-20251015",
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
            max_output_tokens=8192,
            cost_per_1m_input=0.25,
            cost_per_1m_output=1.25,
            speed_rating=5,
            quality_rating=3,
            notes="Fast and cost-effective Claude model"
        ))

        # OpenAI GPT-5 Models
        self.register(ModelInfo(
            model_id="gpt-5-preview",
            provider=ModelProvider.OPENAI,
            display_name="GPT-5 Preview",
            capabilities={
                ModelCapability.STREAMING,
                ModelCapability.TOOLS,
                ModelCapability.STRUCTURED_OUTPUT,
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.PARALLEL_TOOLS,
                ModelCapability.VISION
            },
            max_context_tokens=128000,
            max_output_tokens=16384,
            cost_per_1m_input=10.0,
            cost_per_1m_output=30.0,
            speed_rating=3,
            quality_rating=5,
            notes="Latest GPT model with advanced capabilities"
        ))

        self.register(ModelInfo(
            model_id="gpt-5-turbo",
            provider=ModelProvider.OPENAI,
            display_name="GPT-5 Turbo",
            capabilities={
                ModelCapability.STREAMING,
                ModelCapability.TOOLS,
                ModelCapability.STRUCTURED_OUTPUT,
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.PARALLEL_TOOLS,
                ModelCapability.VISION
            },
            max_context_tokens=128000,
            max_output_tokens=16384,
            cost_per_1m_input=2.5,
            cost_per_1m_output=10.0,
            speed_rating=4,
            quality_rating=4,
            notes="Balanced GPT-5 model"
        ))

        # OpenAI o1 Models (Reasoning)
        self.register(ModelInfo(
            model_id="o1-preview",
            provider=ModelProvider.OPENAI,
            display_name="o1 Preview",
            capabilities={
                ModelCapability.STREAMING,
                ModelCapability.REASONING,
                ModelCapability.TOOLS
            },
            max_context_tokens=128000,
            max_output_tokens=32768,
            cost_per_1m_input=15.0,
            cost_per_1m_output=60.0,
            speed_rating=2,
            quality_rating=5,
            notes="Advanced reasoning model, slower but more thoughtful"
        ))

        self.register(ModelInfo(
            model_id="o1-mini",
            provider=ModelProvider.OPENAI,
            display_name="o1 Mini",
            capabilities={
                ModelCapability.STREAMING,
                ModelCapability.REASONING,
                ModelCapability.TOOLS
            },
            max_context_tokens=128000,
            max_output_tokens=16384,
            cost_per_1m_input=3.0,
            cost_per_1m_output=12.0,
            speed_rating=3,
            quality_rating=4,
            notes="Faster reasoning model"
        ))

        # Google Gemini Models
        self.register(ModelInfo(
            model_id="gemini-2.0-flash-exp",
            provider=ModelProvider.GOOGLE,
            display_name="Gemini 2.0 Flash Experimental",
            capabilities={
                ModelCapability.STREAMING,
                ModelCapability.TOOLS,
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.PARALLEL_TOOLS,
                ModelCapability.VISION,
                ModelCapability.IMAGE_GENERATION
            },
            max_context_tokens=1000000,
            max_output_tokens=8192,
            cost_per_1m_input=0.0,  # Free during preview
            cost_per_1m_output=0.0,
            speed_rating=5,
            quality_rating=4,
            notes="Experimental Gemini model with multimodal capabilities"
        ))

        self.register(ModelInfo(
            model_id="gemini-exp-1206",
            provider=ModelProvider.GOOGLE,
            display_name="Gemini Experimental 1206",
            capabilities={
                ModelCapability.STREAMING,
                ModelCapability.TOOLS,
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.VISION
            },
            max_context_tokens=2000000,
            max_output_tokens=8192,
            cost_per_1m_input=0.0,  # Free during preview
            cost_per_1m_output=0.0,
            speed_rating=4,
            quality_rating=4,
            notes="Experimental model with extended context"
        ))

        self.register(ModelInfo(
            model_id="gemini-1.5-pro",
            provider=ModelProvider.GOOGLE,
            display_name="Gemini 1.5 Pro",
            capabilities={
                ModelCapability.STREAMING,
                ModelCapability.TOOLS,
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.VISION
            },
            max_context_tokens=2000000,
            max_output_tokens=8192,
            cost_per_1m_input=1.25,
            cost_per_1m_output=5.0,
            speed_rating=3,
            quality_rating=4,
            notes="Pro model with massive context window"
        ))

        self.register(ModelInfo(
            model_id="gemini-1.5-flash",
            provider=ModelProvider.GOOGLE,
            display_name="Gemini 1.5 Flash",
            capabilities={
                ModelCapability.STREAMING,
                ModelCapability.TOOLS,
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.VISION
            },
            max_context_tokens=1000000,
            max_output_tokens=8192,
            cost_per_1m_input=0.075,
            cost_per_1m_output=0.30,
            speed_rating=5,
            quality_rating=3,
            notes="Fast and cost-effective Gemini model"
        ))

        # GPT-4o (multimodal)
        self.register(ModelInfo(
            model_id="gpt-4o",
            provider=ModelProvider.OPENAI,
            display_name="GPT-4o",
            capabilities={
                ModelCapability.STREAMING,
                ModelCapability.TOOLS,
                ModelCapability.STRUCTURED_OUTPUT,
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.PARALLEL_TOOLS,
                ModelCapability.VISION,
                ModelCapability.AUDIO
            },
            max_context_tokens=128000,
            max_output_tokens=16384,
            cost_per_1m_input=2.5,
            cost_per_1m_output=10.0,
            speed_rating=4,
            quality_rating=4,
            notes="Multimodal GPT-4 with vision and audio"
        ))

        logger.info(f"✓ Model registry initialized with {len(self._models)} models")

    def register(self, model: ModelInfo):
        """Register a new model or update existing."""
        self._models[model.model_id] = model
        logger.debug(f"Registered model: {model.model_id} ({model.display_name})")

    def get_model(self, model_id: str) -> Optional[ModelInfo]:
        """Get model information by ID."""
        return self._models.get(model_id)

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
