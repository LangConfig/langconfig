# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Hermes draft validation and approval-gated apply operations."""

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.versioning import check_version_conflict
from models.custom_tool import CustomTool, ToolTemplateType, ToolType
from models.deep_agent import DeepAgentConfig, DeepAgentTemplate
from models.hermes import HermesDraft
from models.workflow import WorkflowProfile, WorkflowStrategy
from models.workflow_schedule import WorkflowSchedule
from models.workflow_trigger import TriggerType, WorkflowTrigger


ARTIFACT_ALIASES = {
    "workflow": "workflow",
    "workflow_profile": "workflow",
    "agent": "deep_agent",
    "deep_agent": "deep_agent",
    "deepagent": "deep_agent",
    "tool": "custom_tool",
    "custom_tool": "custom_tool",
    "schedule": "schedule",
    "trigger": "trigger",
}


class HermesValidationError(ValueError):
    """Raised for validation failures that should be shown to Hermes/users."""


class HermesApplyError(RuntimeError):
    """Raised when a validated draft cannot be applied."""


def normalize_artifact_type(artifact_type: str) -> str:
    key = (artifact_type or "").strip().lower()
    if key not in ARTIFACT_ALIASES:
        raise HermesValidationError(
            f"Unsupported artifact_type '{artifact_type}'. "
            f"Supported: {sorted(set(ARTIFACT_ALIASES.values()))}"
        )
    return ARTIFACT_ALIASES[key]


def serialize_draft(draft: HermesDraft) -> Dict[str, Any]:
    return {
        "id": draft.id,
        "project_id": draft.project_id,
        "artifact_type": draft.artifact_type,
        "title": draft.title,
        "payload_json": draft.payload_json or {},
        "status": draft.status,
        "validation_result": draft.validation_result or {},
        "source_session_id": draft.source_session_id,
        "codex_run_id": draft.codex_run_id,
        "apply_result": draft.apply_result or {},
        "rejection_reason": draft.rejection_reason,
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
    }


def create_draft(
    db: Session,
    *,
    artifact_type: str,
    title: str,
    payload_json: Dict[str, Any],
    project_id: Optional[int] = None,
    source_session_id: Optional[str] = None,
    codex_run_id: Optional[str] = None,
    validate_on_create: bool = True,
) -> HermesDraft:
    normalized = normalize_artifact_type(artifact_type)
    draft = HermesDraft(
        project_id=project_id,
        artifact_type=normalized,
        title=title.strip() if title else "Untitled Hermes Draft",
        payload_json=payload_json or {},
        status="draft",
        source_session_id=source_session_id,
        codex_run_id=codex_run_id,
    )

    if validate_on_create:
        validation = validate_draft_payload(normalized, draft.payload_json, db)
        draft.validation_result = validation
        draft.status = "validated" if validation["valid"] else "validation_failed"

    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def validate_existing_draft(db: Session, draft: HermesDraft) -> Dict[str, Any]:
    if draft.id is None:
        raise HermesApplyError("Draft must be persisted before it can be validated")

    try:
        locked_draft = (
            db.query(HermesDraft)
            .populate_existing()
            .with_for_update()
            .filter(HermesDraft.id == draft.id)
            .one_or_none()
        )
        if locked_draft is None:
            raise HermesApplyError(f"Draft {draft.id} was not found")
        if locked_draft.status == "applied":
            raise HermesApplyError("Applied drafts cannot be revalidated")
        if locked_draft.status == "rejected":
            raise HermesApplyError("Rejected drafts cannot be revalidated")

        validation = _set_draft_validation(locked_draft, db)
        db.commit()
        db.refresh(locked_draft)
        return validation
    except Exception:
        db.rollback()
        raise


def _set_draft_validation(draft: HermesDraft, db: Session) -> Dict[str, Any]:
    validation = validate_draft_payload(draft.artifact_type, draft.payload_json or {}, db)
    draft.validation_result = validation
    draft.status = "validated" if validation["valid"] else "validation_failed"
    return validation


