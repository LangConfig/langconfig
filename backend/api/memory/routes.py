# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Agent Memory Management API

Provides endpoints to view, search, and manage agent memories stored in the vector database.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from db.database import get_db
from services.llama_config import get_vector_store
from core.agents.memory import MemoryType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memory", tags=["memory"])


# Response Models
class MemoryItem(BaseModel):
    """A single memory item"""
    memory_id: str
    content: str
    memory_type: str
    importance: int
    tags: List[str]
    agent_id: str
    created_at: str

    class Config:
        from_attributes = True


class MemorySearchResponse(BaseModel):
    """Response for memory search"""
    memories: List[MemoryItem]
    total: int
    query: Optional[str] = None


class MemoryStatsResponse(BaseModel):
    """Memory statistics for a project"""
    total_memories: int
    by_type: dict
    by_agent: dict
    avg_importance: float


# Request Models
class MemorySearchRequest(BaseModel):
    """Request to search memories"""
    query: str = Field(..., description="Search query")
    k: int = Field(5, ge=1, le=50, description="Number of results")
    min_importance: Optional[int] = Field(None, ge=1, le=10)
    memory_types: Optional[List[str]] = None
    tags: Optional[List[str]] = None


@router.get("/projects/{project_id}/memories", response_model=MemorySearchResponse)
async def list_project_memories(
    project_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    memory_type: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    min_importance: Optional[int] = Query(None, ge=1, le=10),
    db: Session = Depends(get_db)
):
    """
    List all memories for a project with optional filtering.

    This queries the vector database directly to retrieve stored memories.
    """
    try:
        vector_store = get_vector_store(project_id)

        # Query the underlying PostgreSQL table directly for listing
        # (LangChain's PGVectorStore doesn't have a native "list all" method)
        from sqlalchemy import create_engine, text
        from config import app_settings

        engine = create_engine(app_settings.database_url)
        table_name = f"data_project_index_{project_id}"

        # Build query with filters
        query_parts = [f"SELECT * FROM {table_name}"]
        query_parts.append("WHERE metadata->>'doc_type' = 'agent_memory'")

        if memory_type:
            query_parts.append(f"AND metadata->>'type' = '{memory_type}'")
        if agent_id:
            query_parts.append(f"AND metadata->>'agent_id' = '{agent_id}'")
        if min_importance:
            query_parts.append(f"AND CAST(metadata->>'importance' AS INTEGER) >= {min_importance}")

        query_parts.append(f"ORDER BY metadata->>'created_at' DESC")
        query_parts.append(f"LIMIT {limit} OFFSET {offset}")

        query_str = " ".join(query_parts)

        with engine.connect() as conn:
            result = conn.execute(text(query_str))
            rows = result.fetchall()

            memories = []
            for row in rows:
                metadata = row.metadata if hasattr(row, 'metadata') else {}
                memories.append(MemoryItem(
                    memory_id=metadata.get('memory_id', ''),
                    content=row.text if hasattr(row, 'text') else '',
                    memory_type=metadata.get('type', 'unknown'),
                    importance=int(metadata.get('importance', 5)),
                    tags=metadata.get('tags', []),
                    agent_id=metadata.get('agent_id', ''),
                    created_at=metadata.get('created_at', '')
                ))

            # Get total count
            count_query = f"SELECT COUNT(*) FROM {table_name} WHERE metadata->>'doc_type' = 'agent_memory'"
            count_result = conn.execute(text(count_query))
            total = count_result.scalar()

        return MemorySearchResponse(
            memories=memories,
            total=total or 0
        )

    except Exception as e:
        logger.error(f"Failed to list memories for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve memories: {str(e)}")


@router.post("/projects/{project_id}/memories/search", response_model=MemorySearchResponse)
async def search_project_memories(
    project_id: int,
    search_request: MemorySearchRequest,
    db: Session = Depends(get_db)
):
    """
    Semantic search through project memories using vector similarity.

    This uses the same search mechanism that agents use with memory_retrieve.
    """
    try:
        vector_store = get_vector_store(project_id)

        # Build metadata filter
        metadata_filter = {"doc_type": "agent_memory"}
        if search_request.memory_types:
            metadata_filter["type"] = {"$in": search_request.memory_types}
        if search_request.tags:
            metadata_filter["tags"] = {"$in": search_request.tags}
        if search_request.min_importance:
            metadata_filter["importance"] = {"$gte": search_request.min_importance}

        # Perform similarity search
        from langchain_core.documents import Document
        results = await vector_store.asimilarity_search(
            query=search_request.query,
            k=search_request.k,
            filter=metadata_filter
        )

        memories = []
        for doc in results:
            metadata = doc.metadata
            memories.append(MemoryItem(
                memory_id=metadata.get('memory_id', ''),
                content=doc.page_content,
                memory_type=metadata.get('type', 'unknown'),
                importance=int(metadata.get('importance', 5)),
                tags=metadata.get('tags', []),
                agent_id=metadata.get('agent_id', ''),
                created_at=metadata.get('created_at', '')
            ))

        return MemorySearchResponse(
            memories=memories,
            total=len(memories),
            query=search_request.query
        )

    except Exception as e:
        logger.error(f"Failed to search memories for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Memory search failed: {str(e)}")


