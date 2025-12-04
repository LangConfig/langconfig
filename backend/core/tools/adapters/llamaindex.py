# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
LlamaIndex Tool Adapter for LangChain Agents

Wraps LlamaIndex retrieval capabilities as LangChain tools so agents
can use the existing LlamaIndex vector store infrastructure.
"""

import logging
from typing import List, Dict, Any, Optional
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from services.codebase_indexer import CodebaseRetriever

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Schemas for Tool Arguments
# =============================================================================

class CodebaseSearchArgs(BaseModel):
    """Schema for searching codebase knowledge."""
    query: str = Field(
        ...,
        description="Natural language query describing what you're looking for in the codebase."
    )
    knowledge_domain: Optional[str] = Field(
        None,
        description="Filter by knowledge domain (e.g., 'langconfig_project', 'galachain_sdk', 'gswap_sdk')"
    )
    file_type: Optional[str] = Field(
        None,
        description="Filter by file extension (e.g., '.py', '.ts', '.md')"
    )
    limit: int = Field(
        5,
        description="Maximum number of results",
        ge=1,
        le=20
    )


# =============================================================================
# LlamaIndex RAG Tools for LangChain Agents
# =============================================================================

class LlamaIndexRAGTools:
    """
    Provides LangChain-compatible tools that use LlamaIndex retrieval.

    This adapter allows agents using LangChain's tool interface to access
    the existing LlamaIndex vector store infrastructure.
    """

    def __init__(self, project_id: int):
        """
        Initialize RAG tools.

        Args:
            project_id: Project ID for vector store access
        """
        self.project_id = project_id
        self.retriever = CodebaseRetriever(project_id=project_id)

    async def search_codebase(
        self,
        query: str,
        knowledge_domain: Optional[str] = None,
        file_type: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search codebase knowledge using LlamaIndex retrieval.

        Args:
            query: Natural language search query
            knowledge_domain: Filter by domain
            file_type: Filter by file extension
            limit: Maximum results

        Returns:
            List of relevant code chunks
        """
        try:
            results = await self.retriever.search(
                query=query,
                knowledge_domain=knowledge_domain,
                file_extension=file_type,
                top_k=limit
            )

            # Format for agent consumption
            if not results or (len(results) == 1 and "error" in results[0]):
                return [{
                    "message": "No codebase knowledge found matching the query.",
                    "suggestion": "Try broadening your search or using different keywords."
                }]

            # Convert scores to relevance (0-1 scale)
            formatted_results = []
            for result in results:
                if "error" not in result:
                    formatted_results.append({
                        "file_path": result.get("file_path"),
                        "file_name": result.get("file_name"),
                        "knowledge_domain": result.get("knowledge_domain"),
                        "code": result.get("code"),
                        "relevance_score": round(result.get("score", 0.0), 3),
                        "chunk_index": result.get("chunk_index", 0),
                    })

            logger.info(f"Found {len(formatted_results)} code chunks for query: {query[:50]}...")
            return formatted_results

        except Exception as e:
            logger.error(f"Codebase search failed: {e}", exc_info=True)
            return [{
                "error": f"Search failed: {type(e).__name__}",
                "message": str(e)
            }]

    def create_tools(self) -> List[BaseTool]:
        """
        Create LangChain tools for agents.

        Returns:
            List of BaseTool instances
        """
        tools = [
            StructuredTool.from_function(
                coro=self.search_codebase,
                name="codebase_search",
                description=(
                    "Search embedded codebase knowledge using semantic similarity. "
                    "Use this to find relevant code examples, API documentation, patterns, "
                    "or architectural decisions from the LangConfig project, GalaChain SDK, or gswap SDK. "
                    "Returns code snippets with file paths and context. "
                    "\n\nAvailable knowledge domains:"
                    "\n- 'langconfig_project': LangConfig system code and architecture"
                    "\n- 'galachain_sdk': GalaChain blockchain SDK"
                    "\n- 'gswap_sdk': gswap SDK for DEX functionality"
                    "\n\nExample: codebase_search(query='How does agent factory create agents?', knowledge_domain='langconfig_project', file_type='.py')"
                ),
                args_schema=CodebaseSearchArgs,
                return_direct=False
            ),
        ]
        return tools


# =============================================================================
# Convenience Function
# =============================================================================

async def create_llamaindex_rag_tools(project_id: int) -> List[BaseTool]:
    """
    Convenience function to create LlamaIndex RAG tools for agents.

    Args:
        project_id: Project ID

    Returns:
        List of RAG tool instances
    """
    rag_tools = LlamaIndexRAGTools(project_id)
    return rag_tools.create_tools()
