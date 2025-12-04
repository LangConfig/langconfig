# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Dynamic Model Selector for Agent Factory

Implements runtime model selection based on conversation state and task complexity.
This enables 60-80% cost savings by using cheaper models for simple queries.

This is COMPLEMENTARY to ModelRouter:
- ModelRouter: Workflow-level selection (chooses initial model for a task)
- ModelSelector: Agent-level dynamic selection (switches models during conversation)

Routing Rules:
1. Code-heavy tasks → Claude Sonnet 4.5 (best for code)
2. Simple queries (<=2 messages, <200 chars) → GPT-4o-mini (fast/cheap)
3. Research/analysis → Gemini 2.5 Pro (large context)
4. Long conversations (>10 messages) → Primary model
5. Default → GPT-4o (balanced)
"""

import logging
from typing import Dict, Any, List, Callable
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from core.models.router import ModelRouter, ModelTier

logger = logging.getLogger(__name__)


class ModelSelector:
    """
    Dynamic model selector that chooses optimal LLM based on task complexity.

    This implements the "Roman Legion" strategy where:
    - Simple tasks use fast/cheap models (80% cost reduction)
    - Complex tasks use powerful models (best quality)
    - Model selection is transparent to the user
    """

    def __init__(
        self,
        primary_model: str = "gpt-5",
        temperature: float = 0.5,
        enable_routing: bool = True,
        agent_config: Dict[str, Any] = None,
        use_model_router_config: bool = True
    ):
        """
        Initialize model selector.

        Args:
            primary_model: Default model for complex tasks
            temperature: Temperature for generation
            enable_routing: Enable dynamic routing (if False, always use primary)
            agent_config: Full agent configuration
            use_model_router_config: Use ModelRouter tier configurations (recommended)
        """
        self.primary_model = primary_model
        self.temperature = temperature
        self.enable_routing = enable_routing
        self.agent_config = agent_config or {}
        self.use_model_router_config = use_model_router_config

        # Get model configurations from ModelRouter if enabled
        if use_model_router_config:
            self.tier_configs = ModelRouter.MODEL_CONFIGS
            logger.info("Using ModelRouter tier configurations for cost optimization")

        # Track model usage for analytics (use all possible models from ModelRouter)
        self.model_usage = {
            "gpt-4o-mini": 0,
            "gpt-4o": 0,
            "gpt-5": 0,
            "claude-sonnet-4-5-20250929": 0,
            "claude-3.5-sonnet": 0,
            "gemini-2.5-pro": 0,
            "o1-preview": 0
        }

    def create_selector(self, tools: List[BaseTool]) -> Callable:
        """
        Create a model selector function for use with create_react_agent().

        Args:
            tools: List of tools to bind to models

        Returns:
            Function that selects model based on state

        Example:
            >>> selector = ModelSelector("gpt-5", temperature=0.5)
            >>> model_fn = selector.create_selector(tools)
            >>> agent = create_react_agent(model=model_fn, tools=tools)
        """

        # If routing disabled, return static selector
        if not self.enable_routing:
            return self._create_static_selector(tools)

        # Return dynamic selector
        return self._create_dynamic_selector(tools)

    def _create_static_selector(self, tools: List[BaseTool]) -> Callable:
        """Create static model selector (always uses primary model)."""

        from core.agents.factory import AgentFactory

        def static_selector(state: dict, config: dict) -> BaseChatModel:
            """Always return primary model."""
            llm = AgentFactory._create_llm(
                self.primary_model,
                self.temperature,
                None,
                self.agent_config
            )
            return llm.bind_tools(tools)

        return static_selector

    def _create_dynamic_selector(self, tools: List[BaseTool]) -> Callable:
        """
        Create dynamic model selector with routing logic.

        Enhanced to use ModelRouter configurations for consistent tier-based selection.
        """

        from core.agents.factory import AgentFactory

        def dynamic_selector(state: dict, config: dict) -> BaseChatModel:
            """
            Select optimal model based on conversation state.

            Routing Logic (Enhanced with ModelRouter integration):
            - Code tasks → Claude Sonnet (POWERFUL tier)
            - Simple queries → GPT-4o-mini (FAST tier) - 80% cost savings!
            - Research → Gemini Pro (large context)
            - Deep reasoning → o1-preview (REASONING tier)
            - Complex/long → Primary model
            - Default → GPT-4o (STANDARD tier)
            """

            messages = state.get("messages", [])
            message_count = len(messages)

            # Get last message content
            content = ""
            if messages:
                last_msg = messages[-1]
                content = last_msg.content if hasattr(last_msg, 'content') else ""

            content_lower = content.lower()

            # RULE 0: Deep reasoning tasks → o1-preview (REASONING tier)
            # Check ModelRouter's reasoning indicators
            reasoning_indicators = [
                "algorithm", "optimization problem", "mathematical", "proof",
                "complex logic", "graph theory", "dynamic programming", "recursion"
            ]
            if any(kw in content_lower for kw in reasoning_indicators):
                model_name = "o1-preview"
                temp = 1.0  # o1 uses fixed temperature
                self.model_usage[model_name] = self.model_usage.get(model_name, 0) + 1
                logger.info(f"🎯 Selected: o1-preview (REASONING tier - deep reasoning task)")

            # RULE 1: Code-heavy tasks → Claude Sonnet 4.5 (POWERFUL tier)
            elif any(kw in content_lower for kw in [
                "implement", "function", "class", "refactor",
                "code review", "debug", "fix bug", "write code",
                "programming", "syntax", "algorithm", "security",
                "architecture", "design system"
            ]):
                model_name = "claude-sonnet-4-5-20250929"
                temp = 0.3  # Lower temp for precise code
                self.model_usage[model_name] = self.model_usage.get(model_name, 0) + 1
                logger.info(f"🎯 Selected: Claude Sonnet 4.5 (POWERFUL tier - code task)")

            # RULE 2: Simple queries → GPT-4o-mini (FAST tier - BIGGEST SAVINGS!)
            elif message_count <= 2 and len(content) < 200:
                model_name = "gpt-4o-mini"
                temp = 0.7
                self.model_usage[model_name] = self.model_usage.get(model_name, 0) + 1

                # Get cost savings from ModelRouter config
                if self.use_model_router_config:
                    fast_cost = self.tier_configs[ModelTier.FAST]['cost_per_1k_tokens']
                    standard_cost = self.tier_configs[ModelTier.STANDARD]['cost_per_1k_tokens']
                    savings_pct = ((standard_cost - fast_cost) / standard_cost) * 100
                    logger.info(f"🎯 Selected: GPT-4o-mini (FAST tier) - {savings_pct:.0f}% cost reduction!")
                else:
                    logger.info(f"🎯 Selected: GPT-4o-mini (FAST tier) - ~80% cost reduction!")

            # RULE 3: Research/analysis → Gemini 2.5 Pro (large context)
            elif any(kw in content_lower for kw in [
                "research", "analyze", "investigate", "explain",
                "summarize", "study", "review", "compare"
            ]):
                model_name = "gemini-2.5-pro"
                temp = 0.4
                self.model_usage[model_name] = self.model_usage.get(model_name, 0) + 1
                logger.info(f"🎯 Selected: Gemini 2.5 Pro (research/analysis - large context)")

            # RULE 4: Long conversations → Primary model (context matters)
            elif message_count > 10:
                model_name = self.primary_model
                temp = self.temperature
                self.model_usage[model_name] = self.model_usage.get(model_name, 0) + 1
                logger.info(f"🎯 Selected: {self.primary_model} (complex conversation, {message_count} messages)")

            # RULE 5: Default → GPT-4o (STANDARD tier - balanced)
            else:
                model_name = "gpt-4o"
                temp = self.temperature
                self.model_usage[model_name] = self.model_usage.get(model_name, 0) + 1
                logger.info(f"🎯 Selected: GPT-4o (STANDARD tier - balanced, message #{message_count})")

            # Create LLM instance
            try:
                llm = AgentFactory._create_llm(
                    model_name,
                    temp,
                    None,
                    self.agent_config
                )

                # Bind tools
                llm_with_tools = llm.bind_tools(tools)

                return llm_with_tools

            except Exception as e:
                logger.error(f"Failed to create model {model_name}: {e}, falling back to primary")
                # Fallback to primary model
                llm = AgentFactory._create_llm(
                    self.primary_model,
                    self.temperature,
                    None,
                    self.agent_config
                )
                return llm.bind_tools(tools)

        return dynamic_selector

    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get model usage statistics.

        Returns:
            Dict with usage counts and cost estimates

        Example:
            >>> stats = selector.get_usage_stats()
            >>> print(f"Saved {stats['savings_percent']:.1f}% on costs")
        """

        total_calls = sum(self.model_usage.values())

        if total_calls == 0:
            return {
                "total_calls": 0,
                "model_distribution": {},
                "estimated_savings": 0.0,
                "savings_percent": 0.0
            }

        # Get cost estimates from ModelRouter if available, otherwise use defaults
        if self.use_model_router_config:
            cost_per_1k = {}
            for tier, tier_config in self.tier_configs.items():
                model_name = tier_config['model']
                cost_per_1k[model_name] = tier_config['cost_per_1k_tokens']
            # Add any missing models with default estimates
            cost_per_1k.setdefault("gpt-5", 0.010)
            cost_per_1k.setdefault("claude-sonnet-4-5-20250929", 0.003)
            cost_per_1k.setdefault("gemini-2.5-pro", 0.0035)
        else:
            # Rough cost estimates (per 1K tokens) - average of input/output
            cost_per_1k = {
                "gpt-4o-mini": 0.000375,  # ($0.15 + $0.60) / 2 per 1M
                "gpt-4o": 0.00625,        # ($2.50 + $10) / 2 per 1M
                "gpt-5": 0.00625,          # ($2.50 + $10) / 2 per 1M
                "gpt-5-mini": 0.00125,     # ($0.50 + $2) / 2 per 1M
                "gpt-5-nano": 0.000375,    # ($0.15 + $0.60) / 2 per 1M
                "claude-sonnet-4-5-20250929": 0.009,  # ($3 + $15) / 2 per 1M
                "claude-haiku-4-5-20251015": 0.00075,  # ($0.25 + $1.25) / 2 per 1M
                "gemini-2.5-pro": 0.003125,  # ($1.25 + $5) / 2 per 1M
                "gemini-2.5-flash": 0.0001875  # ($0.075 + $0.30) / 2 per 1M
            }

        # Calculate what we would have paid with primary model only
        base_cost = total_calls * cost_per_1k.get(self.primary_model, 0.010) * 500  # Assume 500 tokens avg

        # Calculate actual cost with routing
        actual_cost = sum(
            count * cost_per_1k.get(model, 0.010) * 500
            for model, count in self.model_usage.items()
        )

        savings = base_cost - actual_cost
        savings_percent = (savings / base_cost * 100) if base_cost > 0 else 0

        return {
            "total_calls": total_calls,
            "model_distribution": {
                model: {
                    "count": count,
                    "percent": (count / total_calls * 100)
                }
                for model, count in self.model_usage.items()
                if count > 0
            },
            "estimated_base_cost": base_cost,
            "estimated_actual_cost": actual_cost,
            "estimated_savings": savings,
            "savings_percent": savings_percent
        }

    def reset_stats(self):
        """Reset usage statistics."""
        for model in self.model_usage:
            self.model_usage[model] = 0