@router.get("/projects/{project_id}/memories/stats", response_model=MemoryStatsResponse)
async def get_memory_stats(
    project_id: int,
    db: Session = Depends(get_db)
):
    """
    Get statistics about memories stored for a project.
    """
    try:
        from sqlalchemy import create_engine, text
        from config import app_settings

        engine = create_engine(app_settings.database_url)
        table_name = f"data_project_index_{project_id}"

        with engine.connect() as conn:
            # Total memories
            total_query = f"SELECT COUNT(*) FROM {table_name} WHERE metadata->>'doc_type' = 'agent_memory'"
            total = conn.execute(text(total_query)).scalar() or 0

            # By type
            type_query = f"""
                SELECT metadata->>'type' as type, COUNT(*) as count
                FROM {table_name}
                WHERE metadata->>'doc_type' = 'agent_memory'
                GROUP BY metadata->>'type'
            """
            type_results = conn.execute(text(type_query))
            by_type = {row[0]: row[1] for row in type_results}

            # By agent
            agent_query = f"""
                SELECT metadata->>'agent_id' as agent_id, COUNT(*) as count
                FROM {table_name}
                WHERE metadata->>'doc_type' = 'agent_memory'
                GROUP BY metadata->>'agent_id'
            """
            agent_results = conn.execute(text(agent_query))
            by_agent = {row[0]: row[1] for row in agent_results}

            # Average importance
            avg_query = f"""
                SELECT AVG(CAST(metadata->>'importance' AS FLOAT))
                FROM {table_name}
                WHERE metadata->>'doc_type' = 'agent_memory'
            """
            avg_importance = conn.execute(text(avg_query)).scalar() or 0.0

        return MemoryStatsResponse(
            total_memories=total,
            by_type=by_type,
            by_agent=by_agent,
            avg_importance=float(avg_importance)
        )

    except Exception as e:
        logger.error(f"Failed to get memory stats for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve stats: {str(e)}")


@router.delete("/projects/{project_id}/memories/{memory_id}")
async def delete_memory(
    project_id: int,
    memory_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete a specific memory by ID.
    """
    try:
        from sqlalchemy import create_engine, text
        from config import app_settings

        engine = create_engine(app_settings.database_url)
        table_name = f"data_project_index_{project_id}"

        with engine.connect() as conn:
            delete_query = f"""
                DELETE FROM {table_name}
                WHERE metadata->>'memory_id' = '{memory_id}'
                AND metadata->>'doc_type' = 'agent_memory'
            """
            result = conn.execute(text(delete_query))
            conn.commit()

            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Memory not found")

        return {"message": "Memory deleted successfully", "memory_id": memory_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete memory {memory_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete memory: {str(e)}")


@router.delete("/projects/{project_id}/memories")
async def clear_project_memories(
    project_id: int,
    agent_id: Optional[str] = Query(None, description="Clear only memories from specific agent"),
    db: Session = Depends(get_db)
):
    """
    Clear all memories for a project (or specific agent).
    Use with caution - this is irreversible!
    """
    try:
        from sqlalchemy import create_engine, text
        from config import app_settings

        engine = create_engine(app_settings.database_url)
        table_name = f"data_project_index_{project_id}"

        with engine.connect() as conn:
            if agent_id:
                delete_query = f"""
                    DELETE FROM {table_name}
                    WHERE metadata->>'agent_id' = '{agent_id}'
                    AND metadata->>'doc_type' = 'agent_memory'
                """
                message = f"Cleared memories for agent {agent_id}"
            else:
                delete_query = f"""
                    DELETE FROM {table_name}
                    WHERE metadata->>'doc_type' = 'agent_memory'
                """
                message = "Cleared all project memories"

            result = conn.execute(text(delete_query))
            conn.commit()
            deleted_count = result.rowcount

        return {
            "message": message,
            "deleted_count": deleted_count
        }

    except Exception as e:
        logger.error(f"Failed to clear memories for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear memories: {str(e)}")
