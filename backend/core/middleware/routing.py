# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Dynamic Model Routing Middleware

Analyzes task complexity and requirements to dynamically select the most appropriate
LLM model based on configurable strategies.

This enables cost optimization, performance optimization, or balanced approaches
by routing requests to different models based on task characteristics.

Usage:
    from core.middleware.routing import ModelRouter

    router = ModelRouter()
    selected_model = router.route(
        original_model="claude-haiku-4-5-20251015",
        context_length=5000,
        tool_count=10,
        strategy="cost_optimized"
    )

NOTE: Model routing is OPT-IN only. It must be explicitly enabled via
agent_config["enable_model_routing"] = True
"""

from typing import Dict, Any, Optional
from enum import Enum
import logging

from core.models.registry import model_registry, ModelCapability

logger = logging.getLogger(__name__)


# =============================================================================
# Routing Strategies
# =============================================================================

class RoutingStrategy(str, Enum):
    """Available routing strategies."""
    COST_OPTIMIZED = "cost_optimized"
    PERFORMANCE_OPTIMIZED = "performance_optimized"
    BALANCED = "balanced"
    ADAPTIVE = "adaptive"


# =============================================================================
# Task Complexity Analysis
# =============================================================================

class TaskComplexity(str, Enum):
    """Task complexity levels."""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    VERY_COMPLEX = "very_complex"


def analyze_task_complexity(
    context_length: int,
    tool_count: int,
    has_structured_output: bool = False,
    has_vision: bool = False,
    prompt_length: int = 0
) -> TaskComplexity:
    """
    Analyze task complexity based on characteristics.

    Args:
        context_length: Length of context in characters
        tool_count: Number of tools available
        has_structured_output: Whether structured output is required
        has_vision: Whether vision capabilities are needed
        prompt_length: Length of system prompt

    Returns:
        TaskComplexity level
    """
    complexity_score = 0

    # Context complexity (weight: 1-3)
    if context_length > 50000:
        complexity_score += 3
    elif context_length > 20000:
        complexity_score += 2
    elif context_length > 5000:
        complexity_score += 1

    # Tool complexity (weight: 1-4)
    if tool_count > 15:
        complexity_score += 4
    elif tool_count > 10:
        complexity_score += 3
    elif tool_count > 5:
        complexity_score += 2
    elif tool_count > 0:
        complexity_score += 1

    # Structured output adds complexity
    if has_structured_output:
        complexity_score += 2

    # Vision adds significant complexity
    if has_vision:
        complexity_score += 3

    # Long prompts suggest complex reasoning
    if prompt_length > 2000:
        complexity_score += 2
    elif prompt_length > 1000:
        complexity_score += 1

    # Map score to complexity level
    if complexity_score >= 10:
        return TaskComplexity.VERY_COMPLEX
    elif complexity_score >= 7:
        return TaskComplexity.COMPLEX
    elif complexity_score >= 4:
        return TaskComplexity.MODERATE
    else:
        return TaskComplexity.SIMPLE


# =============================================================================
# Model Router
# =============================================================================

class ModelRouter:
    """
    Dynamic model router that selects appropriate models based on task requirements.

    The router analyzes task characteristics and selects models according to
    the specified strategy while respecting capability requirements.
    """

    def __init__(self):
        """Initialize router with model registry."""
        self.registry = model_registry
        logger.debug("ModelRouter initialized")

    def route(
        self,
        original_model: str,
        context_length: int = 0,
        tool_count: int = 0,
        strategy: str = "balanced",
        requirements: Optional[Dict[str, Any]] = None,
        force_routing: bool = False
    ) -> str:
        """
        Route to the best model based on task characteristics and strategy.

        Args:
            original_model: Originally requested model
            context_length: Length of context in characters
            tool_count: Number of tools available
            strategy: Routing strategy (cost_optimized, performance_optimized, balanced, adaptive)
            requirements: Additional requirements (streaming, structured_output, vision, etc.)
            force_routing: Force routing even for simple tasks

        Returns:
            Selected model ID (may be same as original if optimal)
        """
        requirements = requirements or {}

        # Get original model info
        original_info = self.registry.get_model(original_model)
        if not original_info:
            logger.warning(f"Original model '{original_model}' not in registry, keeping as-is")
            return original_model

        # Analyze task complexity
        complexity = analyze_task_complexity(
            context_length=context_length,
            tool_count=tool_count,
            has_structured_output=requirements.get("structured_output", False),
            has_vision=requirements.get("vision", False),
            prompt_length=requirements.get("prompt_length", 0)
        )

        logger.info(f"Task complexity analysis: {complexity.value}")
        logger.debug(f"  Context length: {context_length}, Tools: {tool_count}")

        # Build requirements from task analysis
        model_requirements = self._build_requirements(
            original_info,
            complexity,
            requirements
        )

        # Apply routing strategy
        selected_model = self._apply_strategy(
            strategy=strategy,
            complexity=complexity,
            requirements=model_requirements,
            original_model=original_model,
            force_routing=force_routing
        )

        if selected_model != original_model:
            logger.info(f"🔀 Model routing: {original_model} → {selected_model} (strategy: {strategy})")
        else:
            logger.debug(f"✓ Model routing: keeping original model '{original_model}'")

        return selected_model

    def _build_requirements(
        self,
        original_info,
        complexity: TaskComplexity,
        additional_requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build comprehensive requirements from task analysis."""
        requirements = {
            "streaming": additional_requirements.get("streaming", False),
            "tools": additional_requirements.get("tools", False),
            "structured_output": additional_requirements.get("structured_output", False),
            "vision": additional_requirements.get("vision", False),
            "reasoning": additional_requirements.get("reasoning", False),
            "provider": additional_requirements.get("provider"),
        }

        # Adjust context requirements based on complexity
        if complexity == TaskComplexity.VERY_COMPLEX:
            requirements["min_context_tokens"] = 128000
        elif complexity == TaskComplexity.COMPLEX:
            requirements["min_context_tokens"] = 64000
        elif complexity == TaskComplexity.MODERATE:
            requirements["min_context_tokens"] = 32000
        else:
            requirements["min_context_tokens"] = 8000

        return requirements

    def _apply_strategy(
        self,
        strategy: str,
        complexity: TaskComplexity,
        requirements: Dict[str, Any],
        original_model: str,
        force_routing: bool
    ) -> str:
        """Apply routing strategy to select model."""

        if strategy == RoutingStrategy.COST_OPTIMIZED:
            return self._route_cost_optimized(complexity, requirements, original_model, force_routing)
        elif strategy == RoutingStrategy.PERFORMANCE_OPTIMIZED:
            return self._route_performance_optimized(complexity, requirements, original_model)
        elif strategy == RoutingStrategy.ADAPTIVE:
            return self._route_adaptive(complexity, requirements, original_model, force_routing)
        else:  # balanced (default)
            return self._route_balanced(complexity, requirements, original_model, force_routing)

    def _route_cost_optimized(
        self,
        complexity: TaskComplexity,
        requirements: Dict[str, Any],
        original_model: str,
        force_routing: bool
    ) -> str:
        """
        Route to cheapest model that meets requirements.

        Strategy: Always use cheapest model unless task is very complex.
        """
        # For simple/moderate tasks, use cheapest
        if complexity in [TaskComplexity.SIMPLE, TaskComplexity.MODERATE]:
            selected = self.registry.find_best_model(requirements, strategy="cost_optimized")
            if selected:
                return selected

        # For complex tasks, still prefer cost but with higher quality threshold
        if complexity == TaskComplexity.COMPLEX:
            # Find cheap models with quality >= 3
            candidates = self.registry.find_models_with_capabilities(
                required_capabilities=self._extract_capabilities(requirements)
            )
            candidates = [c for c in candidates if c.quality_rating >= 3]
            if candidates:
                candidates.sort(key=lambda m: m.cost_per_1m_input + m.cost_per_1m_output)
                return candidates[0].model_id

        # Very complex: use original or find best performance
        if complexity == TaskComplexity.VERY_COMPLEX:
            # Don't downgrade for very complex tasks
            original_info = self.registry.get_model(original_model)
            if original_info and original_info.quality_rating >= 4:
                return original_model

        # Fallback to best match
        selected = self.registry.find_best_model(requirements, strategy="cost_optimized")
        return selected if selected else original_model

    def _route_performance_optimized(
        self,
        complexity: TaskComplexity,
        requirements: Dict[str, Any],
        original_model: str
    ) -> str:
        """
        Route to highest quality model.

        Strategy: Always use best quality model regardless of cost.
        """
        selected = self.registry.find_best_model(requirements, strategy="performance_optimized")
        return selected if selected else original_model

    def _route_balanced(
        self,
        complexity: TaskComplexity,
        requirements: Dict[str, Any],
        original_model: str,
        force_routing: bool
    ) -> str:
        """
        Route based on best quality/cost ratio.

        Strategy: Use fast models for simple tasks, better models for complex tasks.
        """
        # Simple tasks: Use fast, cheap models
        if complexity == TaskComplexity.SIMPLE and not force_routing:
            candidates = self.registry.find_models_with_capabilities(
                required_capabilities=self._extract_capabilities(requirements)
            )
            # Filter for speed >= 4
            fast_models = [c for c in candidates if c.speed_rating >= 4]
            if fast_models:
                # Sort by cost
                fast_models.sort(key=lambda m: m.cost_per_1m_input + m.cost_per_1m_output)
                return fast_models[0].model_id

        # Moderate: Balanced models
        if complexity == TaskComplexity.MODERATE:
            selected = self.registry.find_best_model(requirements, strategy="balanced")
            if selected:
                return selected

        # Complex/Very Complex: Quality models
        if complexity in [TaskComplexity.COMPLEX, TaskComplexity.VERY_COMPLEX]:
            candidates = self.registry.find_models_with_capabilities(
                required_capabilities=self._extract_capabilities(requirements)
            )
            # Filter for quality >= 4
            quality_models = [c for c in candidates if c.quality_rating >= 4]
            if quality_models:
                # For balanced, sort by quality/cost ratio
                def score(m):
                    avg_cost = (m.cost_per_1m_input + m.cost_per_1m_output) / 2
                    return m.quality_rating / avg_cost if avg_cost > 0 else m.quality_rating * 1000
                quality_models.sort(key=score, reverse=True)
                return quality_models[0].model_id

        # Fallback
        return original_model

    def _route_adaptive(
        self,
        complexity: TaskComplexity,
        requirements: Dict[str, Any],
        original_model: str,
        force_routing: bool
    ) -> str:
        """
        Route adaptively based on task complexity.

        Strategy: Start cheap, escalate to better models as complexity increases.
        """
        caps = self._extract_capabilities(requirements)
        candidates = self.registry.find_models_with_capabilities(caps)

        if not candidates:
            return original_model

        # Map complexity to minimum quality rating
        min_quality = {
            TaskComplexity.SIMPLE: 2,
            TaskComplexity.MODERATE: 3,
            TaskComplexity.COMPLEX: 4,
            TaskComplexity.VERY_COMPLEX: 5
        }

        # Filter by minimum quality
        qualified = [c for c in candidates if c.quality_rating >= min_quality[complexity]]

        if not qualified:
            # No models meet quality threshold, use best available
            candidates.sort(key=lambda m: m.quality_rating, reverse=True)
            return candidates[0].model_id

        # Sort by cost within qualified models
        qualified.sort(key=lambda m: m.cost_per_1m_input + m.cost_per_1m_output)
        return qualified[0].model_id

    def _extract_capabilities(self, requirements: Dict[str, Any]) -> set:
        """Extract ModelCapability set from requirements dict."""
        caps = set()
        if requirements.get("streaming"):
            caps.add(ModelCapability.STREAMING)
        if requirements.get("tools"):
            caps.add(ModelCapability.TOOLS)
        if requirements.get("structured_output"):
            caps.add(ModelCapability.STRUCTURED_OUTPUT)
        if requirements.get("vision"):
            caps.add(ModelCapability.VISION)
        if requirements.get("reasoning"):
            caps.add(ModelCapability.REASONING)
        return caps

    def explain_routing(
        self,
        original_model: str,
        selected_model: str,
        complexity: TaskComplexity,
        strategy: str
    ) -> str:
        """Generate human-readable explanation of routing decision."""
        if original_model == selected_model:
            return f"Original model '{original_model}' is optimal for this {complexity.value} task."

        original_info = self.registry.get_model(original_model)
        selected_info = self.registry.get_model(selected_model)

        if not original_info or not selected_info:
            return f"Routed to '{selected_model}' (model info unavailable)"

        cost_diff = (
            (selected_info.cost_per_1m_input - original_info.cost_per_1m_input) /
            original_info.cost_per_1m_input * 100
        )

        explanation = (
            f"Routed from '{original_model}' to '{selected_model}' for {complexity.value} task.\n"
            f"Strategy: {strategy}\n"
            f"Quality: {original_info.quality_rating} → {selected_info.quality_rating}\n"
            f"Speed: {original_info.speed_rating} → {selected_info.speed_rating}\n"
            f"Cost change: {cost_diff:+.1f}%"
        )

        return explanation


# =============================================================================
# Convenience Functions
# =============================================================================

def route_model(
    original_model: str,
    context_length: int = 0,
    tool_count: int = 0,
    strategy: str = "balanced",
    **kwargs
) -> str:
    """
    Convenience function for model routing.

    Args:
        original_model: Original model ID
        context_length: Context length in characters
        tool_count: Number of tools
        strategy: Routing strategy
        **kwargs: Additional requirements

    Returns:
        Selected model ID
    """
    router = ModelRouter()
    return router.route(
        original_model=original_model,
        context_length=context_length,
        tool_count=tool_count,
        strategy=strategy,
        requirements=kwargs
    )