def validate_draft_payload(
    artifact_type: str,
    payload: Dict[str, Any],
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    normalized = normalize_artifact_type(artifact_type)
    issues: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []

    try:
        if normalized == "workflow":
            _validate_workflow_payload(payload, issues, warnings)
        elif normalized == "deep_agent":
            _validate_deep_agent_payload(payload, issues, warnings)
        elif normalized == "custom_tool":
            _validate_custom_tool_payload(payload, issues, warnings)
        elif normalized == "schedule":
            _validate_schedule_payload(payload, issues, warnings, db)
        elif normalized == "trigger":
            _validate_trigger_payload(payload, issues, warnings, db)
    except HermesValidationError as exc:
        issues.append({"path": "$", "message": str(exc)})

    return {
        "valid": not issues,
        "artifact_type": normalized,
        "issues": issues,
        "warnings": warnings,
    }


def apply_draft(
    db: Session,
    draft: HermesDraft,
    *,
    target_id: Optional[int] = None,
    lock_version: Optional[int] = None,
    approval_note: Optional[str] = None,
) -> Dict[str, Any]:
    if draft.id is None:
        raise HermesApplyError("Draft must be persisted before it can be applied")

    try:
        # Reload under a row lock so concurrent apply requests serialize and the
        # second request observes the terminal status written by the first.
        locked_draft = (
            db.query(HermesDraft)
            .populate_existing()
            .with_for_update()
            .filter(HermesDraft.id == draft.id)
            .one_or_none()
        )
        if locked_draft is None:
            raise HermesApplyError(f"Draft {draft.id} was not found")
        if locked_draft.status == "applied":
            raise HermesApplyError("Draft has already been applied")
        if locked_draft.status == "rejected":
            raise HermesApplyError("Rejected drafts cannot be applied")

        validation = _set_draft_validation(locked_draft, db)
        if not validation["valid"]:
            raise HermesApplyError("Draft validation failed")

        artifact_type = normalize_artifact_type(locked_draft.artifact_type)
        payload = _with_draft_project(locked_draft.payload_json or {}, locked_draft.project_id)
        if artifact_type == "workflow":
            result = _apply_workflow(db, payload, target_id=target_id, lock_version=lock_version)
        elif artifact_type == "deep_agent":
            result = _apply_deep_agent(db, payload, target_id=target_id, lock_version=lock_version)
        elif artifact_type == "custom_tool":
            result = _apply_custom_tool(db, payload)
        elif artifact_type == "schedule":
            result = _apply_schedule(db, payload)
        elif artifact_type == "trigger":
            result = _apply_trigger(db, payload)
        else:
            raise HermesApplyError(f"Unsupported artifact type: {artifact_type}")

        locked_draft.status = "applied"
        locked_draft.apply_result = {
            **result,
            "approval_note": approval_note,
        }
        db.commit()
        db.refresh(locked_draft)
        return locked_draft.apply_result or {}
    except IntegrityError as exc:
        db.rollback()
        raise HermesApplyError(f"Artifact could not be saved: {exc.orig}") from exc
    except Exception:
        db.rollback()
        raise


def reject_draft(db: Session, draft: HermesDraft, reason: Optional[str] = None) -> HermesDraft:
    if draft.id is None:
        raise HermesApplyError("Draft must be persisted before it can be rejected")

    try:
        # Serialize rejection with apply/validation so the losing transaction
        # observes the terminal state committed by the winner.
        locked_draft = (
            db.query(HermesDraft)
            .populate_existing()
            .with_for_update()
            .filter(HermesDraft.id == draft.id)
            .one_or_none()
        )
        if locked_draft is None:
            raise HermesApplyError(f"Draft {draft.id} was not found")
        if locked_draft.status == "applied":
            raise HermesApplyError("Draft has already been applied")
        if locked_draft.status == "rejected":
            raise HermesApplyError("Draft has already been rejected")

        locked_draft.status = "rejected"
        locked_draft.rejection_reason = reason
        db.commit()
        db.refresh(locked_draft)
        return locked_draft
    except Exception:
        db.rollback()
        raise


def _validate_workflow_payload(payload: Dict[str, Any], issues: List[Dict[str, str]], warnings: List[Dict[str, str]]) -> None:
    workflow = payload.get("workflow") if isinstance(payload.get("workflow"), dict) else payload
    configuration = workflow.get("configuration")
    blueprint = workflow.get("blueprint")

    if not isinstance(configuration, dict):
        issues.append({"path": "$.configuration", "message": "Workflow drafts require a configuration object"})
        return

    nodes = configuration.get("nodes") or (blueprint or {}).get("nodes") or []
    edges = configuration.get("edges") or (blueprint or {}).get("edges") or []
    if not isinstance(nodes, list):
        issues.append({"path": "$.configuration.nodes", "message": "nodes must be a list"})
        return
    if not nodes:
        issues.append({"path": "$.configuration.nodes", "message": "workflow must contain at least one node"})
    if not isinstance(edges, list):
        issues.append({"path": "$.configuration.edges", "message": "edges must be a list"})
        return

    node_ids = []
    for index, node in enumerate(nodes):
        node_id = node.get("id") if isinstance(node, dict) else None
        if not node_id:
            issues.append({"path": f"$.configuration.nodes[{index}].id", "message": "node id is required"})
            continue
        node_ids.append(str(node_id))
        if isinstance(node, dict) and not (node.get("type") or (node.get("data") or {}).get("agentType")):
            warnings.append({"path": f"$.configuration.nodes[{index}]", "message": "node has no explicit semantic type"})

    duplicates = sorted({node_id for node_id in node_ids if node_ids.count(node_id) > 1})
    for node_id in duplicates:
        issues.append({"path": "$.configuration.nodes", "message": f"duplicate node id '{node_id}'"})

    node_id_set = set(node_ids)
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            issues.append({"path": f"$.configuration.edges[{index}]", "message": "edge must be an object"})
            continue
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source not in node_id_set:
            issues.append({"path": f"$.configuration.edges[{index}].source", "message": f"unknown source node '{source}'"})
        if target not in node_id_set:
            issues.append({"path": f"$.configuration.edges[{index}].target", "message": f"unknown target node '{target}'"})


def _validate_deep_agent_payload(payload: Dict[str, Any], issues: List[Dict[str, str]], warnings: List[Dict[str, str]]) -> None:
    config_payload = payload.get("config") if isinstance(payload.get("config"), dict) else payload
    try:
        config = DeepAgentConfig.model_validate(config_payload)
    except Exception as exc:
        issues.append({"path": "$.config", "message": str(exc)})
        return
    if not config.subagents:
        warnings.append({"path": "$.config.subagents", "message": "Hermes agents usually benefit from specialized subagents"})
    if not config.native_tools:
        warnings.append({"path": "$.config.native_tools", "message": "No native tools configured"})


def _validate_custom_tool_payload(payload: Dict[str, Any], issues: List[Dict[str, str]], warnings: List[Dict[str, str]]) -> None:
    for key in ("name", "description", "implementation_config", "input_schema"):
        if key not in payload:
            issues.append({"path": f"$.{key}", "message": f"{key} is required"})
    try:
        ToolType(payload.get("tool_type", ToolType.API.value))
    except ValueError:
        issues.append({"path": "$.tool_type", "message": f"Invalid tool_type: {payload.get('tool_type')}"})
    if payload.get("tool_id") and not re.match(r"^[a-zA-Z0-9_]+$", str(payload["tool_id"])):
        issues.append({"path": "$.tool_id", "message": "tool_id must contain only letters, numbers, and underscores"})


def _validate_schedule_payload(
    payload: Dict[str, Any],
    issues: List[Dict[str, str]],
    warnings: List[Dict[str, str]],
    db: Optional[Session],
) -> None:
    workflow_id = payload.get("workflow_id")
    if not workflow_id:
        issues.append({"path": "$.workflow_id", "message": "workflow_id is required"})
    elif db and not db.query(WorkflowProfile).filter(WorkflowProfile.id == workflow_id).first():
        issues.append({"path": "$.workflow_id", "message": f"workflow {workflow_id} was not found"})
    if not payload.get("cron_expression"):
        issues.append({"path": "$.cron_expression", "message": "cron_expression is required"})
    if not payload.get("timezone"):
        warnings.append({"path": "$.timezone", "message": "timezone omitted; UTC will be used"})


def _validate_trigger_payload(
    payload: Dict[str, Any],
    issues: List[Dict[str, str]],
    warnings: List[Dict[str, str]],
    db: Optional[Session],
) -> None:
    workflow_id = payload.get("workflow_id")
    if not workflow_id:
        issues.append({"path": "$.workflow_id", "message": "workflow_id is required"})
    elif db and not db.query(WorkflowProfile).filter(WorkflowProfile.id == workflow_id).first():
        issues.append({"path": "$.workflow_id", "message": f"workflow {workflow_id} was not found"})

    try:
        trigger_type = TriggerType(payload.get("trigger_type"))
    except ValueError:
        issues.append({"path": "$.trigger_type", "message": "trigger_type must be webhook or file_watch"})
        return

    config = payload.get("config") or {}
    if trigger_type == TriggerType.FILE_WATCH and not config.get("watch_path"):
        issues.append({"path": "$.config.watch_path", "message": "watch_path is required for file_watch triggers"})


def _apply_workflow(
    db: Session,
    payload: Dict[str, Any],
    *,
    target_id: Optional[int],
    lock_version: Optional[int],
) -> Dict[str, Any]:
    workflow_payload = payload.get("workflow") if isinstance(payload.get("workflow"), dict) else payload
    strategy_value = workflow_payload.get("strategy_type") or WorkflowStrategy.DEFAULT_SEQUENTIAL.value
    strategy = WorkflowStrategy(strategy_value)

    if target_id:
        workflow = (
            db.query(WorkflowProfile)
            .populate_existing()
            .with_for_update()
            .filter(WorkflowProfile.id == target_id)
            .first()
        )
        if not workflow:
            raise HermesApplyError(f"Workflow {target_id} not found")
        if lock_version is None:
            raise HermesApplyError("lock_version is required when applying over an existing workflow")
        if check_version_conflict(workflow, lock_version):
            raise HermesApplyError("Workflow was modified since the draft was created")
        action = "updated"
    else:
        workflow = WorkflowProfile(
            name=workflow_payload.get("name") or payload.get("title") or f"Hermes Workflow {uuid.uuid4().hex[:6]}",
            configuration={},
        )
        db.add(workflow)
        action = "created"

    workflow.name = workflow_payload.get("name") or workflow.name
    workflow.description = workflow_payload.get("description")
    workflow.project_id = workflow_payload.get("project_id", workflow.project_id)
    workflow.strategy_type = strategy
    workflow.configuration = workflow_payload["configuration"]
    workflow.schema_output_config = workflow_payload.get("schema_output_config")
    workflow.output_schema = workflow_payload.get("output_schema")
    workflow.blueprint = workflow_payload.get("blueprint")
    workflow.custom_output_path = workflow_payload.get("custom_output_path")
    workflow.is_template = bool(workflow_payload.get("is_template", False))
    workflow.template_category = workflow_payload.get("template_category")
    workflow.template_icon = workflow_payload.get("template_icon")
    workflow.template_tags = workflow_payload.get("template_tags")

    db.flush()
    db.refresh(workflow)
    return {"artifact_type": "workflow", "action": action, "workflow_id": workflow.id, "lock_version": workflow.lock_version}


def _apply_deep_agent(
    db: Session,
    payload: Dict[str, Any],
    *,
    target_id: Optional[int],
    lock_version: Optional[int],
) -> Dict[str, Any]:
    config_payload = payload.get("config") if isinstance(payload.get("config"), dict) else payload
    config = DeepAgentConfig.model_validate(config_payload)
    config_json = config.model_dump(mode="json")

    if target_id:
        template = (
            db.query(DeepAgentTemplate)
            .populate_existing()
            .with_for_update()
            .filter(DeepAgentTemplate.id == target_id)
            .first()
        )
        if not template:
            raise HermesApplyError(f"DeepAgent {target_id} not found")
        if lock_version is None:
            raise HermesApplyError("lock_version is required when applying over an existing DeepAgent")
        if check_version_conflict(template, lock_version):
            raise HermesApplyError("DeepAgent was modified since the draft was created")
        action = "updated"
    else:
        template = DeepAgentTemplate(
            name=payload.get("name") or "Hermes Agent",
            description=payload.get("description"),
            category=payload.get("category") or "automation",
            config=config_json,
        )
        db.add(template)
        action = "created"

    template.name = payload.get("name") or template.name
    template.description = payload.get("description")
    template.category = payload.get("category") or template.category
    template.base_template_id = payload.get("base_template_id")
    template.runtime = config.runtime
    template.config = config_json
    template.middleware_config = [middleware.model_dump(mode="json") for middleware in config.middleware]
    template.subagents_config = [subagent.model_dump(mode="json") for subagent in config.subagents]
    template.backend_config = config.backend.model_dump(mode="json")
    template.guardrails_config = config.guardrails.model_dump(mode="json")
    template.export_settings = {
        "export_format": config.export_format,
        "include_chat_ui": config.include_chat_ui,
        "include_docker": config.include_docker,
    }

    db.flush()
    db.refresh(template)
    return {"artifact_type": "deep_agent", "action": action, "agent_id": template.id, "lock_version": template.lock_version}


def _apply_custom_tool(db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    tool_id = payload.get("tool_id") or _slugify(payload.get("name") or "hermes_tool")
    if db.query(CustomTool).filter(CustomTool.tool_id == tool_id).first():
        tool_id = f"{tool_id}_{uuid.uuid4().hex[:6]}"

    tool = CustomTool(
        tool_id=tool_id,
        name=payload["name"],
        description=payload["description"],
        tool_type=ToolType(payload.get("tool_type", ToolType.API.value)),
        template_type=ToolTemplateType(payload.get("template_type") or ToolTemplateType.CUSTOM.value),
        implementation_config=payload["implementation_config"],
        input_schema=payload["input_schema"],
        output_format=payload.get("output_format", "string"),
        validation_rules=payload.get("validation_rules"),
        is_template_based=bool(payload.get("is_template_based", False)),
        is_advanced_mode=bool(payload.get("is_advanced_mode", True)),
        project_id=payload.get("project_id"),
        category=payload.get("category"),
        tags=payload.get("tags") or [],
    )
    db.add(tool)
    db.flush()
    db.refresh(tool)
    return {"artifact_type": "custom_tool", "action": "created", "tool_id": tool.id, "tool_key": tool.tool_id}


def _apply_schedule(db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    schedule = WorkflowSchedule(
        workflow_id=payload["workflow_id"],
        name=payload.get("name"),
        cron_expression=payload["cron_expression"],
        timezone=payload.get("timezone") or "UTC",
        enabled=bool(payload.get("enabled", True)),
        default_input_data=payload.get("default_input_data") or {},
        max_concurrent_runs=int(payload.get("max_concurrent_runs", 1)),
        timeout_minutes=int(payload.get("timeout_minutes", 60)),
        idempotency_key_template=payload.get("idempotency_key_template"),
    )
    db.add(schedule)
    db.flush()
    db.refresh(schedule)
    return {"artifact_type": "schedule", "action": "created", "schedule_id": schedule.id}


def _apply_trigger(db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    trigger_type = TriggerType(payload["trigger_type"])
    trigger = WorkflowTrigger(
        workflow_id=payload["workflow_id"],
        trigger_type=trigger_type.value,
        name=payload.get("name"),
        enabled=bool(payload.get("enabled", True)),
        config=payload.get("config") or {},
    )
    if trigger_type == TriggerType.WEBHOOK:
        trigger.webhook_secret = WorkflowTrigger.generate_webhook_secret()
    db.add(trigger)
    db.flush()
    db.refresh(trigger)
    return {"artifact_type": "trigger", "action": "created", "trigger_id": trigger.id}


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip().lower()).strip("_")
    return slug or "hermes_tool"


def _with_draft_project(payload: Dict[str, Any], project_id: Optional[int]) -> Dict[str, Any]:
    if project_id is None:
        return dict(payload)
    payload_copy = dict(payload)
    if isinstance(payload_copy.get("workflow"), dict):
        workflow_payload = dict(payload_copy["workflow"])
        workflow_payload.setdefault("project_id", project_id)
        payload_copy["workflow"] = workflow_payload
    else:
        payload_copy.setdefault("project_id", project_id)
    return payload_copy
