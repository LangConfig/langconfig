# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Platform Brain source catalog for LangConfig-aware agents."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from models.core import Project, Task
from models.custom_tool import CustomTool
from models.deep_agent import ChatSession
from models.execution_event import ExecutionEvent
from models.workflow import WorkflowProfile
from models.workflow_schedule import WorkflowSchedule
from models.workflow_trigger import WorkflowTrigger


REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_PATHS = [
    "AGENTS.md",
    "README.md",
    "CONTRIBUTING.md",
    "docs/SETUP.md",
    "docs/GOOGLE_OAUTH_SETUP.md",
    "backend/api/chat/README.md",
]

SENSITIVE_KEYS = {
    "apikey",
    "accesstoken",
    "refreshtoken",
    "authtoken",
    "bearertoken",
    "idtoken",
    "password",
    "passwd",
    "secret",
    "clientsecret",
    "webhooksecret",
    "credential",
    "authorization",
    "connectionstring",
    "privatekey",
    "accesskey",
    "webhookurl",
}

SAFE_TOKEN_KEYS = {
    "completiontokens",
    "inputtokens",
    "maxtokens",
    "outputtokens",
    "prompttokens",
    "tokencount",
    "tokencounts",
    "tokenbudget",
    "tokenlimit",
    "tokenlimits",
    "tokenusage",
    "tokenwindow",
    "totaltokens",
}


@dataclass
class BrainSource:
    source_id: str
    source_type: str
    title: str
    content: str
    metadata: Dict[str, Any]

    def to_result(self, score: float, highlights: List[str]) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "title": self.title,
            "score": score,
            "highlights": highlights,
            "metadata": self.metadata,
        }


