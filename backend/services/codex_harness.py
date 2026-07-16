# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Local Codex CLI harness for Hermes.

The harness never accepts or stores Codex credentials. Authentication remains
owned by the local Codex CLI (`codex login` / ChatGPT subscription auth).
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
CODEX_RUN_ROOT = REPO_ROOT / "backend" / "data" / "codex_runs"

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
DEFAULT_MAX_RETAINED_RUNS = 100
DEFAULT_MAX_EVENTS_PER_RUN = 2_000
DEFAULT_RETENTION_SECONDS = 24 * 60 * 60


@dataclass
class CodexRun:
    id: str
    mode: str
    command: List[str]
    sandbox_dir: Path
    status: str = "queued"
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    exit_code: Optional[int] = None
    last_message: Optional[str] = None
    error: Optional[str] = None
    process: Optional[subprocess.Popen] = field(default=None, repr=False)
    events: List[Dict[str, Any]] = field(default_factory=list)
    event_offset: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class CodexHarnessError(RuntimeError):
    """Raised when a local Codex operation cannot be performed."""


class CodexHarness:
    """Process manager for local Codex CLI runs.

    By default, terminal runs and their managed workspaces are retained for at
    most 24 hours, up to 100 runs, with the newest 2,000 events kept per run.
    Active runs are never evicted.
    """

    def __init__(
        self,
        run_root: Path = CODEX_RUN_ROOT,
        *,
        max_retained_runs: int = DEFAULT_MAX_RETAINED_RUNS,
        max_events_per_run: int = DEFAULT_MAX_EVENTS_PER_RUN,
        retention_seconds: float = DEFAULT_RETENTION_SECONDS,
    ):
        if max_retained_runs < 1:
            raise ValueError("max_retained_runs must be at least 1")
        if max_events_per_run < 1:
            raise ValueError("max_events_per_run must be at least 1")
        if retention_seconds < 0:
            raise ValueError("retention_seconds cannot be negative")
        self.run_root = run_root
        self.max_retained_runs = max_retained_runs
        self.max_events_per_run = max_events_per_run
        self.retention_seconds = retention_seconds
        self._runs: Dict[str, CodexRun] = {}
        self._workers: Dict[str, threading.Thread] = {}
        self._lock = threading.RLock()
        self._shutting_down = False
        self._codex_binary = shutil.which("codex")

    @property
    def codex_binary(self) -> Optional[str]:
        return self._codex_binary or shutil.which("codex")

    def status(self) -> Dict[str, Any]:
        """Return local Codex CLI availability and login status."""
        binary = self.codex_binary
        result: Dict[str, Any] = {
            "installed": bool(binary),
            "binary": binary,
            "version": None,
            "logged_in": False,
            "login_status": "codex CLI not found",
            "auth_owner": "codex-cli",
            "credentials_stored_by_langconfig": False,
            "exec_supported": False,
            "mcp_server_supported": False,
        }
        if not binary:
            return result

        version = self._run_short([binary, "--version"], timeout=8)
        result["version"] = version["stdout"].strip() or version["stderr"].strip() or None

        login = self._run_short([binary, "login", "status"], timeout=8)
        combined = f"{login['stdout']}\n{login['stderr']}".strip()
        result["login_status"] = combined or f"codex login status exited {login['returncode']}"
        result["logged_in"] = login["returncode"] == 0 and "logged in" in combined.lower()

        exec_help = self._run_short([binary, "exec", "--help"], timeout=8)
        result["exec_supported"] = exec_help["returncode"] == 0 and "--json" in exec_help["stdout"]

        mcp_help = self._run_short([binary, "mcp-server", "--help"], timeout=8)
        result["mcp_server_supported"] = mcp_help["returncode"] == 0
        result["mcp_command"] = [binary, "mcp-server"] if result["mcp_server_supported"] else None
        return result

    def start_device_login(self) -> CodexRun:
        """Start `codex login --device-auth` as an evented local run."""
        binary = self._require_codex()
        run_id = self._new_run_id()
        workspace = self._prepare_run_workspace(run_id)
        command = [binary, "login", "--device-auth"]
        run = CodexRun(
            id=run_id,
            mode="login_device",
            command=command,
            sandbox_dir=workspace,
            metadata={
                "auth_owner": "codex-cli",
                "credentials_stored_by_langconfig": False,
                "managed_workspace": True,
            },
        )
        self._register_and_start(run)
        return run

    def start_exec_run(
        self,
        prompt: str,
        sandbox_dir: Optional[str] = None,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CodexRun:
        """Start `codex exec --json` in a validated sandbox directory."""
        if not prompt or not prompt.strip():
            raise CodexHarnessError("prompt is required")

        binary = self._require_codex()
        run_id = self._new_run_id()
        workspace = self._prepare_run_workspace(run_id, sandbox_dir=sandbox_dir)
        last_message_path = workspace / "codex-last-message.txt"

        command = [
            binary,
            "exec",
            "--json",
            "--skip-git-repo-check",
            "--sandbox",
            "workspace-write",
            "--cd",
            str(workspace),
            "--output-last-message",
            str(last_message_path),
        ]
        if model:
            command.extend(["--model", model])
        command.append(prompt.strip())

        run = CodexRun(
            id=run_id,
            mode="exec",
            command=command,
            sandbox_dir=workspace,
            metadata={
                **(metadata or {}),
                "sandbox": "workspace-write",
                "last_message_path": str(last_message_path),
                "managed_workspace": sandbox_dir is None,
            },
        )
        self._register_and_start(run)
        return run

    def get_run(self, run_id: str) -> Optional[CodexRun]:
        with self._lock:
            return self._runs.get(run_id)

    def cancel_run(self, run_id: str) -> Dict[str, Any]:
        with self._lock:
            run = self._runs.get(run_id)
            if not run:
                raise CodexHarnessError("Codex run not found")
            if run.status in TERMINAL_STATUSES:
                return self.serialize_run(run)

            process = run.process
            self._mark_cancelled_locked(run, "Codex run cancelled")

        if process is not None:
            self._terminate_process(process)
            with self._lock:
                run.exit_code = process.returncode

        result = self.serialize_run(run)
        self.prune_retained_runs()
        return result

    async def stream_events(self, run_id: str, start_index: int = 0) -> AsyncIterator[Dict[str, Any]]:
        """Yield stored and live events for a run."""
        index = max(start_index, 0)
        while True:
            with self._lock:
                run = self._runs.get(run_id)
                if not run:
                    raise CodexHarnessError("Codex run not found")
                event_offset = run.event_offset
                events = list(run.events)
                terminal = run.status in TERMINAL_STATUSES

            index = max(index, event_offset)
            event_limit = event_offset + len(events)
            while index < event_limit:
                yield {"index": index, **events[index - event_offset]}
                index += 1

            if terminal:
                break
            await asyncio.sleep(0.25)

    def list_events(self, run_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            run = self._runs.get(run_id)
            if not run:
                raise CodexHarnessError("Codex run not found")
            return [
                {"index": run.event_offset + index, **event}
                for index, event in enumerate(run.events)
            ]

    def serialize_run(self, run: CodexRun) -> Dict[str, Any]:
        return {
            "id": run.id,
            "mode": run.mode,
            "status": run.status,
            "sandbox_dir": str(run.sandbox_dir),
            "created_at": run.created_at,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "exit_code": run.exit_code,
            "last_message": run.last_message,
            "error": run.error,
            "metadata": run.metadata,
            "command_preview": self._redacted_command(run.command),
        }

    def validate_sandbox_path(self, path: Path) -> Path:
        """Ensure a sandbox path is inside the Codex run root."""
        resolved = path.expanduser().resolve()
        root = self.run_root.resolve()
        if resolved != root and root not in resolved.parents:
            raise CodexHarnessError(f"Sandbox path must be inside {root}")
        return resolved

    def _register_and_start(self, run: CodexRun) -> None:
        self.prune_retained_runs()
        with self._lock:
            if self._shutting_down:
                raise CodexHarnessError("Codex harness is shutting down")
            self._runs[run.id] = run
            thread = threading.Thread(target=self._run_process, args=(run,), daemon=True)
            self._workers[run.id] = thread
            thread.start()

    def _run_process(self, run: CodexRun) -> None:
        try:
            with self._lock:
                if run.status == "cancelled" or self._shutting_down:
                    if run.status != "cancelled":
                        self._mark_cancelled_locked(run, "Codex harness is shutting down")
                    return
                run.status = "running"
                run.started_at = time.time()
                self._append_event_locked(
                    run,
                    {
                        "type": "run.started",
                        "mode": run.mode,
                        "sandbox_dir": str(run.sandbox_dir),
                        "command_preview": self._redacted_command(run.command),
                    },
                )

            creationflags = 0
            if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
                creationflags = subprocess.CREATE_NO_WINDOW

            process = subprocess.Popen(
                run.command,
                cwd=str(run.sandbox_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
            )
            with self._lock:
                run.process = process
                if self._shutting_down and run.status != "cancelled":
                    self._mark_cancelled_locked(run, "Codex harness is shutting down")
                cancelled = run.status == "cancelled"

            # Cancellation can arrive while Popen is creating the child. The
            # child must be stopped before any output is consumed.
            if cancelled:
                self._terminate_process(process)
                with self._lock:
                    run.exit_code = process.returncode
                    run.completed_at = run.completed_at or time.time()
                return

            assert process.stdout is not None

            for line in process.stdout:
                with self._lock:
                    if run.status == "cancelled":
                        break
                line = line.rstrip("\n")
                if not line:
                    continue
                self._append_event(run, self._parse_output_line(line))

            exit_code = process.wait()
            with self._lock:
                run.exit_code = exit_code
                cancelled = run.status == "cancelled"

            if run.mode == "exec" and not cancelled:
                last_message_path = Path(run.metadata.get("last_message_path", ""))
                if last_message_path.exists():
                    run.last_message = last_message_path.read_text(encoding="utf-8", errors="replace")

            with self._lock:
                run.completed_at = time.time()
                if run.status != "cancelled":
                    run.status = "completed" if run.exit_code == 0 else "failed"
                    self._append_event_locked(
                        run,
                        {
                            "type": f"run.{run.status}",
                            "exit_code": run.exit_code,
                            "last_message": run.last_message,
                        },
                    )
        except Exception as exc:
            with self._lock:
                if run.status != "cancelled":
                    run.status = "failed"
                    run.error = str(exc)
                    run.completed_at = time.time()
                    self._append_event_locked(run, {"type": "run.failed", "error": str(exc)})
        finally:
            with self._lock:
                self._workers.pop(run.id, None)
            self.prune_retained_runs()

    def _append_event(self, run: CodexRun, event: Dict[str, Any]) -> None:
        with self._lock:
            self._append_event_locked(run, event)

    def _append_event_locked(self, run: CodexRun, event: Dict[str, Any]) -> None:
        event.setdefault("timestamp", time.time())
        run.events.append(event)
        overflow = len(run.events) - self.max_events_per_run
        if overflow > 0:
            del run.events[:overflow]
            run.event_offset += overflow

    def _mark_cancelled_locked(self, run: CodexRun, message: str) -> None:
        if run.status in TERMINAL_STATUSES:
            return
        run.status = "cancelled"
        run.completed_at = time.time()
        self._append_event_locked(run, {"type": "run.cancelled", "message": message})

    @staticmethod
    def _terminate_process(process: subprocess.Popen, timeout: float = 5.0) -> None:
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=max(timeout, 0.01))
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                process.wait(timeout=max(timeout, 0.01))
            except subprocess.TimeoutExpired:
                pass

    def shutdown(self, timeout: float = 10.0) -> None:
        """Cancel active runs, terminate children, and join worker threads."""
        deadline = time.monotonic() + max(timeout, 0.0)
        with self._lock:
            self._shutting_down = True
            for run in self._runs.values():
                if run.status not in TERMINAL_STATUSES:
                    self._mark_cancelled_locked(run, "Codex harness is shutting down")
            processes = [
                run.process
                for run in self._runs.values()
                if run.process is not None and run.process.poll() is None
            ]
            workers = list(self._workers.values())

        for process in processes:
            remaining = max(deadline - time.monotonic(), 0.01)
            self._terminate_process(process, timeout=min(5.0, remaining))

        current_thread = threading.current_thread()
        for worker in workers:
            if worker is current_thread:
                continue
            remaining = max(deadline - time.monotonic(), 0.0)
            worker.join(timeout=remaining)

        with self._lock:
            self._workers = {
                run_id: worker
                for run_id, worker in self._workers.items()
                if worker.is_alive()
            }
        self.prune_retained_runs()

    def prune_retained_runs(self, now: Optional[float] = None) -> List[str]:
        """Evict old terminal runs and delete only harness-managed workspaces."""
        current_time = time.time() if now is None else now
        with self._lock:
            prunable = []
            for run in self._runs.values():
                worker = self._workers.get(run.id)
                if run.status in TERMINAL_STATUSES and (worker is None or not worker.is_alive()):
                    prunable.append(run)
            prunable.sort(key=lambda run: (self._terminal_timestamp(run), run.created_at))
            expired_ids = {
                run.id
                for run in prunable
                if current_time - self._terminal_timestamp(run) >= self.retention_seconds
            }
            remaining_count = len(self._runs) - len(expired_ids)
            overflow = max(remaining_count - self.max_retained_runs, 0)
            overflow_ids = [run.id for run in prunable if run.id not in expired_ids][:overflow]
            run_ids = [run.id for run in prunable if run.id in expired_ids] + overflow_ids
            removed_runs = [self._runs.pop(run_id) for run_id in run_ids]

        for run in removed_runs:
            self._delete_managed_workspace(run)
        return run_ids

    def _delete_managed_workspace(self, run: CodexRun) -> None:
        if not run.metadata.get("managed_workspace"):
            return
        run_directory = self.run_root / run.id
        try:
            validated = self.validate_sandbox_path(run_directory)
        except CodexHarnessError:
            return
        shutil.rmtree(validated, ignore_errors=True)

    @staticmethod
    def _terminal_timestamp(run: CodexRun) -> float:
        return run.completed_at if run.completed_at is not None else run.created_at

    def _parse_output_line(self, line: str) -> Dict[str, Any]:
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                return {"type": parsed.get("type", "codex.event"), "event": parsed, "raw": line}
        except json.JSONDecodeError:
            pass
        return {"type": "codex.log", "message": line, "raw": line}

    def _prepare_run_workspace(self, run_id: str, sandbox_dir: Optional[str] = None) -> Path:
        if sandbox_dir:
            workspace = self.validate_sandbox_path(Path(sandbox_dir))
        else:
            workspace = self.run_root / run_id / "workspace"
        workspace = self.validate_sandbox_path(workspace)
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace

    def _new_run_id(self) -> str:
        return f"codex_{uuid.uuid4().hex[:16]}"

    def _require_codex(self) -> str:
        binary = self.codex_binary
        if not binary:
            raise CodexHarnessError("codex CLI is not installed or not on PATH")
        return binary

    def _run_short(self, command: List[str], timeout: int) -> Dict[str, Any]:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
            return {
                "returncode": result.returncode,
                "stdout": result.stdout or "",
                "stderr": result.stderr or "",
            }
        except Exception as exc:
            return {"returncode": 1, "stdout": "", "stderr": str(exc)}

    def _redacted_command(self, command: List[str]) -> List[str]:
        if not command:
            return []
        redacted = list(command)
        # Avoid echoing the full task prompt back through API logs/UI.
        if len(redacted) > 1 and redacted[1] == "exec":
            redacted[-1] = "<prompt>"
        return redacted


codex_harness = CodexHarness()
