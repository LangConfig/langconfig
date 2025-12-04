# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
LlamaIndex Configuration Service

This module provides centralized configuration for LlamaIndex integration,
including global settings initialization and multi-tenant PGVector store setup.
"""

import logging
import os
from typing import Optional, Union
from urllib.parse import urlparse

from config import settings as app_settings

logger = logging.getLogger(__name__)

# Try to import LlamaIndex - it's optional
try:
    from llama_index.core import Settings
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding
    from llama_index.embeddings.openai import OpenAIEmbedding
    from llama_index.llms.openai import OpenAI
    from llama_index.vector_stores.postgres import PGVectorStore
    LLAMAINDEX_AVAILABLE = True
except ImportError:
    logger.warning("LlamaIndex not available. Vector store features will be disabled.")
    LLAMAINDEX_AVAILABLE = False
    Settings = None
    HuggingFaceEmbedding = None
    OpenAIEmbedding = None
    OpenAI = None
    PGVectorStore = None

# Global flag to track initialization
_initialized = False
_multimodal_enabled = False

def initialize_llama_index_settings(
    litellm_proxy_url: Optional[str] = None, 
    litellm_api_key: Optional[str] = None,
    enable_multimodal: bool = True
):
    """
    Initialize the global LlamaIndex Settings object with optional multimodal support.
    
    Args:
        litellm_proxy_url: URL for the LiteLLM proxy service
        litellm_api_key: API key for LiteLLM proxy authentication
        enable_multimodal: Whether to use multimodal embeddings (requires OpenAI API key)
    """
    global _initialized, _multimodal_enabled
    
    if _initialized:
        logger.info("LlamaIndex settings already initialized")
        return
    
    try:
        # Check if OpenAI API key is available for multimodal embeddings
        openai_api_key = app_settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")

        if enable_multimodal and openai_api_key:
            logger.info("Initializing OpenAI multimodal embedding model")
            Settings.embed_model = OpenAIEmbedding(
                model="text-embedding-3-large",
                dimensions=1024,  # Configurable dimensions for OpenAI embeddings
                api_key=openai_api_key
            )
            _multimodal_enabled = True
            logger.info("Multimodal embeddings enabled with OpenAI text-embedding-3-large")
        else:
            if enable_multimodal:
                logger.warning("Multimodal requested but OpenAI API key not available, falling back to text-only")
            logger.info("Initializing HuggingFace text-only embedding model")
            Settings.embed_model = HuggingFaceEmbedding(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
            _multimodal_enabled = False
        
        # Configure LLM for HyDE if proxy details are provided
        if litellm_proxy_url and litellm_api_key:
            logger.info(f"Configuring LLM with LiteLLM proxy: {litellm_proxy_url}")
            Settings.llm = OpenAI(
                model="gpt-4o-mini",
                api_base=f"{litellm_proxy_url}/v1",
                api_key=litellm_api_key
            )
        else:
            logger.warning("LiteLLM proxy URL or API key not provided. LLM will not be configured for HyDE.")
        
        _initialized = True
        logger.info("LlamaIndex settings initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize LlamaIndex settings: {e}")
        raise


def get_vector_store(project_id: int, embed_dim: Optional[int] = None) -> PGVectorStore:
    """
    Initialize and return a PGVectorStore for the specified project.
    
    This implements multi-tenancy by using project-specific table names,
    ensuring strict data isolation between different projects.
    
    Args:
        project_id: The project identifier for multi-tenant isolation
        embed_dim: Embedding dimension (default: auto-detect based on current model)
        
    Returns:
        PGVectorStore: Configured vector store instance
        
    Raises:
        ValueError: If database URL is invalid or missing
        Exception: If vector store initialization fails
    """
    if not app_settings.database_url:
        raise ValueError("database_url is required but not configured")

    # Auto-detect embedding dimension if not provided
    if embed_dim is None:
        embed_dim = get_embedding_dimension()

    # Parse the database URL to extract connection parameters
    parsed_url = urlparse(app_settings.database_url)
    
    # Ensure we have proper connection details (port defaults to 5432 for PostgreSQL)
    port = parsed_url.port or 5432
    if not all([parsed_url.hostname, parsed_url.username,
                parsed_url.password, parsed_url.path]):
        raise ValueError("Invalid database_url format. Missing required connection parameters.")
    
    # Extract database name (remove leading '/')
    database_name = parsed_url.path.lstrip('/')
    
    # Create project-specific table name for multi-tenancy
    table_name = f"data_project_index_{project_id}"
    
    logger.info(f"Initializing PGVectorStore for project {project_id} with table '{table_name}'")
    
    try:
        vector_store = PGVectorStore.from_params(
            database=database_name,
            host=parsed_url.hostname,
            port=port,
            user=parsed_url.username,
            password=parsed_url.password,
            table_name=table_name,
            embed_dim=embed_dim,
            # Additional configuration for robustness
            hnsw_kwargs={
                "hnsw_m": 16,
                "hnsw_ef_construction": 64,
                "hnsw_ef_search": 40,
            }
        )
        
        logger.info(f"PGVectorStore initialized successfully for project {project_id}")
        return vector_store
        
    except Exception as e:
        logger.error(f"Failed to initialize PGVectorStore for project {project_id}: {e}")
        raise


def ensure_initialized():
    """
    Ensure LlamaIndex settings are initialized before use.

    This is a convenience function that can be called to guarantee
    initialization has occurred before using LlamaIndex components.
    """
    if not _initialized:
        logger.info("LlamaIndex not yet initialized, initializing with default settings")
        # Configure LiteLLM proxy for HyDE support
        litellm_url = os.getenv("LITELLM_PROXY_URL", "http://litellm-proxy:4000")
        litellm_key = os.getenv("LITELLM_API_KEY", "sk-proxy-master-key")
        initialize_llama_index_settings(
            litellm_proxy_url=litellm_url,
            litellm_api_key=litellm_key,
            enable_multimodal=True
        )


def get_embedding_dimension() -> int:
    """
    Get the embedding dimension used by the configured embedding model.
    
    Returns:
        int: Embedding dimension (1024 for multimodal, 384 for text-only)
    """
    global _multimodal_enabled
    return 1024 if _multimodal_enabled else 384


def is_multimodal_enabled() -> bool:
    """
    Check if multimodal embeddings are currently enabled.
    
    Returns:
        bool: True if multimodal embeddings are active
    """
    global _multimodal_enabled
    return _multimodal_enabled


def get_table_name(project_id: int) -> str:
    """
    Generate the table name for a given project ID.
    
    This follows the multi-tenant naming convention used by the vector store.
    
    Args:
        project_id: The project identifier
        
    Returns:
        str: The table name for the project's vector data
    """
    return f"data_project_index_{project_id}"