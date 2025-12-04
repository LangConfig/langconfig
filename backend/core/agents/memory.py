# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Agent Memory System for LangConfig.

Provides agents with explicit memory control through tools, enabling them to:
1. Decide what information is important enough to save
2. Search their memories when needed
3. Update or correct outdated information

This is inspired by LangGraph's LangMem pattern where memory is an active
capability rather than passive storage.

Enhanced with:
- Full LangChain VectorStore abstraction compliance
- Pydantic validation for tool arguments (Guardrails)
- Robust error handling (Resilience)
- UUID-based memory IDs
- Relevance score filtering
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
import uuid

# LangChain imports for VectorStore abstraction and Tool definition
from langchain_core.vectorstores import VectorStore
from langchain_core.documents import Document
from langchain_core.tools import BaseTool, StructuredTool
# Use langchain_core.pydantic_v1 for compatibility with LangChain tools
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MemoryType(str, Enum):
    """Types of memories agents can store."""
    FACT = "fact"  # Factual information about the project
    DECISION = "decision"  # Architectural or design decisions
    PATTERN = "pattern"  # Code patterns or conventions discovered
    LEARNING = "learning"  # Bugs fixed, lessons learned
    CONTEXT = "context"  # Important contextual information
    RELATIONSHIP = "relationship"  # Relationships between components


# =============================================================================
# Pydantic Schemas for Tool Arguments (Guardrails and Documentation)
# =============================================================================

class MemorySaveArgs(BaseModel):
    """Schema for saving information to long-term memory."""
    memory_content: str = Field(
        ...,
        description="The specific information to remember. Be detailed, include context and rationale."
    )
    memory_type: MemoryType = Field(
        MemoryType.FACT,
        description="Category of the memory (e.g., FACT, DECISION, LEARNING)."
    )
    importance: int = Field(
        5,
        description="Importance score (1-10). Higher is more critical.",
        ge=1,
        le=10
    )
    tags: Optional[List[str]] = Field(
        None,
        description="Optional tags for categorization (e.g., ['auth', 'security'])."
    )


class MemorySearchArgs(BaseModel):
    """Schema for searching long-term memory."""
    query: str = Field(
        ...,
        description="The concept you are trying to recall (use natural language)."
    )
    memory_type: Optional[MemoryType] = Field(
        None,
        description="Optional: Filter by memory type."
    )
    min_relevance: float = Field(
        0.75,
        description="Minimum relevance score (0.0-1.0) to return.",
        ge=0.0,
        le=1.0
    )
    limit: int = Field(
        5,
        description="Maximum number of memories to return.",
        ge=1,
        le=15
    )


# =============================================================================
# Agent Memory System
# =============================================================================

