# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Node-level caching configuration for LangGraph workflows.

LangGraph 1.0 supports CachePolicy per node -- the runtime skips re-execution
if the same input was seen within the TTL window.  The CachePolicy is passed to
``StateGraph.add_node(cache_policy=...)`` and a cache backend (e.g.
InMemoryCache) is passed to ``StateGraph.compile(cache=...)``.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_CACHE_TTL = 300

# -- CachePolicy lives in langgraph.types (not langgraph.cache) -----------
try:
    from langgraph.types import CachePolicy
    CACHE_POLICY_AVAILABLE = True
except ImportError:
    CACHE_POLICY_AVAILABLE = False
    logger.warning("langgraph.types.CachePolicy not available. Node cache policies disabled.")

# -- Cache backends live in langgraph.cache.{memory,redis} ----------------
try:
    from langgraph.cache.memory import InMemoryCache
    CACHE_BACKEND_AVAILABLE = True
except ImportError:
    CACHE_BACKEND_AVAILABLE = False
    logger.warning("langgraph.cache.memory.InMemoryCache not available. Cache backends disabled.")

try:
    from langgraph.cache.redis import RedisCache
    REDIS_CACHE_AVAILABLE = True
except ImportError:
    REDIS_CACHE_AVAILABLE = False

# Unified flag: both policy *and* backend must be importable for caching to
# be considered available.
CACHE_AVAILABLE = CACHE_POLICY_AVAILABLE and CACHE_BACKEND_AVAILABLE


def build_cache_policy(node_config: Dict[str, Any]) -> Optional[Any]:
    """Build a CachePolicy from a node's config dict.

    Returns ``None`` when caching is disabled (either explicitly via
    ``cache_enabled: False`` or because the LangGraph cache API is not
    installed).

    The returned object is intended to be passed to
    ``StateGraph.add_node(..., cache_policy=policy)``.
    """
    if not CACHE_POLICY_AVAILABLE:
        return None
    if not node_config.get("cache_enabled", False):
        return None
    ttl = node_config.get("cache_ttl", DEFAULT_CACHE_TTL)
    return CachePolicy(ttl=ttl)


def get_cache_backend(settings: Dict[str, Any]) -> Optional[Any]:
    """Return a cache backend instance based on *settings*.

    Defaults to ``InMemoryCache`` when no ``cache_backend`` key is
    specified.  Pass ``cache_backend: "disabled"`` to explicitly turn off
    caching.  The returned object is intended to be passed to
    ``StateGraph.compile(cache=backend)``.
    """
    if not CACHE_BACKEND_AVAILABLE:
        return None
    backend = settings.get("cache_backend", "memory")
    if backend == "disabled":
        return None
    if backend == "redis" and REDIS_CACHE_AVAILABLE:
        redis_url = settings.get("cache_redis_url", "redis://localhost:6379")
        return RedisCache(url=redis_url)
    return InMemoryCache()
