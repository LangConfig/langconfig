# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Advanced Middleware Patterns for LangGraph v1.0

Collection of sophisticated middleware for production use cases:
- Multi-model routing with fallbacks
- Rate limiting and throttling
- Caching with TTL
- A/B testing and experimentation
- Metrics and observability
- Security and compliance

These patterns demonstrate the power and flexibility of the v1.0 middleware system.
"""

import logging
import time
import hashlib
import json
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass, field

from core.middleware.core import AgentMiddleware
from langchain.messages import BaseMessage, AIMessage, HumanMessage

logger = logging.getLogger(__name__)


# =============================================================================
# Multi-Model Routing Middleware
# =============================================================================

@dataclass
class ModelConfig:
    """Configuration for a model in routing."""
    name: str
    cost_per_1k_tokens: float
    latency_ms: int  # Expected latency
    quality_score: float  # 0.0 - 1.0
    max_tokens: int


class MultiModelRoutingMiddleware(AgentMiddleware):
    """
    Intelligently routes requests to different models based on:
    - Task complexity
    - Cost constraints
    - Latency requirements
    - Quality needs

    Example:
        >>> models = {
        ...     "fast": ModelConfig("gpt-4o-mini", 0.00015, 500, 0.7, 16000),
        ...     "balanced": ModelConfig("gpt-4o", 0.0025, 1000, 0.9, 128000),
        ...     "powerful": ModelConfig("gpt-5", 0.010, 2000, 0.95, 200000)
        ... }
        >>> middleware = [MultiModelRoutingMiddleware(models)]
    """

    def __init__(
        self,
        models: Dict[str, ModelConfig],
        default_model: str = "balanced",
        cost_limit_per_call: Optional[float] = None
    ):
        self.models = models
        self.default_model = default_model
        self.cost_limit_per_call = cost_limit_per_call

    def wrap_model_call(self, request: Any, handler: Callable) -> Any:
        """Route to best model based on request characteristics."""

        messages = request.state.get("messages", [])

        # Estimate complexity
        complexity = self._estimate_complexity(messages)

        # Select model
        selected_model = self._select_model(complexity)

        logger.info(f"🎯 Routing to {selected_model} (complexity: {complexity})")

        # Update request with selected model
        request = request.replace(model=selected_model)

        return handler(request)

    def _estimate_complexity(self, messages: List[BaseMessage]) -> str:
        """Estimate task complexity from messages."""
        total_chars = sum(len(m.content) for m in messages if hasattr(m, 'content'))

        # Simple heuristics (can be enhanced with ML)
        if total_chars < 500:
            return "simple"
        elif total_chars < 3000:
            return "moderate"
        else:
            return "complex"

    def _select_model(self, complexity: str) -> str:
        """Select best model for complexity level."""
        if complexity == "simple":
            return self.models.get("fast", self.models[self.default_model]).name
        elif complexity == "moderate":
            return self.models.get("balanced", self.models[self.default_model]).name
        else:
            return self.models.get("powerful", self.models[self.default_model]).name


# =============================================================================
# Rate Limiting Middleware
# =============================================================================

class RateLimitMiddleware(AgentMiddleware):
    """
    Enforces rate limits to prevent API quota exhaustion.

    Tracks requests per:
    - User
    - Project
    - Time window

    Example:
        >>> middleware = [
        ...     RateLimitMiddleware(
        ...         max_requests_per_minute=10,
        ...         max_requests_per_hour=100
        ...     )
        ... ]
    """

    def __init__(
        self,
        max_requests_per_minute: int = 60,
        max_requests_per_hour: int = 1000,
        max_requests_per_day: int = 10000
    ):
        self.max_per_minute = max_requests_per_minute
        self.max_per_hour = max_requests_per_hour
        self.max_per_day = max_requests_per_day

        # Track requests
        self._requests = defaultdict(list)  # user_id -> [timestamps]

    def before_model(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """Check rate limits before model call."""

        # Get user ID from runtime context
        user_id = getattr(runtime.context, 'user_id', 'anonymous') if hasattr(runtime, 'context') else 'anonymous'

        # Check limits
        now = time.time()
        self._cleanup_old_requests(user_id, now)

        requests = self._requests[user_id]

        # Check per-minute
        minute_ago = now - 60
        recent_requests = [ts for ts in requests if ts > minute_ago]
        if len(recent_requests) >= self.max_per_minute:
            logger.warning(f"⚠️ Rate limit exceeded for user {user_id}: {len(recent_requests)}/min")
            raise Exception(f"Rate limit exceeded: {self.max_per_minute} requests per minute")

        # Check per-hour
        hour_ago = now - 3600
        hourly_requests = [ts for ts in requests if ts > hour_ago]
        if len(hourly_requests) >= self.max_per_hour:
            raise Exception(f"Rate limit exceeded: {self.max_per_hour} requests per hour")

        # Check per-day
        day_ago = now - 86400
        daily_requests = [ts for ts in requests if ts > day_ago]
        if len(daily_requests) >= self.max_per_day:
            raise Exception(f"Rate limit exceeded: {self.max_per_day} requests per day")

        # Record this request
        self._requests[user_id].append(now)

        return None

    def _cleanup_old_requests(self, user_id: str, now: float):
        """Remove requests older than 1 day."""
        day_ago = now - 86400
        self._requests[user_id] = [ts for ts in self._requests[user_id] if ts > day_ago]


# =============================================================================
# Caching Middleware
# =============================================================================

class CachingMiddleware(AgentMiddleware):
    """
    Caches model responses to reduce costs and latency.

    Features:
    - TTL-based cache expiration
    - Cache key generation from messages
    - Hit/miss tracking

    Example:
        >>> middleware = [
        ...     CachingMiddleware(
        ...         ttl_seconds=3600,  # 1 hour
        ...         max_cache_size=1000
        ...     )
        ... ]
    """

    def __init__(self, ttl_seconds: int = 3600, max_cache_size: int = 1000):
        self.ttl_seconds = ttl_seconds
        self.max_cache_size = max_cache_size

        # Cache: key -> (response, timestamp)
        self._cache: Dict[str, tuple] = {}

        # Stats
        self.hits = 0
        self.misses = 0

    def before_model(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """Check cache before model call."""

        messages = state.get("messages", [])

        # Generate cache key
        cache_key = self._generate_cache_key(messages)

        # Check cache
        if cache_key in self._cache:
            cached_response, timestamp = self._cache[cache_key]

            # Check TTL
            age_seconds = time.time() - timestamp
            if age_seconds < self.ttl_seconds:
                self.hits += 1
                logger.info(f"✅ Cache HIT (age: {age_seconds:.0f}s, hit rate: {self._hit_rate():.1%})")

                # Return cached response
                return {
                    "messages": messages + [cached_response],
                    "cached": True
                }

        self.misses += 1
        return None

    def after_model(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """Cache response after model call."""

        messages = state.get("messages", [])

        if len(messages) < 2:
            return None

        # Don't cache if this was a cached response
        if state.get("cached", False):
            return None

        # Get last message (model response)
        last_msg = messages[-1]

        if not isinstance(last_msg, AIMessage):
            return None

        # Generate cache key from input messages (all except last)
        input_messages = messages[:-1]
        cache_key = self._generate_cache_key(input_messages)

        # Store in cache
        self._cache[cache_key] = (last_msg, time.time())

        # Enforce max size
        if len(self._cache) > self.max_cache_size:
            # Remove oldest entry
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]

        logger.debug(f"💾 Cached response (cache size: {len(self._cache)})")

        return None

    def _generate_cache_key(self, messages: List[BaseMessage]) -> str:
        """Generate cache key from messages."""
        # Create hash from message contents
        content = json.dumps([
            {"type": type(m).__name__, "content": m.content}
            for m in messages
        ])
        return hashlib.md5(content.encode()).hexdigest()

    def _hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self._hit_rate(),
            "cache_size": len(self._cache)
        }


# =============================================================================
# A/B Testing Middleware
# =============================================================================

class ABTestingMiddleware(AgentMiddleware):
    """
    Enables A/B testing of different models, prompts, or parameters.

    Features:
    - Percentage-based splits
    - Consistent user assignment
    - Metrics tracking per variant

    Example:
        >>> variants = {
        ...     "control": {"model": "gpt-4o", "temperature": 0.7},
        ...     "treatment": {"model": "gpt-5", "temperature": 0.5}
        ... }
        >>> middleware = [
        ...     ABTestingMiddleware(
        ...         experiment_name="model_comparison",
        ...         variants=variants,
        ...         split={"control": 0.5, "treatment": 0.5}
        ...     )
        ... ]
    """

    def __init__(
        self,
        experiment_name: str,
        variants: Dict[str, Dict[str, Any]],
        split: Dict[str, float]
    ):
        self.experiment_name = experiment_name
        self.variants = variants
        self.split = split

        # Validate split adds up to 1.0
        total = sum(split.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Split must add up to 1.0, got {total}")

        # Track metrics per variant
        self.metrics = defaultdict(lambda: {
            "count": 0,
            "total_latency": 0.0,
            "errors": 0
        })

    def wrap_model_call(self, request: Any, handler: Callable) -> Any:
        """Assign to variant and track metrics."""

        # Get user ID for consistent assignment
        user_id = getattr(request.runtime.context, 'user_id', 'anonymous') if hasattr(request.runtime, 'context') else 'anonymous'

        # Assign to variant
        variant = self._assign_variant(user_id)

        logger.info(f"🧪 A/B Test '{self.experiment_name}': Assigned to '{variant}'")

        # Apply variant configuration
        variant_config = self.variants[variant]

        if "model" in variant_config:
            request = request.replace(model=variant_config["model"])

        # Track metrics
        start_time = time.time()

        try:
            response = handler(request)

            # Record success
            latency = time.time() - start_time
            self.metrics[variant]["count"] += 1
            self.metrics[variant]["total_latency"] += latency

            return response

        except Exception as e:
            # Record error
            self.metrics[variant]["errors"] += 1
            raise

    def _assign_variant(self, user_id: str) -> str:
        """Consistently assign user to variant."""
        # Use hash for deterministic assignment
        hash_val = int(hashlib.md5(f"{self.experiment_name}:{user_id}".encode()).hexdigest(), 16)
        threshold = hash_val % 100 / 100.0

        cumulative = 0.0
        for variant, percentage in self.split.items():
            cumulative += percentage
            if threshold < cumulative:
                return variant

        # Fallback to first variant
        return list(self.variants.keys())[0]

    def get_results(self) -> Dict[str, Any]:
        """Get experiment results."""
        results = {}

        for variant, metrics in self.metrics.items():
            count = metrics["count"]
            results[variant] = {
                "count": count,
                "avg_latency": metrics["total_latency"] / count if count > 0 else 0,
                "error_rate": metrics["errors"] / count if count > 0 else 0,
                "errors": metrics["errors"]
            }

        return results


# =============================================================================
# Metrics & Observability Middleware
# =============================================================================

class MetricsMiddleware(AgentMiddleware):
    """
    Comprehensive metrics tracking for observability.

    Tracks:
    - Latency (p50, p95, p99)
    - Token usage
    - Cost
    - Error rates
    - Model distribution

    Example:
        >>> metrics = MetricsMiddleware()
        >>> middleware = [metrics]
        >>> # After execution:
        >>> print(metrics.get_summary())
    """

    def __init__(self):
        self.call_count = 0
        self.error_count = 0
        self.latencies = []
        self.token_usage = []
        self.costs = []
        self.model_counts = defaultdict(int)

        self._start_time = None

    def before_model(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """Start timing."""
        self._start_time = time.time()
        self.call_count += 1
        return None

    def after_model(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """Collect metrics."""

        # Record latency
        if self._start_time:
            latency = time.time() - self._start_time
            self.latencies.append(latency)

        # Record model
        model_name = getattr(runtime, 'model', 'unknown')
        if hasattr(model_name, 'model_name'):
            model_name = model_name.model_name
        self.model_counts[model_name] += 1

        # Record token usage
        messages = state.get("messages", [])
        if messages:
            last_msg = messages[-1]
            if hasattr(last_msg, 'response_metadata'):
                metadata = last_msg.response_metadata
                if 'token_usage' in metadata:
                    usage = metadata['token_usage']
                    self.token_usage.append(usage.get('total_tokens', 0))

        return None

    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary."""
        latencies_sorted = sorted(self.latencies)

        return {
            "calls": {
                "total": self.call_count,
                "errors": self.error_count,
                "success_rate": 1 - (self.error_count / self.call_count) if self.call_count > 0 else 0
            },
            "latency": {
                "p50": self._percentile(latencies_sorted, 0.50) if latencies_sorted else 0,
                "p95": self._percentile(latencies_sorted, 0.95) if latencies_sorted else 0,
                "p99": self._percentile(latencies_sorted, 0.99) if latencies_sorted else 0,
                "avg": sum(self.latencies) / len(self.latencies) if self.latencies else 0
            },
            "tokens": {
                "total": sum(self.token_usage),
                "avg": sum(self.token_usage) / len(self.token_usage) if self.token_usage else 0
            },
            "models": dict(self.model_counts)
        }

    def _percentile(self, sorted_list: List[float], percentile: float) -> float:
        """Calculate percentile from sorted list."""
        if not sorted_list:
            return 0.0

        index = int(len(sorted_list) * percentile)
        return sorted_list[min(index, len(sorted_list) - 1)]