class AgentMemorySystem:
    """
    Provides agents with explicit, tool-based control over long-term memory using a VectorStore.

    This creates more intelligent, context-aware agents that build up
    project-specific knowledge over time.

    Example Usage:
        >>> memory_system = AgentMemorySystem(vector_store, project_id=1, agent_id="task_42")
        >>> tools = memory_system.create_memory_tools()
        >>>
        >>> # Tools can be passed directly to LangChain agent
        >>> agent = create_react_agent(llm, tools)
    """

    def __init__(
        self,
        vector_store: VectorStore,
        project_id: int,
        agent_id: str
    ):
        """
        Initialize agent memory system.

        Args:
            vector_store: LangChain VectorStore instance
            project_id: Project this memory belongs to
            agent_id: Agent identifier (e.g., "task_42")
        """
        # Ensure compatibility with LangChain interface
        if not isinstance(vector_store, VectorStore):
            raise TypeError("vector_store must be an instance of langchain_core.vectorstores.VectorStore")

        self.vector_store = vector_store
        self.project_id = project_id
        self.agent_id = agent_id

        # Define the base filter to scope all operations to this project
        self.base_metadata = {
            "project_id": self.project_id,
            "doc_type": "agent_memory"  # Differentiate from standard RAG documents
        }

    def create_memory_tools(self) -> List[BaseTool]:
        """
        Creates a list of StructuredTools for the agent to manage its memory.
        This list is ready to be consumed by the AgentFactory.

        Returns:
            List of BaseTool instances ready for agent binding
        """
        tools = [
            StructuredTool.from_function(
                coro=self.save_to_memory,
                name="memory_store",
                description=(
                    "Save critical information (facts, decisions, patterns, or learnings) to long-term memory. "
                    "Use this immediately when you discover something vital for future reference."
                ),
                args_schema=MemorySaveArgs,
                return_direct=False  # Agent should observe the confirmation message
            ),
            StructuredTool.from_function(
                coro=self.search_memory,
                name="memory_retrieve",
                description=(
                    "Search long-term memory using semantic similarity to recall relevant information. "
                    "Use this before starting tasks to ensure consistency with past work and decisions."
                ),
                args_schema=MemorySearchArgs,
                return_direct=False
            ),
        ]
        return tools

    # =============================================================================
    # Tool Implementations (Agent-facing async methods)
    # =============================================================================

    async def save_to_memory(
        self,
        memory_content: str,
        memory_type: MemoryType = MemoryType.FACT,
        importance: int = 5,
        tags: Optional[List[str]] = None
    ) -> str:
        """
        Save important information to long-term memory.

        Use this when you learn something important that you'll need later.
        Examples:
        - Architectural decisions made
        - Code patterns discovered
        - Bugs fixed and their solutions
        - Important project conventions

        Args:
            memory_content: The information to remember (be specific and clear)
            memory_type: Type of memory (fact, decision, pattern, learning, context)
            importance: How important is this? (1-10, higher = more important)
            tags: Optional tags for categorization (e.g., ["auth", "security"])

        Returns:
            Confirmation message with memory ID
        """
        try:
            memory_id = str(uuid.uuid4())
            metadata = {
                **self.base_metadata,
                "memory_id": memory_id,
                "agent_id": self.agent_id,
                "type": memory_type.value,
                "importance": importance,
                "tags": tags or [],
                "created_at": datetime.utcnow().isoformat(),
            }

            doc = Document(page_content=memory_content, metadata=metadata)

            # Use the standard LangChain asynchronous add_documents method
            await self.vector_store.aadd_documents([doc])

            logger.info(
                f"Agent {self.agent_id} saved memory (ID: {memory_id}, Type: {memory_type.value}, "
                f"Importance: {importance}): {memory_content[:100]}..."
            )

            return (
                f"✓ Memory stored successfully. ID: {memory_id}. "
                f"This {memory_type.value} is now available for retrieval."
            )

        except Exception as e:
            logger.error(f"Failed to save memory: {e}", exc_info=True)
            # Return informative error to the agent (Resilience)
            return (
                f"✗ Error: Failed to save memory due to internal error: {type(e).__name__}. "
                f"The information was NOT saved."
            )

    async def search_memory(
        self,
        query: str,
        memory_type: Optional[MemoryType] = None,
        min_relevance: float = 0.75,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search your long-term memory for relevant information.

        Use this when you need to recall past information, decisions, or learnings.
        The search uses semantic similarity, so you don't need exact keywords.

        Args:
            query: What you're trying to remember (use natural language)
            memory_type: Filter by memory type (fact, decision, pattern, learning)
            min_relevance: Only return memories with relevance >= this value (0.0-1.0)
            limit: Maximum number of memories to return

        Returns:
            List of relevant memories with their content and metadata

        Example:
            search_memory("how do we handle authentication?", memory_type="decision")
            search_memory("bugs related to JWT tokens", tags=["auth", "bug-fix"])
        """
        try:
            logger.debug(
                f"Agent {self.agent_id} searching memory: '{query}' "
                f"(type={memory_type}, min_relevance={min_relevance})"
            )

            # Construct the filter based on scope and optional type
            search_filter = self.base_metadata.copy()
            if memory_type:
                search_filter["type"] = memory_type.value

            # Use LangChain's asynchronous similarity search with scores
            results = await self.vector_store.asimilarity_search_with_relevance_scores(
                query=query,
                k=limit,
                filter=search_filter
            )

            memories = []
            for doc, score in results:
                # Filter results based on the minimum relevance threshold
                if score >= min_relevance:
                    memories.append({
                        "memory_id": doc.metadata.get("memory_id"),
                        "content": doc.page_content,
                        "type": doc.metadata.get("type"),
                        "importance": doc.metadata.get("importance"),
                        "relevance_score": round(score, 3),
                        "tags": doc.metadata.get("tags", []),
                        "created_at": doc.metadata.get("created_at"),
                    })

            if not memories:
                logger.debug("No matching memories found")
                return [{
                    "message": f"No memories found matching the query with relevance > {min_relevance}.",
                    "suggestion": "Try broadening your search or using different keywords."
                }]

            logger.info(f"Found {len(memories)} relevant memories")
            return memories

        except Exception as e:
            logger.error(f"Memory search failed: {e}", exc_info=True)
            return [{
                "error": f"Memory retrieval failed due to internal error: {type(e).__name__}.",
                "message": "Unable to search memories at this time."
            }]

    def get_memory_stats(self) -> Dict[str, Any]:
        """
        Get statistics about agent's memory usage.

        Returns:
            Dictionary with memory statistics
        """
        return {
            "project_id": self.project_id,
            "agent_id": self.agent_id,
            "system_status": "active"
        }


# =============================================================================
# Convenience Functions
# =============================================================================

async def create_memory_aware_agent_tools(
    vector_store: VectorStore,
    project_id: int,
    agent_id: str
) -> List[BaseTool]:
    """
    Convenience function to create memory tools for an agent.

    Args:
        vector_store: LangChain VectorStore instance
        project_id: Project ID
        agent_id: Agent ID (e.g., "task_42")

    Returns:
        List of memory tool instances
    """
    memory_system = AgentMemorySystem(vector_store, project_id, agent_id)
    return memory_system.create_memory_tools()


# =============================================================================
# Example System Prompt for Memory-Aware Agent
# =============================================================================

MEMORY_AWARE_AGENT_PROMPT = """You are an intelligent coding agent with long-term memory capabilities.

MEMORY TOOLS AVAILABLE:
You have access to two memory management tools:

1. **memory_store(memory_content, memory_type, importance, tags)**
   - Save important facts, decisions, patterns, or learnings
   - Use when you discover something valuable for future reference
   - Types: fact, decision, pattern, learning, context, relationship
   - Importance: 1-10 scale (higher = more important)

2. **memory_retrieve(query, memory_type, min_relevance, limit)**
   - Search your memories using natural language
   - Use before implementing to check for existing patterns/decisions
   - Results are ranked by semantic relevance

WHEN TO USE MEMORY TOOLS:

✓ After fixing a bug: Save the bug + solution as learning
✓ When discovering patterns: Save code patterns you notice
✓ After architectural decisions: Save decisions with rationale
✓ Before implementing: Search for relevant past work
✓ When refactoring: Search for similar refactoring patterns
✓ After learning conventions: Save project-specific conventions

MEMORY BEST PRACTICES:

1. Be specific: "We use JWT tokens in httpOnly cookies for auth" > "auth setup"
2. Include context: Why was this decision made? What problem does it solve?
3. Add tags: Make memories easily findable later
4. Set importance: Critical decisions = 9-10, minor facts = 3-5
5. Search first: Before starting work, check if similar work was done

EXAMPLE WORKFLOW:

```
Task: "Add user registration endpoint"

1. memory_retrieve(query="user authentication patterns")
   → Finds: "We use JWT tokens, bcrypt hashing, email validation"

2. Implement registration following past patterns

3. memory_store(
     memory_content="User registration endpoint added at /api/auth/register. Uses bcrypt for password hashing, returns JWT token in httpOnly cookie. Email validation with regex pattern. PostgreSQL user table.",
     memory_type="fact",
     importance=7,
     tags=["auth", "registration", "api"]
   )
```

Your goal: Build up comprehensive project knowledge over time, making you more consistent and context-aware with each task.
"""
