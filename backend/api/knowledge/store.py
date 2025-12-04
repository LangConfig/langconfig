# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Store Management API

Endpoints for managing LangGraph Store (long-term memory) data.
Allows viewing, adding, and deleting memory items for workflows.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from db.database import get_db
from models.workflow import WorkflowProfile
from core.workflows.checkpointing.manager import get_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/workflows", tags=["store"])


# Pydantic Schemas
class StoreItemCreate(BaseModel):
    """Schema for creating/updating a Store item."""
    namespace: List[str] = Field(..., description="Namespace tuple (e.g., ['workflow', '123'])")
    key: str = Field(..., description="Item key")
    value: Dict[str, Any] = Field(..., description="Item value (any JSON-serializable data)")


class StoreItemResponse(BaseModel):
    """Schema for Store item response."""
    namespace: List[str]
    key: str
    value: Dict[str, Any]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class StoreItemBatch(BaseModel):
    """Schema for batch operations."""
    items: List[StoreItemCreate]


# Endpoints

@router.get("/{workflow_id}/memory", response_model=List[StoreItemResponse])
async def list_workflow_memory(
    workflow_id: int,
    namespace_filter: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    List all memory items for a workflow.

    Optionally filter by namespace prefix.
    """
    # Verify workflow exists
    workflow = db.query(WorkflowProfile).filter(WorkflowProfile.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Get Store instance
    store = get_store()
    if not store:
        raise HTTPException(
            status_code=503,
            detail="Store not available. Long-term memory is not initialized."
        )

    try:
        # Search for items with workflow namespace
        namespace = ("workflow", str(workflow_id))

        # Use Store's search API to list items
        # Note: LangGraph Store doesn't have a direct "list all" method,
        # so we need to search with a pattern
        items = []

        # Store search returns items matching namespace prefix
        search_results = await store.asearch(namespace)

        for item in search_results:
            items.append({
                "namespace": list(item.namespace),
                "key": item.key,
                "value": item.value,
                "created_at": item.created_at.isoformat() if hasattr(item, 'created_at') and item.created_at else None,
                "updated_at": item.updated_at.isoformat() if hasattr(item, 'updated_at') and item.updated_at else None
            })

        logger.info(f"Retrieved {len(items)} memory items for workflow {workflow_id}")
        return items

    except Exception as e:
        logger.error(f"Error listing workflow memory: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list memory items: {str(e)}")


@router.get("/{workflow_id}/memory/{key}", response_model=StoreItemResponse)
async def get_workflow_memory_item(
    workflow_id: int,
    key: str,
    db: Session = Depends(get_db)
):
    """
    Get a specific memory item for a workflow.
    """
    # Verify workflow exists
    workflow = db.query(WorkflowProfile).filter(WorkflowProfile.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Get Store instance
    store = get_store()
    if not store:
        raise HTTPException(
            status_code=503,
            detail="Store not available. Long-term memory is not initialized."
        )

    try:
        # Get item from Store
        namespace = ("workflow", str(workflow_id))
        item = await store.aget(namespace, key)

        if not item:
            raise HTTPException(status_code=404, detail="Memory item not found")

        return {
            "namespace": list(namespace),
            "key": key,
            "value": item.value,
            "created_at": item.created_at.isoformat() if hasattr(item, 'created_at') and item.created_at else None,
            "updated_at": item.updated_at.isoformat() if hasattr(item, 'updated_at') and item.updated_at else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting memory item: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get memory item: {str(e)}")


@router.post("/{workflow_id}/memory", response_model=StoreItemResponse, status_code=201)
async def create_workflow_memory_item(
    workflow_id: int,
    item: StoreItemCreate,
    db: Session = Depends(get_db)
):
    """
    Create or update a memory item for a workflow.

    This endpoint is used for:
    - Manual memory injection
    - HITL memory injection during paused workflows
    - Pre-seeding workflow memory
    """
    # Verify workflow exists
    workflow = db.query(WorkflowProfile).filter(WorkflowProfile.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Get Store instance
    store = get_store()
    if not store:
        raise HTTPException(
            status_code=503,
            detail="Store not available. Long-term memory is not initialized."
        )

    try:
        # Override namespace to ensure workflow scoping
        namespace = ("workflow", str(workflow_id))

        # Store the item
        await store.aput(namespace, item.key, item.value)

        logger.info(f"Created memory item for workflow {workflow_id}: {item.key}")

        # Return the created item
        stored_item = await store.aget(namespace, item.key)

        return {
            "namespace": list(namespace),
            "key": item.key,
            "value": stored_item.value if stored_item else item.value,
            "created_at": stored_item.created_at.isoformat() if stored_item and hasattr(stored_item, 'created_at') and stored_item.created_at else None,
            "updated_at": stored_item.updated_at.isoformat() if stored_item and hasattr(stored_item, 'updated_at') and stored_item.updated_at else None
        }

    except Exception as e:
        logger.error(f"Error creating memory item: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create memory item: {str(e)}")


@router.post("/{workflow_id}/memory/batch", status_code=201)
async def create_workflow_memory_batch(
    workflow_id: int,
    batch: StoreItemBatch,
    db: Session = Depends(get_db)
):
    """
    Create or update multiple memory items at once.

    Useful for HITL memory injection where multiple items need to be added.
    """
    # Verify workflow exists
    workflow = db.query(WorkflowProfile).filter(WorkflowProfile.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Get Store instance
    store = get_store()
    if not store:
        raise HTTPException(
            status_code=503,
            detail="Store not available. Long-term memory is not initialized."
        )

    try:
        namespace = ("workflow", str(workflow_id))
        created_count = 0

        for item in batch.items:
            await store.aput(namespace, item.key, item.value)
            created_count += 1

        logger.info(f"Created {created_count} memory items for workflow {workflow_id}")

        return {
            "success": True,
            "created": created_count,
            "message": f"Successfully created {created_count} memory items"
        }

    except Exception as e:
        logger.error(f"Error creating memory batch: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create memory items: {str(e)}")


@router.delete("/{workflow_id}/memory/{key}", status_code=204)
async def delete_workflow_memory_item(
    workflow_id: int,
    key: str,
    db: Session = Depends(get_db)
):
    """
    Delete a specific memory item.
    """
    # Verify workflow exists
    workflow = db.query(WorkflowProfile).filter(WorkflowProfile.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Get Store instance
    store = get_store()
    if not store:
        raise HTTPException(
            status_code=503,
            detail="Store not available. Long-term memory is not initialized."
        )

    try:
        namespace = ("workflow", str(workflow_id))

        # Delete the item
        await store.adelete(namespace, key)

        logger.info(f"Deleted memory item for workflow {workflow_id}: {key}")
        return None

    except Exception as e:
        logger.error(f"Error deleting memory item: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete memory item: {str(e)}")


@router.delete("/{workflow_id}/memory", status_code=204)
async def clear_workflow_memory(
    workflow_id: int,
    db: Session = Depends(get_db)
):
    """
    Clear ALL memory items for a workflow.

    Use with caution - this deletes all long-term memory for the workflow.
    """
    # Verify workflow exists
    workflow = db.query(WorkflowProfile).filter(WorkflowProfile.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Get Store instance
    store = get_store()
    if not store:
        raise HTTPException(
            status_code=503,
            detail="Store not available. Long-term memory is not initialized."
        )

    try:
        namespace = ("workflow", str(workflow_id))

        # Search for all items and delete them
        items = await store.asearch(namespace)
        deleted_count = 0

        for item in items:
            await store.adelete(namespace, item.key)
            deleted_count += 1

        logger.info(f"Cleared {deleted_count} memory items for workflow {workflow_id}")
        return None

    except Exception as e:
        logger.error(f"Error clearing workflow memory: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear memory: {str(e)}")