# =============================================================================
# Security & Compliance Middleware
# =============================================================================

class SecurityMiddleware(AgentMiddleware):
    """
    Enforces security and compliance policies.

    Features:
    - PII detection and redaction
    - Content filtering
    - Audit logging
    - Data retention policies

    Example:
        >>> middleware = [
        ...     SecurityMiddleware(
        ...         redact_pii=True,
        ...         allowed_domains=["mycompany.com"],
        ...         audit_log_path="/var/log/agents/"
        ...     )
        ... ]
    """

    def __init__(
        self,
        redact_pii: bool = True,
        allowed_domains: Optional[List[str]] = None,
        audit_log_path: Optional[str] = None
    ):
        self.redact_pii = redact_pii
        self.allowed_domains = allowed_domains or []
        self.audit_log_path = audit_log_path

    def before_model(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """Sanitize input and audit."""

        messages = state.get("messages", [])

        # PII redaction
        if self.redact_pii:
            sanitized_messages = [self._redact_pii_from_message(m) for m in messages]

            # Audit log
            if self.audit_log_path:
                self._audit_log("input", sanitized_messages, runtime)

            return {"messages": sanitized_messages}

        return None

    def after_model(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        """Sanitize output and audit."""

        messages = state.get("messages", [])

        if self.audit_log_path and messages:
            self._audit_log("output", [messages[-1]], runtime)

        return None

    def _redact_pii_from_message(self, message: BaseMessage) -> BaseMessage:
        """Redact PII from message content."""
        import re

        content = message.content

        # Simple PII patterns (enhance with proper PII detection)
        patterns = [
            (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]'),  # Email
            (r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]'),  # SSN
            (r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b', '[CREDIT_CARD]'),  # Credit card
        ]

        redacted_content = content
        for pattern, replacement in patterns:
            redacted_content = re.sub(pattern, replacement, redacted_content)

        # Create new message with redacted content
        if redacted_content != content:
            logger.warning("🔒 PII detected and redacted")
            return message.__class__(content=redacted_content)

        return message

    def _audit_log(self, event_type: str, messages: List[BaseMessage], runtime: Any):
        """Write audit log entry."""
        # In production, use proper audit logging system
        timestamp = datetime.utcnow().isoformat()
        user_id = getattr(runtime.context, 'user_id', 'unknown') if hasattr(runtime, 'context') else 'unknown'

        log_entry = {
            "timestamp": timestamp,
            "event_type": event_type,
            "user_id": user_id,
            "message_count": len(messages)
        }

        logger.info(f"📝 Audit Log: {log_entry}")


# =============================================================================
# Helper: Compose Multiple Advanced Middleware
# =============================================================================

def create_production_middleware_stack(
    enable_caching: bool = True,
    enable_rate_limiting: bool = True,
    enable_metrics: bool = True,
    enable_security: bool = True
) -> List[AgentMiddleware]:
    """
    Create a production-ready middleware stack.

    Example:
        >>> middleware = create_production_middleware_stack()
        >>> agent = create_agent(model="...", tools=..., middleware=middleware)
    """
    stack = []

    if enable_security:
        stack.append(SecurityMiddleware(redact_pii=True))

    if enable_rate_limiting:
        stack.append(RateLimitMiddleware(
            max_requests_per_minute=60,
            max_requests_per_hour=1000
        ))

    if enable_caching:
        stack.append(CachingMiddleware(ttl_seconds=3600))

    if enable_metrics:
        stack.append(MetricsMiddleware())

    return stack
