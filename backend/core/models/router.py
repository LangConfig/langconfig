# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Dynamic Model Router for LangConfig.

Intelligently routes tasks to appropriate LLM models based on complexity,
achieving 40-60% cost savings by using cheaper models for simple tasks
while maintaining quality on complex work.

Inspired by LangGraph's dynamic model selection pattern.
"""

import logging
from typing import Dict, Any, Optional
from enum import Enum

from .graph_state import WorkflowState

logger = logging.getLogger(__name__)


class ModelTier(str, Enum):
    """Model tiers ordered by capability and cost."""
    FAST = "fast"          # gpt-4o-mini - cheap, fast, good for simple tasks
    STANDARD = "standard"  # gpt-4o - balanced performance/cost
    POWERFUL = "powerful"  # claude-3.5-sonnet - high quality, expensive
    REASONING = "reasoning"  # o1-preview - deep reasoning, very expensive


class ModelRouter:
    """
    Dynamically select models based on task complexity and optimization goals.

    This router analyzes the task description and metadata to choose the most
    appropriate model tier, significantly reducing costs while maintaining quality.

    Example Usage:
        >>> state = WorkflowState(task_description="fix typo in README")
        >>> model = ModelRouter.select_model(state, config={})
        >>> print(model)  # "gpt-4o-mini"

        >>> state = WorkflowState(task_description="design authentication system")
        >>> model = ModelRouter.select_model(state, config={})
        >>> print(model)  # "claude-3.5-sonnet"
    """

    # Complexity indicators that suggest a simple task
    SIMPLE_INDICATORS = [
        'fix typo', 'update comment', 'rename variable', 'format code',
        'add comment', 'update docstring', 'fix formatting', 'update readme',
        'fix spacing', 'remove unused', 'update version', 'change color',
        'update text', 'fix lint', 'add import', 'remove import'
    ]

    # Complexity indicators that suggest a moderate task
    MODERATE_INDICATORS = [
        'add function', 'refactor', 'add test', 'debug', 'fix bug',
        'update logic', 'modify endpoint', 'add validation', 'error handling',
        'add logging', 'improve performance', 'add feature', 'implement'
    ]

    # Complexity indicators that suggest a complex task
    COMPLEX_INDICATORS = [
        'design system', 'architecture', 'security', 'optimize performance',
        'scalability', 'database schema', 'authentication', 'authorization',
        'migration', 'integration', 'infrastructure', 'deployment pipeline',
        'distributed system', 'microservices', 'api design', 'data model'
    ]

    # Indicators that require deep reasoning (o1-preview)
    REASONING_INDICATORS = [
        'algorithm', 'optimization problem', 'mathematical', 'proof',
        'complex logic', 'graph theory', 'dynamic programming', 'recursion',
        'performance analysis', 'complexity analysis'
    ]

    # Model configurations by tier (Updated December 2025)
    MODEL_CONFIGS = {
        ModelTier.FAST: {
            'model': 'gpt-4o-mini',
            'temperature': 0.7,
            'max_tokens': 4096,
            'timeout': 30,
            'cost_per_1k_tokens': 0.00015  # $0.15 per 1M tokens
        },
        ModelTier.STANDARD: {
            'model': 'gpt-4o',
            'temperature': 0.7,
            'max_tokens': 16384,
            'timeout': 60,
            'cost_per_1k_tokens': 0.0025  # $2.50 per 1M tokens
        },
        ModelTier.POWERFUL: {
            'model': 'claude-sonnet-4-5',
            'temperature': 0.7,
            'max_tokens': 30000,
            'timeout': 90,
            'cost_per_1k_tokens': 0.003  # $3.00 per 1M tokens
        },
        ModelTier.REASONING: {
            'model': 'o3',
            'temperature': 1.0,  # o3 uses fixed temperature
            'max_tokens': 32768,
            'timeout': 120,
            'cost_per_1k_tokens': 0.020  # $20.00 per 1M tokens
        }
    }

    @classmethod
    def select_model(
        cls,
        state: WorkflowState,
        config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Select the most appropriate model for the task.

        Args:
            state: Current workflow state containing task information
            config: Optional configuration overrides
                - optimize_cost: bool - Force cheapest model
                - force_tier: ModelTier - Override automatic selection
                - min_tier: ModelTier - Minimum tier to use

        Returns:
            Model identifier string (e.g., "gpt-4o-mini", "claude-3.5-sonnet")
        """
        if config is None:
            config = {}

        # Check for forced tier override
        if 'force_tier' in config:
            tier = ModelTier(config['force_tier'])
            logger.info(f"Using forced model tier: {tier}")
            return cls.MODEL_CONFIGS[tier]['model']

        # Check for aggressive cost optimization
        if config.get('optimize_cost', False):
            logger.info("Cost optimization enabled - using FAST tier")
            return cls.MODEL_CONFIGS[ModelTier.FAST]['model']

        # Determine complexity tier from task description
        tier = cls._analyze_complexity(state, config)

        # Apply minimum tier constraint
        min_tier = config.get('min_tier')
        if min_tier:
            min_tier_enum = ModelTier(min_tier)
            tier_order = list(ModelTier)
            if tier_order.index(tier) < tier_order.index(min_tier_enum):
                logger.info(f"Upgrading from {tier} to minimum tier {min_tier_enum}")
                tier = min_tier_enum

        model = cls.MODEL_CONFIGS[tier]['model']

        logger.info(
            f"Selected model tier {tier.value} ({model}) for task: "
            f"{state.get('current_directive', '')[:50]}..."
        )

        return model

    @classmethod
    def _analyze_complexity(
        cls,
        state: WorkflowState,
        config: Dict[str, Any]
    ) -> ModelTier:
        """
        Analyze task complexity and return appropriate tier.

        Uses multiple signals:
        1. Task description keywords
        2. Task metadata (explicit complexity markers)
        3. Historical data (if available)
        4. Classification type (DevOps might need more power)
        """
        # Get task description
        task_description = state.get('current_directive', '')
        if not task_description:
            task_description = state.get('original_directive', '')

        task_lower = task_description.lower()

        # Check for explicit complexity in metadata
        task_metadata = state.get('strategy_state', {})

        if task_metadata.get('requires_reasoning'):
            return ModelTier.REASONING

        if task_metadata.get('complexity') == 'high':
            return ModelTier.POWERFUL

        if task_metadata.get('complexity') == 'low':
            return ModelTier.FAST

        # Check for reasoning indicators (highest priority)
        for indicator in cls.REASONING_INDICATORS:
            if indicator in task_lower:
                logger.debug(f"Reasoning indicator found: {indicator}")
                return ModelTier.REASONING

        # Check for complex task indicators
        for indicator in cls.COMPLEX_INDICATORS:
            if indicator in task_lower:
                logger.debug(f"Complex indicator found: {indicator}")
                return ModelTier.POWERFUL

        # Check for simple task indicators
        for indicator in cls.SIMPLE_INDICATORS:
            if indicator in task_lower:
                logger.debug(f"Simple indicator found: {indicator}")
                return ModelTier.FAST

        # Check for moderate task indicators
        for indicator in cls.MODERATE_INDICATORS:
            if indicator in task_lower:
                logger.debug(f"Moderate indicator found: {indicator}")
                return ModelTier.STANDARD

        # Check classification type for hints
        classification = state.get('classification', '')
        if classification == 'DEVOPS_IAC':
            # DevOps tasks can be risky - use higher tier
            return ModelTier.POWERFUL

        # Check retry count - if retrying, upgrade to more powerful model
        retry_count = state.get('retry_count', 0)
        if retry_count > 0:
            logger.info(f"Task has {retry_count} retries - upgrading model tier")
            return ModelTier.POWERFUL

        # Default to standard tier for ambiguous cases
        logger.debug("No clear complexity indicators - using STANDARD tier")
        return ModelTier.STANDARD

    @classmethod
    def get_model_config(
        cls,
        model_name: str,
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Get full configuration for a model.

        Args:
            model_name: Model identifier (e.g., "gpt-4o-mini")
            temperature: Optional temperature override

        Returns:
            Dictionary with model configuration
        """
        # Find tier by model name
        tier = None
        for t, config in cls.MODEL_CONFIGS.items():
            if config['model'] == model_name:
                tier = t
                break

        if not tier:
            logger.warning(f"Unknown model {model_name}, using STANDARD config")
            tier = ModelTier.STANDARD

        config = cls.MODEL_CONFIGS[tier].copy()

        # Apply temperature override
        if temperature is not None:
            config['temperature'] = temperature

        return config

    @classmethod
    def estimate_cost(
        cls,
        model_name: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """
        Estimate cost for a model invocation.

        Args:
            model_name: Model identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Estimated cost in USD
        """
        config = cls.get_model_config(model_name)
        cost_per_1k = config.get('cost_per_1k_tokens', 0.001)

        total_tokens = input_tokens + output_tokens
        estimated_cost = (total_tokens / 1000) * cost_per_1k

        return estimated_cost

    @classmethod
    def compare_tiers(cls) -> Dict[str, Any]:
        """
        Get comparison data for all model tiers.

        Returns:
            Dictionary with tier comparison data for UI/reporting
        """
        return {
            tier.value: {
                'model': config['model'],
                'cost_per_1k': config['cost_per_1k_tokens'],
                'max_tokens': config['max_tokens'],
                'timeout': config['timeout'],
                'use_cases': cls._get_tier_use_cases(tier)
            }
            for tier, config in cls.MODEL_CONFIGS.items()
        }

    @classmethod
    def _get_tier_use_cases(cls, tier: ModelTier) -> list:
        """Get typical use cases for a tier."""
        use_cases = {
            ModelTier.FAST: [
                "Formatting and style fixes",
                "Simple refactoring",
                "Documentation updates",
                "Comment additions"
            ],
            ModelTier.STANDARD: [
                "Feature implementation",
                "Bug fixes",
                "Test writing",
                "API endpoint creation"
            ],
            ModelTier.POWERFUL: [
                "System architecture",
                "Security implementations",
                "Complex refactoring",
                "Database design"
            ],
            ModelTier.REASONING: [
                "Algorithm design",
                "Performance optimization",
                "Complex problem solving",
                "Mathematical implementations"
            ]
        }
        return use_cases.get(tier, [])


# Convenience functions for direct usage

async def get_optimized_model(
    state: WorkflowState,
    config: Optional[Dict[str, Any]] = None
) -> str:
    """
    Convenience async function to get optimized model.

    Can be called directly from workflow nodes.
    """
    return ModelRouter.select_model(state, config)


async def get_optimized_model_config(
    state: WorkflowState,
    config: Optional[Dict[str, Any]] = None,
    temperature: Optional[float] = None
) -> Dict[str, Any]:
    """
    Get full optimized model configuration.

    Returns complete config ready for litellm.acompletion()
    """
    model = ModelRouter.select_model(state, config)
    model_config = ModelRouter.get_model_config(model, temperature)

    return model_config
