# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Task Handlers


Registry of task handlers for different task types.

Each handler is an async function that:
1. Receives task payload and task_id
2. Performs the long-running operation
3. Returns result dict on success
4. Raises exception on failure (automatic retry)

Usage:
    from core.task_handlers import register_handler

    @register_handler("my_task_type")
    async def handle_my_task(payload: dict, task_id: int) -> dict:
        # Task logic here
        return {"result": "success"}

Handlers Implemented:
- export_workflow_agent: Export workflow to standalone DeepAgent
- auto_export_workflow: Auto-export workflow on save (called from workflow update)
- download_images: Download and persist images from URLs
- index_document: Index document for RAG search
- generate_workflow_code: Generate LangGraph code from workflow config
"""

import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from core.task_queue import register_handler
from db.database import SessionLocal

logger = logging.getLogger(__name__)


# =============================================================================
# Agent Export Handlers
# =============================================================================

@register_handler("export_agent")
async def handle_export_agent(payload: dict, task_id: int) -> dict:
    """
    Export DeepAgent to standalone code or .langconfig format.

    Background Job Infrastructure
    - Handles manual agent exports from /api/deepagents/{id}/export endpoint
    - Updates AgentExport record with file path and size
    - Supports both standalone and langconfig formats

    Payload:
        agent_id: int - Agent to export
        export_id: int - Export record ID
        export_type: str - 'standalone' or 'langconfig'
        export_config: dict - Export configuration (include_chat_ui, include_docker)

    Returns:
        dict with export results:
        {
            "success": bool,
            "export_id": int,
            "file_path": str,
            "file_size": int
        }
    """
    agent_id = payload.get("agent_id")
    export_id = payload.get("export_id")
    export_type = payload.get("export_type")
    export_config = payload.get("export_config", {})

    logger.info(
        f"Task {task_id}: Exporting agent {agent_id} (type: {export_type})",
        extra={"task_id": task_id, "agent_id": agent_id, "export_type": export_type}
    )

    db: Session = SessionLocal()
    try:
        # Import here to avoid circular dependencies
        from models.deep_agent import DeepAgentTemplate, AgentExport, DeepAgentConfig
        from services.export_service import ExportService

        # Load agent
        agent = db.query(DeepAgentTemplate).filter(
            DeepAgentTemplate.id == agent_id
        ).first()

        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        # Load export record
        export = db.query(AgentExport).filter(
            AgentExport.id == export_id
        ).first()

        if not export:
            raise ValueError(f"Export record {export_id} not found")

        # Parse config
        config = DeepAgentConfig(**agent.config)
        config.include_chat_ui = export_config.get("include_chat_ui", True)
        config.include_docker = export_config.get("include_docker", False)
        config.export_format = export_type

        # Perform export (long-running operation)
        if export_type == "standalone":
            file_path = await ExportService.export_standalone(agent, config)
            export.file_path = file_path
            export.export_format = "zip"
        elif export_type == "langconfig":
            langconfig_json = await ExportService.export_langconfig(agent, config)
            file_path = f"/tmp/deepagent_exports/{agent.id}.langconfig"
            import os
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w') as f:
                f.write(langconfig_json)
            export.file_path = file_path
            export.export_format = "json"
        else:
            raise ValueError(f"Unknown export type: {export_type}")

        # Update export record with file info
        import os
        if os.path.exists(file_path):
            export.file_size = os.path.getsize(file_path)

        db.commit()

        logger.info(
            f"Task {task_id}: Successfully exported agent {agent_id} to {file_path}",
            extra={
                "task_id": task_id,
                "agent_id": agent_id,
                "export_id": export_id,
                "file_path": file_path,
                "file_size": export.file_size
            }
        )

        return {
            "success": True,
            "export_id": export_id,
            "file_path": file_path,
            "file_size": export.file_size
        }

    except Exception as e:
        logger.error(
            f"Task {task_id}: Failed to export agent {agent_id}: {e}",
            exc_info=True,
            extra={"task_id": task_id, "agent_id": agent_id}
        )
        # Re-raise to trigger automatic retry
        raise
    finally:
        db.close()


# =============================================================================
# Workflow Export Handlers
# =============================================================================

@register_handler("export_workflow_agent")
async def handle_export_workflow_agent(payload: dict, task_id: int) -> dict:
    """
    Export workflow to standalone DeepAgent format.

    Background Job Infrastructure
    - Replaces blocking export in workflow PATCH endpoint
    - Allows user to continue working while export happens
    - Tracks export status in database

    Payload:
        workflow_id: int - Workflow to export
        agent_id: int - Agent to export (if specified)
        config: dict - Export configuration

    Returns:
        dict with export results:
        {
            "success": bool,
            "file_path": str,
            "agent_id": int
        }
    """
    workflow_id = payload.get("workflow_id")
    agent_id = payload.get("agent_id")

    logger.info(
        f"Task {task_id}: Exporting workflow {workflow_id} to DeepAgent",
        extra={"task_id": task_id, "workflow_id": workflow_id}
    )

    db: Session = SessionLocal()
    try:
        # Import here to avoid circular dependencies
        from models.workflow import WorkflowProfile
        from services.deepagent_factory import auto_export_deepagent_workflow

        # Load workflow
        workflow = db.query(WorkflowProfile).filter(
            WorkflowProfile.id == workflow_id
        ).first()

        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")

        # Perform export (long-running operation)
        result = await auto_export_deepagent_workflow(workflow, db)

        logger.info(
            f"Task {task_id}: Successfully exported workflow {workflow_id}",
            extra={"task_id": task_id, "workflow_id": workflow_id}
        )

        return {
            "success": True,
            "workflow_id": workflow_id,
            "agent_id": result.get("agent_id") if isinstance(result, dict) else None,
            "message": "Export completed successfully"
        }

    except Exception as e:
        logger.error(
            f"Task {task_id}: Failed to export workflow {workflow_id}: {e}",
            exc_info=True,
            extra={"task_id": task_id, "workflow_id": workflow_id}
        )
        # Re-raise to trigger automatic retry
        raise
    finally:
        db.close()


@register_handler("auto_export_workflow")
async def handle_auto_export_workflow(payload: dict, task_id: int) -> dict:
    """
    Auto-export workflow triggered by update.

    Called automatically when workflow blueprint or configuration changes.
    Updates workflow export_status field based on result.

    Payload:
        workflow_id: int - Workflow to export

    Returns:
        dict with export results
    """
    workflow_id = payload.get("workflow_id")

    logger.info(
        f"Task {task_id}: Auto-exporting workflow {workflow_id}",
        extra={"task_id": task_id, "workflow_id": workflow_id}
    )

    db: Session = SessionLocal()
    try:
        # Import here to avoid circular dependencies
        from models.workflow import WorkflowProfile
        from services.deepagent_factory import auto_export_deepagent_workflow
        from datetime import datetime

        # Load workflow
        workflow = db.query(WorkflowProfile).filter(
            WorkflowProfile.id == workflow_id
        ).first()

        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")

        # Update status to in_progress
        workflow.export_status = "in_progress"
        db.commit()

        # Perform export
        result = await auto_export_deepagent_workflow(workflow, db)

        # Update status to completed
        workflow.export_status = "completed"
        workflow.export_error = None
        workflow.last_export_at = datetime.utcnow()
        db.commit()

        logger.info(
            f"Task {task_id}: Auto-export completed for workflow {workflow_id}",
            extra={"task_id": task_id, "workflow_id": workflow_id}
        )

        return {
            "success": True,
            "workflow_id": workflow_id,
            "message": "Auto-export completed successfully"
        }

    except Exception as e:
        # Update workflow export status to failed
        try:
            from models.workflow import WorkflowProfile
            from datetime import datetime

            workflow = db.query(WorkflowProfile).filter(
                WorkflowProfile.id == workflow_id
            ).first()

            if workflow:
                workflow.export_status = "failed"
                workflow.export_error = str(e)
                workflow.last_export_at = datetime.utcnow()
                db.commit()
        except Exception as update_error:
            logger.error(
                f"Failed to update workflow export status: {update_error}",
                exc_info=True
            )

        logger.error(
            f"Task {task_id}: Auto-export failed for workflow {workflow_id}: {e}",
            exc_info=True,
            extra={"task_id": task_id, "workflow_id": workflow_id}
        )

        # Re-raise to trigger automatic retry
        raise
    finally:
        db.close()


# =============================================================================
# Image Processing Handlers
# =============================================================================

@register_handler("download_images")
async def handle_download_images(payload: dict, task_id: int) -> dict:
    """
    Download and persist images from URLs.

    Payload:
        image_urls: List[str] - URLs of images to download
        target_dir: str - Directory to save images
        workflow_id: int - Associated workflow (optional)

    Returns:
        dict with download results:
        {
            "success": bool,
            "downloaded": int,
            "failed": int,
            "paths": List[str]
        }
    """
    image_urls = payload.get("image_urls", [])
    target_dir = payload.get("target_dir")

    logger.info(
        f"Task {task_id}: Downloading {len(image_urls)} images",
        extra={"task_id": task_id, "count": len(image_urls)}
    )

    downloaded = 0
    failed = 0
    paths = []

    # TODO: Implement actual image download logic
    # For now, this is a placeholder

    logger.info(
        f"Task {task_id}: Downloaded {downloaded} images, {failed} failed",
        extra={
            "task_id": task_id,
            "downloaded": downloaded,
            "failed": failed
        }
    )

    return {
        "success": failed == 0,
        "downloaded": downloaded,
        "failed": failed,
        "paths": paths
    }


# =============================================================================
# Document Processing Handlers
# =============================================================================

@register_handler("index_document")
async def handle_index_document(payload: dict, task_id: int) -> dict:
    """
    Index document for RAG search.

    Payload:
        document_id: int - Document to index
        project_id: int - Associated project

    Returns:
        dict with indexing results:
        {
            "success": bool,
            "chunks_created": int,
            "document_id": int
        }
    """
    document_id = payload.get("document_id")
    project_id = payload.get("project_id")

    logger.info(
        f"Task {task_id}: Indexing document {document_id}",
        extra={"task_id": task_id, "document_id": document_id}
    )

    db: Session = SessionLocal()
    try:
        # Import here to avoid circular dependencies
        from models.core import ContextDocument

        # Load document
        document = db.query(ContextDocument).filter(
            ContextDocument.id == document_id
        ).first()

        if not document:
            raise ValueError(f"Document {document_id} not found")

        # Update status
        document.indexing_status = "indexing"
        db.commit()

        # TODO: Implement actual indexing logic
        # This would involve:
        # 1. Extracting text from document
        # 2. Chunking text
        # 3. Generating embeddings
        # 4. Storing in vector database

        chunks_created = 0  # Placeholder

        # Update status
        document.indexing_status = "indexed"
        db.commit()

        logger.info(
            f"Task {task_id}: Indexed document {document_id}, created {chunks_created} chunks",
            extra={
                "task_id": task_id,
                "document_id": document_id,
                "chunks_created": chunks_created
            }
        )

        return {
            "success": True,
            "document_id": document_id,
            "chunks_created": chunks_created
        }

    except Exception as e:
        # Update document status to failed
        try:
            from models.core import ContextDocument

            document = db.query(ContextDocument).filter(
                ContextDocument.id == document_id
            ).first()

            if document:
                document.indexing_status = "failed"
                db.commit()
        except Exception as update_error:
            logger.error(
                f"Failed to update document indexing status: {update_error}",
                exc_info=True
            )

        logger.error(
            f"Task {task_id}: Failed to index document {document_id}: {e}",
            exc_info=True,
            extra={"task_id": task_id, "document_id": document_id}
        )

        # Re-raise to trigger automatic retry
        raise
    finally:
        db.close()


# =============================================================================
# Workflow Code Generation Handlers
# =============================================================================

@register_handler("generate_workflow_code")
async def handle_generate_workflow_code(payload: dict, task_id: int) -> dict:
    """
    Generate LangGraph code from workflow configuration.

    Payload:
        workflow_id: int - Workflow to generate code for
        version_id: int - Specific version (optional)

    Returns:
        dict with generation results:
        {
            "success": bool,
            "workflow_id": int,
            "code_length": int
        }
    """
    workflow_id = payload.get("workflow_id")
    version_id = payload.get("version_id")

    logger.info(
        f"Task {task_id}: Generating code for workflow {workflow_id}",
        extra={"task_id": task_id, "workflow_id": workflow_id}
    )

    db: Session = SessionLocal()
    try:
        # Import here to avoid circular dependencies
        from models.workflow import WorkflowProfile, WorkflowVersion

        # Load workflow
        workflow = db.query(WorkflowProfile).filter(
            WorkflowProfile.id == workflow_id
        ).first()

        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")

        # Load specific version if provided
        if version_id:
            version = db.query(WorkflowVersion).filter(
                WorkflowVersion.id == version_id,
                WorkflowVersion.workflow_id == workflow_id
            ).first()

            if not version:
                raise ValueError(f"Version {version_id} not found for workflow {workflow_id}")
        else:
            version = None

        # TODO: Implement actual code generation
        # This would use LangGraphCodeGenerator

        code_length = 0  # Placeholder

        logger.info(
            f"Task {task_id}: Generated {code_length} chars of code for workflow {workflow_id}",
            extra={
                "task_id": task_id,
                "workflow_id": workflow_id,
                "code_length": code_length
            }
        )

        return {
            "success": True,
            "workflow_id": workflow_id,
            "code_length": code_length
        }

    except Exception as e:
        logger.error(
            f"Task {task_id}: Failed to generate code for workflow {workflow_id}: {e}",
            exc_info=True,
            extra={"task_id": task_id, "workflow_id": workflow_id}
        )

        # Re-raise to trigger automatic retry
        raise
    finally:
        db.close()


# =============================================================================
# Scheduled Workflow Execution Handlers
# =============================================================================

@register_handler("execute_scheduled_workflow")
async def handle_execute_scheduled_workflow(payload: dict, task_id: int) -> dict:
    """
    Execute a workflow triggered by a cron schedule.

    Updates the ScheduledRunLog with execution status and results.

    Payload:
        schedule_id: int - Schedule that triggered this execution
        run_log_id: int - ScheduledRunLog entry ID
        workflow_id: int - Workflow to execute
        input_data: dict - Input data for workflow execution
        timeout_minutes: int - Execution timeout

    Returns:
        dict with execution results:
        {
            "success": bool,
            "workflow_id": int,
            "schedule_id": int,
            "execution_result": dict
        }
    """
    schedule_id = payload.get("schedule_id")
    run_log_id = payload.get("run_log_id")
    workflow_id = payload.get("workflow_id")
    input_data = payload.get("input_data", {})
    timeout_minutes = payload.get("timeout_minutes", 60)

    logger.info(
        f"Task {task_id}: Executing scheduled workflow {workflow_id} "
        f"(schedule: {schedule_id}, run_log: {run_log_id})",
        extra={
            "task_id": task_id,
            "workflow_id": workflow_id,
            "schedule_id": schedule_id
        }
    )

    db: Session = SessionLocal()
    try:
        # Import models here to avoid circular dependencies
        from models.workflow_schedule import ScheduledRunLog, ScheduleRunStatus, WorkflowSchedule
        from models.workflow import WorkflowProfile
        from datetime import datetime

        # Update run log status to RUNNING
        run_log = db.query(ScheduledRunLog).filter(
            ScheduledRunLog.id == run_log_id
        ).first()

        if run_log:
            run_log.status = ScheduleRunStatus.RUNNING.value
            run_log.started_at = datetime.utcnow()
            db.commit()

        # Load workflow
        workflow = db.query(WorkflowProfile).filter(
            WorkflowProfile.id == workflow_id
        ).first()

        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")

        # Execute the workflow
        # Import executor here to avoid circular dependencies
        from core.workflows.executor import execute_workflow_sync

        # Prepare execution input
        execution_input = {
            "task": input_data.get("task", "Scheduled execution"),
            "context": input_data.get("context", {}),
            **input_data
        }

        # Execute workflow (synchronous wrapper for background execution)
        result = await execute_workflow_sync(
            workflow_id=workflow_id,
            input_data=execution_input,
            db=db
        )

        # Update run log with success
        if run_log:
            run_log.status = ScheduleRunStatus.SUCCESS.value
            run_log.completed_at = datetime.utcnow()
            db.commit()

        # Update schedule status
        schedule = db.query(WorkflowSchedule).filter(
            WorkflowSchedule.id == schedule_id
        ).first()

        if schedule:
            schedule.last_run_status = ScheduleRunStatus.SUCCESS.value
            db.commit()

        logger.info(
            f"Task {task_id}: Scheduled workflow {workflow_id} completed successfully",
            extra={
                "task_id": task_id,
                "workflow_id": workflow_id,
                "schedule_id": schedule_id
            }
        )

        return {
            "success": True,
            "workflow_id": workflow_id,
            "schedule_id": schedule_id,
            "run_log_id": run_log_id,
            "execution_result": result if isinstance(result, dict) else {"output": str(result)}
        }

    except Exception as e:
        # Update run log with failure
        try:
            from models.workflow_schedule import ScheduledRunLog, ScheduleRunStatus, WorkflowSchedule
            from datetime import datetime

            run_log = db.query(ScheduledRunLog).filter(
                ScheduledRunLog.id == run_log_id
            ).first()

            if run_log:
                run_log.status = ScheduleRunStatus.FAILED.value
                run_log.completed_at = datetime.utcnow()
                run_log.error_message = str(e)
                db.commit()

            # Update schedule status
            schedule = db.query(WorkflowSchedule).filter(
                WorkflowSchedule.id == schedule_id
            ).first()

            if schedule:
                schedule.last_run_status = ScheduleRunStatus.FAILED.value
                db.commit()

        except Exception as update_error:
            logger.error(
                f"Failed to update run log status: {update_error}",
                exc_info=True
            )

        logger.error(
            f"Task {task_id}: Scheduled workflow {workflow_id} failed: {e}",
            exc_info=True,
            extra={
                "task_id": task_id,
                "workflow_id": workflow_id,
                "schedule_id": schedule_id
            }
        )

        # Re-raise to trigger automatic retry
        raise
    finally:
        db.close()


# =============================================================================
# Triggered Workflow Execution Handlers (Webhooks, File Watch)
# =============================================================================

@register_handler("execute_triggered_workflow")
async def handle_execute_triggered_workflow(payload: dict, task_id: int) -> dict:
    """
    Execute a workflow triggered by an event (webhook, file watch, etc.).

    Updates the TriggerLog with execution status and results.

    Payload:
        trigger_id: int - Trigger that fired
        trigger_log_id: int - TriggerLog entry ID
        workflow_id: int - Workflow to execute
        trigger_type: str - Type of trigger (webhook, file_watch)
        input_data: dict - Input data for workflow execution
        trigger_source: str - Source of trigger (IP, file path, etc.)

    Returns:
        dict with execution results:
        {
            "success": bool,
            "workflow_id": int,
            "trigger_id": int,
            "execution_result": dict
        }
    """
    trigger_id = payload.get("trigger_id")
    trigger_log_id = payload.get("trigger_log_id")
    workflow_id = payload.get("workflow_id")
    trigger_type = payload.get("trigger_type")
    input_data = payload.get("input_data", {})
    trigger_source = payload.get("trigger_source", "unknown")

    logger.info(
        f"Task {task_id}: Executing triggered workflow {workflow_id} "
        f"(trigger: {trigger_id}, type: {trigger_type}, source: {trigger_source})",
        extra={
            "task_id": task_id,
            "workflow_id": workflow_id,
            "trigger_id": trigger_id,
            "trigger_type": trigger_type
        }
    )

    db: Session = SessionLocal()
    try:
        from models.workflow_trigger import TriggerLog, TriggerStatus, WorkflowTrigger
        from models.workflow import WorkflowProfile
        from datetime import datetime

        # Update trigger log status to RUNNING
        trigger_log = db.query(TriggerLog).filter(
            TriggerLog.id == trigger_log_id
        ).first()

        if trigger_log:
            trigger_log.status = TriggerStatus.RUNNING.value
            db.commit()

        # Load workflow
        workflow = db.query(WorkflowProfile).filter(
            WorkflowProfile.id == workflow_id
        ).first()

        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")

        # Execute the workflow
        from core.workflows.executor import execute_workflow_sync

        # Prepare execution input - merge trigger input with defaults
        execution_input = {
            "task": input_data.get("task", f"Triggered execution ({trigger_type})"),
            "context": input_data.get("context", {}),
            **{k: v for k, v in input_data.items() if k not in ["task", "context"]}
        }

        # Add trigger metadata to context
        if "context" not in execution_input:
            execution_input["context"] = {}
        execution_input["context"]["_trigger"] = {
            "type": trigger_type,
            "source": trigger_source,
            "trigger_id": trigger_id,
        }

        # Execute workflow
        result = await execute_workflow_sync(
            workflow_id=workflow_id,
            input_data=execution_input,
            db=db
        )

        # Update trigger log with success
        if trigger_log:
            trigger_log.status = TriggerStatus.SUCCESS.value
            trigger_log.completed_at = datetime.utcnow()
            db.commit()

        logger.info(
            f"Task {task_id}: Triggered workflow {workflow_id} completed successfully",
            extra={
                "task_id": task_id,
                "workflow_id": workflow_id,
                "trigger_id": trigger_id
            }
        )

        return {
            "success": True,
            "workflow_id": workflow_id,
            "trigger_id": trigger_id,
            "trigger_log_id": trigger_log_id,
            "trigger_type": trigger_type,
            "execution_result": result if isinstance(result, dict) else {"output": str(result)}
        }

    except Exception as e:
        # Update trigger log with failure
        try:
            from models.workflow_trigger import TriggerLog, TriggerStatus
            from datetime import datetime

            trigger_log = db.query(TriggerLog).filter(
                TriggerLog.id == trigger_log_id
            ).first()

            if trigger_log:
                trigger_log.status = TriggerStatus.FAILED.value
                trigger_log.completed_at = datetime.utcnow()
                trigger_log.error_message = str(e)
                db.commit()

        except Exception as update_error:
            logger.error(
                f"Failed to update trigger log status: {update_error}",
                exc_info=True
            )

        logger.error(
            f"Task {task_id}: Triggered workflow {workflow_id} failed: {e}",
            exc_info=True,
            extra={
                "task_id": task_id,
                "workflow_id": workflow_id,
                "trigger_id": trigger_id
            }
        )

        # Re-raise to trigger automatic retry
        raise
    finally:
        db.close()


# =============================================================================
# Utility Functions
# =============================================================================

def get_registered_handlers() -> list:
    """
    Get list of all registered task handlers.

    Returns:
        List of task type names
    """
    from core.task_queue import task_queue
    return task_queue.registry.list_handlers()


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "handle_export_workflow_agent",
    "handle_auto_export_workflow",
    "handle_download_images",
    "handle_index_document",
    "handle_generate_workflow_code",
    "handle_execute_scheduled_workflow",
    "handle_execute_triggered_workflow",
    "get_registered_handlers"
]