class PlatformBrainService:
    """Collects LangConfig operating-model sources and searches them."""

    def __init__(self):
        self._sources: List[BrainSource] = []
        self._last_indexed_at: Optional[float] = None
        self._last_duration_ms: Optional[float] = None

    def status(self) -> Dict[str, Any]:
        counts: Dict[str, int] = {}
        for source in self._sources:
            counts[source.source_type] = counts.get(source.source_type, 0) + 1
        return {
            "source_count": len(self._sources),
            "source_counts": counts,
            "last_indexed_at": self._last_indexed_at,
            "last_duration_ms": self._last_duration_ms,
            "metadata_contract": "source_type, source_id, path/entity ids, project_id, updated_at",
            "retrieval_backend": "platform-source-catalog",
        }

    def reindex(self, db: Optional[Session] = None) -> Dict[str, Any]:
        started = time.time()
        sources = []
        sources.extend(self._collect_docs())
        sources.extend(self._collect_routes())
        sources.extend(self._collect_workflow_recipes())
        sources.extend(self._collect_native_tools())
        if db is not None:
            sources.extend(self._collect_database_sources(db))

        self._sources = sources
        self._last_indexed_at = time.time()
        self._last_duration_ms = (self._last_indexed_at - started) * 1000
        return self.status()

    def query(
        self,
        query: str,
        db: Optional[Session] = None,
        *,
        top_k: int = 8,
        source_types: Optional[List[str]] = None,
        project_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        wanted_types = set(source_types or [])
        if not self._sources:
            # Interactive queries initialize the static catalog only. Database
            # sources require an explicit project scope below.
            self.reindex()

        if db is not None:
            query_sources = [
                source for source in self._sources
                if not source.source_type.startswith("db.")
            ]
            if project_id is not None:
                query_sources.extend(self._collect_database_sources(
                    db,
                    project_id=project_id,
                    source_types=wanted_types or None,
                ))
        else:
            # Explicit reindex callers may intentionally cache database sources.
            # Reuse them only when no live database session was supplied; the
            # ownership checks below still fail closed.
            query_sources = list(self._sources)

        terms = _tokenize(query)
        scored = []
        for source in query_sources:
            if wanted_types and source.source_type not in wanted_types:
                continue
            source_project_id = source.metadata.get("project_id")
            if source.source_type.startswith("db."):
                # Database records fail closed: they require an explicit
                # project scope and must carry matching ownership metadata.
                if project_id is None or source_project_id != project_id:
                    continue
            elif project_id is not None and source_project_id not in (None, project_id):
                    continue
            score, highlights = self._score_source(source, terms)
            if score > 0:
                scored.append(source.to_result(score, highlights))

        scored.sort(key=lambda item: item["score"], reverse=True)
        return {
            "query": query,
            "results": scored[: max(top_k, 1)],
            "total_results": len(scored),
            "status": self.status(),
        }

    def _score_source(self, source: BrainSource, terms: List[str]) -> tuple[float, List[str]]:
        if not terms:
            return 0.0, []
        haystack = f"{source.title}\n{source.content}".lower()
        title = source.title.lower()
        score = 0.0
        highlights = []
        for term in terms:
            count = haystack.count(term)
            if not count:
                continue
            score += count
            if term in title:
                score += 4
            highlights.extend(_snippets(source.content, term, limit=2))
        return score, highlights[:4]

    def _collect_docs(self) -> List[BrainSource]:
        sources = []
        for relative in DOC_PATHS:
            path = REPO_ROOT / relative
            if not path.exists() or not path.is_file():
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
            sources.extend(_chunk_text(
                source_type="docs",
                source_id_prefix=f"doc:{relative}",
                title=relative,
                content=content,
                metadata={"path": str(path), "relative_path": relative},
            ))
        return sources

    def _collect_routes(self) -> List[BrainSource]:
        sources = []
        api_root = REPO_ROOT / "backend" / "api"
        for path in api_root.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            prefix = _first_match(r"APIRouter\(prefix=[\"']([^\"']+)[\"']", text) or ""
            route_lines = []
            for match in re.finditer(r"@router\.(get|post|put|patch|delete)\([\"']([^\"']*)[\"']", text):
                method, route_path = match.groups()
                route_lines.append(f"{method.upper()} {prefix}{route_path}")
            if not route_lines:
                continue
            relative = path.relative_to(REPO_ROOT).as_posix()
            sources.append(BrainSource(
                source_id=f"route:{relative}",
                source_type="api.route",
                title=f"API routes in {relative}",
                content="\n".join(route_lines),
                metadata={"path": str(path), "relative_path": relative, "prefix": prefix},
            ))
        return sources

    def _collect_workflow_recipes(self) -> List[BrainSource]:
        try:
            from core.templates.workflow_recipes import get_all_recipes, recipe_to_dict
        except Exception:
            return []
        sources = []
        for recipe in get_all_recipes():
            data = recipe_to_dict(recipe)
            content = json.dumps(data, indent=2, ensure_ascii=False)
            sources.append(BrainSource(
                source_id=f"recipe:{recipe.recipe_id}",
                source_type="workflow.recipe",
                title=recipe.name,
                content=content,
                metadata={
                    "recipe_id": recipe.recipe_id,
                    "category": recipe.category,
                    "tags": recipe.tags,
                    "node_count": len(recipe.nodes),
                    "edge_count": len(recipe.edges),
                },
            ))
        return sources

    def _collect_native_tools(self) -> List[BrainSource]:
        try:
            from tools.native_tools import get_available_tool_names
        except Exception:
            return []
        names = get_available_tool_names()
        return [
            BrainSource(
                source_id="tools:native",
                source_type="tool.catalog",
                title="Native tool catalog",
                content="\n".join(sorted(names)),
                metadata={"tool_count": len(names)},
            )
        ]

    def _collect_database_sources(
        self,
        db: Session,
        *,
        project_id: Optional[int] = None,
        source_types: Optional[set[str]] = None,
    ) -> List[BrainSource]:
        sources: List[BrainSource] = []
        collectors = (
            ("db.project", self._db_projects),
            ("db.workflow", self._db_workflows),
            ("db.custom_tool", self._db_custom_tools),
            ("db.schedule", self._db_schedules),
            ("db.trigger", self._db_triggers),
            ("db.execution_trace", self._db_execution_traces),
            ("db.chat_history", self._db_chat_history),
        )
        for source_type, collector in collectors:
            if source_types is not None and source_type not in source_types:
                continue
            sources.extend(collector(db, project_id=project_id))
        return sources

    def _db_projects(self, db: Session, *, project_id: Optional[int] = None) -> Iterable[BrainSource]:
        query = db.query(Project)
        if project_id is not None:
            query = query.filter(Project.id == project_id)
        for project in query.order_by(desc(Project.updated_at)).limit(100).all():
            content = _safe_database_json({
                "name": project.name,
                "description": project.description,
                "configuration": project.configuration,
                "status": getattr(project.status, "value", project.status),
            })
            yield BrainSource(
                source_id=f"project:{project.id}",
                source_type="db.project",
                title=f"Project: {project.name}",
                content=content,
                metadata={"project_id": project.id, "updated_at": _iso(project.updated_at)},
            )

    def _db_workflows(self, db: Session, *, project_id: Optional[int] = None) -> Iterable[BrainSource]:
        query = db.query(WorkflowProfile)
        if project_id is not None:
            query = query.filter(WorkflowProfile.project_id == project_id)
        for workflow in query.order_by(desc(WorkflowProfile.updated_at)).limit(200).all():
            content = _safe_database_json({
                "name": workflow.name,
                "description": workflow.description,
                "configuration": workflow.configuration,
                "blueprint": workflow.blueprint,
                "strategy_type": getattr(workflow.strategy_type, "value", workflow.strategy_type),
            })
            yield BrainSource(
                source_id=f"workflow:{workflow.id}",
                source_type="db.workflow",
                title=f"Workflow: {workflow.name}",
                content=content,
                metadata={"workflow_id": workflow.id, "project_id": workflow.project_id, "updated_at": _iso(workflow.updated_at)},
            )

    def _db_custom_tools(self, db: Session, *, project_id: Optional[int] = None) -> Iterable[BrainSource]:
        query = db.query(CustomTool)
        if project_id is not None:
            query = query.filter(CustomTool.project_id == project_id)
        for tool in query.order_by(desc(CustomTool.updated_at)).limit(200).all():
            content = _safe_database_json({
                "tool_id": tool.tool_id,
                "name": tool.name,
                "description": tool.description,
                "tool_type": getattr(tool.tool_type, "value", tool.tool_type),
                "implementation_config": tool.implementation_config,
                "input_schema": tool.input_schema,
            })
            yield BrainSource(
                source_id=f"custom_tool:{tool.id}",
                source_type="db.custom_tool",
                title=f"Custom Tool: {tool.name}",
                content=content,
                metadata={"tool_id": tool.id, "tool_key": tool.tool_id, "project_id": tool.project_id},
            )

    def _db_schedules(self, db: Session, *, project_id: Optional[int] = None) -> Iterable[BrainSource]:
        query = (
            db.query(WorkflowSchedule, WorkflowProfile.project_id.label("project_id"))
            .join(WorkflowProfile, WorkflowSchedule.workflow_id == WorkflowProfile.id)
        )
        if project_id is not None:
            query = query.filter(WorkflowProfile.project_id == project_id)
        rows = (
            query
            .order_by(desc(WorkflowSchedule.updated_at))
            .limit(200)
            .all()
        )
        for schedule, project_id in rows:
            yield BrainSource(
                source_id=f"schedule:{schedule.id}",
                source_type="db.schedule",
                title=f"Schedule: {schedule.name or schedule.id}",
                content=_safe_database_json(schedule.to_dict()),
                metadata={
                    "schedule_id": schedule.id,
                    "workflow_id": schedule.workflow_id,
                    "project_id": project_id,
                },
            )

    def _db_triggers(self, db: Session, *, project_id: Optional[int] = None) -> Iterable[BrainSource]:
        query = (
            db.query(WorkflowTrigger, WorkflowProfile.project_id.label("project_id"))
            .join(WorkflowProfile, WorkflowTrigger.workflow_id == WorkflowProfile.id)
        )
        if project_id is not None:
            query = query.filter(WorkflowProfile.project_id == project_id)
        rows = (
            query
            .order_by(desc(WorkflowTrigger.updated_at))
            .limit(200)
            .all()
        )
        for trigger, project_id in rows:
            content = _safe_database_json({
                "id": trigger.id,
                "workflow_id": trigger.workflow_id,
                "name": trigger.name,
                "trigger_type": trigger.trigger_type,
                "enabled": trigger.enabled,
                "config": trigger.config,
                "last_triggered_at": _iso(trigger.last_triggered_at),
                "trigger_count": trigger.trigger_count,
                "created_at": _iso(trigger.created_at),
                "updated_at": _iso(trigger.updated_at),
            })
            yield BrainSource(
                source_id=f"trigger:{trigger.id}",
                source_type="db.trigger",
                title=f"Trigger: {trigger.name or trigger.id}",
                content=content,
                metadata={
                    "trigger_id": trigger.id,
                    "workflow_id": trigger.workflow_id,
                    "project_id": project_id,
                },
            )

    def _db_execution_traces(self, db: Session, *, project_id: Optional[int] = None) -> Iterable[BrainSource]:
        query = (
            db.query(ExecutionEvent, Task.project_id.label("project_id"))
            .join(Task, ExecutionEvent.task_id == Task.id)
        )
        if project_id is not None:
            query = query.filter(Task.project_id == project_id)
        rows = (
            query
            .order_by(desc(ExecutionEvent.timestamp))
            .limit(200)
            .all()
        )
        for event, project_id in rows:
            content = _safe_database_json({
                "event_type": event.event_type,
                "event_data": event.event_data,
                "run_id": event.run_id,
                "parent_run_id": event.parent_run_id,
            })
            yield BrainSource(
                source_id=f"execution_event:{event.id}",
                source_type="db.execution_trace",
                title=f"Execution event: {event.event_type}",
                content=content,
                metadata={
                    "event_id": event.id,
                    "task_id": event.task_id,
                    "workflow_id": event.workflow_id,
                    "project_id": project_id,
                    "timestamp": _iso(event.timestamp),
                },
            )

    def _db_chat_history(self, db: Session, *, project_id: Optional[int] = None) -> Iterable[BrainSource]:
        query = db.query(ChatSession)
        if project_id is not None:
            query = query.filter(ChatSession.project_id == project_id)
        sessions = query.order_by(desc(ChatSession.updated_at)).limit(50).all()
        for session in sessions:
            messages = (session.messages or [])[-12:]
            yield BrainSource(
                source_id=f"chat_session:{session.session_id}",
                source_type="db.chat_history",
                title=f"Chat session: {session.session_id}",
                content=_safe_database_json({
                    "session_id": session.session_id,
                    "messages": messages,
                    "tool_calls": session.tool_calls,
                    "subagent_spawns": session.subagent_spawns,
                }),
                metadata={"session_id": session.session_id, "agent_id": session.agent_id, "project_id": session.project_id},
            )


def _tokenize(query: str) -> List[str]:
    return [term for term in re.findall(r"[a-zA-Z0-9_]{2,}", (query or "").lower()) if term]


def _safe_database_json(value: Any) -> str:
    """Serialize database content after recursively removing credentials."""
    return json.dumps(_redact_credentials(value), default=str, ensure_ascii=False)


def _redact_credentials(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: Dict[Any, Any] = {}
        for key, item in value.items():
            normalized_key = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if _is_sensitive_key(normalized_key):
                redacted[key] = "REDACTED"
            else:
                redacted[key] = _redact_credentials(item)
        return redacted
    if isinstance(value, list):
        return [_redact_credentials(item) for item in value]
    if isinstance(value, tuple):
        return [_redact_credentials(item) for item in value]
    return value


def _is_sensitive_key(normalized_key: str) -> bool:
    if normalized_key in SENSITIVE_KEYS:
        return True
    if normalized_key.endswith(("password", "passwd", "secret", "credential", "privatekey", "accesskey")):
        return True
    if normalized_key.endswith("token"):
        return normalized_key not in SAFE_TOKEN_KEYS
    return False


def _snippets(content: str, term: str, limit: int = 2) -> List[str]:
    snippets = []
    lower = content.lower()
    start = 0
    while len(snippets) < limit:
        index = lower.find(term, start)
        if index == -1:
            break
        left = max(0, index - 120)
        right = min(len(content), index + 180)
        snippets.append(content[left:right].replace("\n", " ").strip())
        start = index + len(term)
    return snippets


def _chunk_text(
    *,
    source_type: str,
    source_id_prefix: str,
    title: str,
    content: str,
    metadata: Dict[str, Any],
    chunk_size: int = 6000,
) -> List[BrainSource]:
    if len(content) <= chunk_size:
        return [BrainSource(source_id=source_id_prefix, source_type=source_type, title=title, content=content, metadata=metadata)]
    chunks = []
    for index, offset in enumerate(range(0, len(content), chunk_size)):
        chunks.append(BrainSource(
            source_id=f"{source_id_prefix}:chunk:{index}",
            source_type=source_type,
            title=f"{title} (part {index + 1})",
            content=content[offset: offset + chunk_size],
            metadata={**metadata, "chunk_index": index},
        ))
    return chunks


def _first_match(pattern: str, text: str) -> Optional[str]:
    match = re.search(pattern, text)
    return match.group(1) if match else None


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if value else None


platform_brain_service = PlatformBrainService()
