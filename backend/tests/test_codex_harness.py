import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil
import pytest
import services.codex_harness as codex_harness_module
from services.codex_harness import CodexHarness, CodexHarnessError, CodexRun


class FakeProcess:
    def __init__(self, lines=(), returncode=0):
        self.stdout = iter(lines)
        self.returncode = None
        self._final_returncode = returncode
        self.terminated = False
        self.killed = False

    def wait(self, timeout=None):
        self.returncode = self._final_returncode
        return self.returncode

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 143

    def kill(self):
        self.killed = True
        self.returncode = 137


class BlockingProcess(FakeProcess):
    def __init__(self):
        super().__init__(returncode=0)
        self._stopped = threading.Event()
        self.stdout = self._output()

    def _output(self):
        self._stopped.wait(timeout=5)
        return
        yield  # pragma: no cover - makes this a generator

    def wait(self, timeout=None):
        if not self._stopped.wait(timeout=timeout):
            raise codex_harness_module.subprocess.TimeoutExpired("codex", timeout)
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 143
        self._stopped.set()

    def kill(self):
        self.killed = True
        self.returncode = 137
        self._stopped.set()


def test_codex_status_parses_chatgpt_login(tmp_path, monkeypatch):
    harness = CodexHarness(run_root=tmp_path)
    harness._codex_binary = "codex"

    def fake_run(command, timeout):
        if command[-1] == "--version":
            return {"returncode": 0, "stdout": "codex-cli 0.136.0\n", "stderr": ""}
        if command[-2:] == ["login", "status"]:
            return {"returncode": 0, "stdout": "Logged in using ChatGPT\n", "stderr": ""}
        if command[-2:] == ["exec", "--help"]:
            return {"returncode": 0, "stdout": "Usage: codex exec --json --sandbox --cd\n", "stderr": ""}
        if command[-2:] == ["mcp-server", "--help"]:
            return {"returncode": 0, "stdout": "Start Codex as an MCP server\n", "stderr": ""}
        return {"returncode": 1, "stdout": "", "stderr": "unexpected"}

    monkeypatch.setattr(harness, "_run_short", fake_run)

    status = harness.status()

    assert status["installed"] is True
    assert status["version"] == "codex-cli 0.136.0"
    assert status["logged_in"] is True
    assert status["credentials_stored_by_langconfig"] is False
    assert status["exec_supported"] is True
    assert status["mcp_server_supported"] is True


def test_codex_exec_command_is_bounded_to_run_root(tmp_path, monkeypatch):
    harness = CodexHarness(run_root=tmp_path)
    harness._codex_binary = "codex"

    def no_start(run):
        harness._runs[run.id] = run

    monkeypatch.setattr(harness, "_register_and_start", no_start)

    run = harness.start_exec_run("write a plan", model="gpt-5.4")

    assert run.sandbox_dir.is_relative_to(tmp_path)
    assert run.command[:7] == [
        "codex",
        "exec",
        "--json",
        "--skip-git-repo-check",
        "--sandbox",
        "workspace-write",
        "--cd",
    ]
    assert "--output-last-message" in run.command
    assert run.command[-3:] == ["--model", "gpt-5.4", "write a plan"]


def test_codex_rejects_sandbox_escape(tmp_path):
    harness = CodexHarness(run_root=tmp_path)
    outside = tmp_path.parent / "outside"

    with pytest.raises(CodexHarnessError):
        harness.validate_sandbox_path(Path(outside))


def test_codex_jsonl_event_parsing(tmp_path):
    harness = CodexHarness(run_root=tmp_path)

    parsed = harness._parse_output_line('{"type":"task.started","id":"abc"}')
    fallback = harness._parse_output_line("plain log line")

    assert parsed["type"] == "task.started"
    assert parsed["event"]["id"] == "abc"
    assert fallback["type"] == "codex.log"
    assert fallback["message"] == "plain log line"


def test_codex_process_success_loads_last_message_and_emits_events(tmp_path, monkeypatch):
    harness = CodexHarness(run_root=tmp_path)
    last_message_path = tmp_path / "last-message.txt"
    last_message_path.write_text("Finished cleanly", encoding="utf-8")
    process = FakeProcess(
        lines=['{"type":"task.started","id":"task-1"}\n', "plain output\n"],
        returncode=0,
    )
    monkeypatch.setattr(codex_harness_module.subprocess, "Popen", lambda *args, **kwargs: process)
    run = CodexRun(
        id="run-success",
        mode="exec",
        command=["codex", "exec", "prompt"],
        sandbox_dir=tmp_path,
        metadata={"last_message_path": str(last_message_path)},
    )

    harness._run_process(run)

    assert run.status == "completed"
    assert run.exit_code == 0
    assert run.last_message == "Finished cleanly"
    assert [event["type"] for event in run.events] == [
        "run.started",
        "task.started",
        "codex.log",
        "run.completed",
    ]
    assert run.events[-1]["last_message"] == "Finished cleanly"


def test_codex_process_nonzero_exit_is_failed(tmp_path, monkeypatch):
    harness = CodexHarness(run_root=tmp_path)
    process = FakeProcess(lines=['{"type":"error","message":"bad task"}\n'], returncode=9)
    monkeypatch.setattr(codex_harness_module.subprocess, "Popen", lambda *args, **kwargs: process)
    run = CodexRun(
        id="run-failed",
        mode="exec",
        command=["codex", "exec", "prompt"],
        sandbox_dir=tmp_path,
        metadata={"last_message_path": str(tmp_path / "missing-message.txt")},
    )

    harness._run_process(run)

    assert run.status == "failed"
    assert run.exit_code == 9
    assert run.error is None
    assert run.events[-1]["type"] == "run.failed"
    assert run.events[-1]["exit_code"] == 9


def test_codex_process_start_error_is_recorded_as_failure(tmp_path, monkeypatch):
    harness = CodexHarness(run_root=tmp_path)

    def fail_to_start(*args, **kwargs):
        raise OSError("process unavailable")

    monkeypatch.setattr(codex_harness_module.subprocess, "Popen", fail_to_start)
    run = CodexRun(
        id="run-start-error",
        mode="exec",
        command=["codex", "exec", "prompt"],
        sandbox_dir=tmp_path,
    )

    harness._run_process(run)

    assert run.status == "failed"
    assert run.error == "process unavailable"
    assert run.events[-1]["type"] == "run.failed"
    assert run.events[-1]["error"] == "process unavailable"


def test_codex_cancel_terminates_running_process_and_is_terminal(tmp_path):
    harness = CodexHarness(run_root=tmp_path)
    process = FakeProcess(returncode=143)
    run = CodexRun(
        id="run-cancel",
        mode="exec",
        command=["codex", "exec", "prompt"],
        sandbox_dir=tmp_path,
        status="running",
        process=process,
    )
    harness._runs[run.id] = run

    first = harness.cancel_run(run.id)
    event_count = len(run.events)
    second = harness.cancel_run(run.id)

    assert process.terminated is True
    assert process.killed is False
    assert first["status"] == "cancelled"
    assert first["exit_code"] == 143
    assert run.events[-1]["type"] == "run.cancelled"
    assert second["status"] == "cancelled"
    assert len(run.events) == event_count


def test_codex_cancel_preserves_completed_terminal_run(tmp_path):
    harness = CodexHarness(run_root=tmp_path)
    run = CodexRun(
        id="run-complete",
        mode="exec",
        command=["codex", "exec", "prompt"],
        sandbox_dir=tmp_path,
        status="completed",
        exit_code=0,
        events=[{"type": "run.completed"}],
    )
    harness._runs[run.id] = run

    result = harness.cancel_run(run.id)

    assert result["status"] == "completed"
    assert run.events == [{"type": "run.completed"}]


def test_codex_cancelled_queued_run_never_spawns(tmp_path, monkeypatch):
    harness = CodexHarness(run_root=tmp_path)
    harness._codex_binary = "codex"
    worker_entered = threading.Event()
    release_worker = threading.Event()
    worker_finished = threading.Event()
    popen_calls = []
    original_run_process = harness._run_process

    def blocked_run_process(run):
        worker_entered.set()
        release_worker.wait(timeout=5)
        try:
            original_run_process(run)
        finally:
            worker_finished.set()

    def unexpected_popen(*args, **kwargs):
        popen_calls.append((args, kwargs))
        return FakeProcess()

    monkeypatch.setattr(harness, "_run_process", blocked_run_process)
    monkeypatch.setattr(codex_harness_module.subprocess, "Popen", unexpected_popen)

    run = harness.start_exec_run("do not execute")
    assert worker_entered.wait(timeout=2)

    result = harness.cancel_run(run.id)
    release_worker.set()
    assert worker_finished.wait(timeout=2)

    assert result["status"] == "cancelled"
    assert run.status == "cancelled"
    assert run.started_at is None
    assert popen_calls == []


def test_codex_cancel_during_popen_is_rechecked_and_terminated(tmp_path, monkeypatch):
    harness = CodexHarness(run_root=tmp_path)
    process = FakeProcess()
    run = CodexRun(
        id="run-cancel-during-spawn",
        mode="exec",
        command=["codex", "exec", "prompt"],
        sandbox_dir=tmp_path,
    )
    harness._runs[run.id] = run

    def cancel_while_spawning(*args, **kwargs):
        harness.cancel_run(run.id)
        return process

    monkeypatch.setattr(codex_harness_module.subprocess, "Popen", cancel_while_spawning)

    harness._run_process(run)

    assert run.status == "cancelled"
    assert process.terminated is True
    assert [event["type"] for event in run.events] == ["run.started", "run.cancelled"]


def test_codex_shutdown_cancels_process_and_joins_worker(tmp_path, monkeypatch):
    harness = CodexHarness(run_root=tmp_path)
    harness._codex_binary = "codex"
    process = BlockingProcess()
    process_spawned = threading.Event()

    def blocking_popen(*args, **kwargs):
        process_spawned.set()
        return process

    monkeypatch.setattr(codex_harness_module.subprocess, "Popen", blocking_popen)

    run = harness.start_exec_run("wait for shutdown")
    assert process_spawned.wait(timeout=2)

    harness.shutdown(timeout=2)

    assert run.status == "cancelled"
    assert process.terminated is True
    assert not any(worker.is_alive() for worker in harness._workers.values())


def test_codex_retention_bounds_events_runs_and_managed_workspaces(tmp_path):
    harness = CodexHarness(
        run_root=tmp_path,
        max_retained_runs=2,
        max_events_per_run=3,
        retention_seconds=3600,
    )
    active = CodexRun(
        id="active",
        mode="exec",
        command=["codex", "exec", "prompt"],
        sandbox_dir=tmp_path / "active" / "workspace",
        status="running",
    )
    harness._runs[active.id] = active
    for index in range(5):
        harness._append_event(active, {"type": "codex.log", "message": str(index)})

    assert [event["index"] for event in harness.list_events(active.id)] == [2, 3, 4]
    assert [event["message"] for event in harness.list_events(active.id)] == ["2", "3", "4"]

    harness._runs.pop(active.id)
    now = time.time()
    for index in range(3):
        run_id = f"terminal-{index}"
        workspace = tmp_path / run_id / "workspace"
        workspace.mkdir(parents=True)
        run = CodexRun(
            id=run_id,
            mode="exec",
            command=["codex", "exec", "prompt"],
            sandbox_dir=workspace,
            status="completed",
            created_at=now + index,
            completed_at=now + index,
            metadata={"managed_workspace": True},
        )
        harness._runs[run.id] = run

    removed = harness.prune_retained_runs(now=now + 10)

    assert removed == ["terminal-0"]
    assert set(harness._runs) == {"terminal-1", "terminal-2"}
    assert not (tmp_path / "terminal-0").exists()
    assert (tmp_path / "terminal-1").exists()


@pytest.mark.asyncio
async def test_codex_lists_and_streams_stored_events(tmp_path):
    harness = CodexHarness(run_root=tmp_path)
    run = CodexRun(
        id="run-events",
        mode="exec",
        command=["codex", "exec", "prompt"],
        sandbox_dir=tmp_path,
        status="completed",
        events=[{"type": "task.started"}, {"type": "run.completed", "exit_code": 0}],
    )
    harness._runs[run.id] = run

    listed = harness.list_events(run.id)
    streamed = [event async for event in harness.stream_events(run.id)]
    resumed = [event async for event in harness.stream_events(run.id, start_index=1)]

    assert listed == streamed
    assert [event["index"] for event in streamed] == [0, 1]
    assert resumed == [listed[1]]


@pytest.mark.asyncio
async def test_codex_missing_run_raises_for_cancel_list_and_stream(tmp_path):
    harness = CodexHarness(run_root=tmp_path)

    with pytest.raises(CodexHarnessError, match="not found"):
        harness.cancel_run("missing")
    with pytest.raises(CodexHarnessError, match="not found"):
        harness.list_events("missing")
    with pytest.raises(CodexHarnessError, match="not found"):
        await anext(harness.stream_events("missing"))


def process_alive(process):
    try:
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


@pytest.fixture
def owned_process_tree(tmp_path):
    """Real Python descendants only; always reap fixture-owned processes."""
    recorded = []
    roots = []
    helpers = []
    pid_file = tmp_path / "descendants.json"
    grandchild_code = "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)"
    child_code = (
        "import json,os,subprocess,sys,time; from pathlib import Path; "
        f"child=subprocess.Popen([sys.executable, '-c', {grandchild_code!r}]); "
        f"Path({str(pid_file)!r}).write_text(json.dumps([os.getppid(), os.getpid(), child.pid])); "
        "time.sleep(30)"
    )

    def launch(harness, *, parent_exits=False, short=False):
        parent_code = (
            "import subprocess,sys,time; "
            f"child=subprocess.Popen([sys.executable, '-c', {child_code!r}]); "
            + ("time.sleep(0.2)" if parent_exits else "time.sleep(30)")
        )
        command = [sys.executable, "-c", parent_code]
        if short:
            result = {}
            helper = threading.Thread(target=lambda: result.update(harness._run_short(command, timeout=1)))
            helpers.append(helper)
            helper.start()
        else:
            run = CodexRun(id="real-tree", mode="test", command=command, sandbox_dir=tmp_path)
            harness._register_and_start(run)
            roots.append(run)
        deadline = time.monotonic() + 5
        pids = None
        while time.monotonic() < deadline:
            try:
                pids = json.loads(pid_file.read_text())
                break
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            time.sleep(0.01)
        assert pids, "Fixture failed to spawn descendants"
        recorded.extend(psutil.Process(pid) for pid in pids)
        if short:
            return helper, recorded, result
        if parent_exits:
            run.process.wait(timeout=5)
        return run, recorded

    yield launch
    # Use recorded Process identities, not a global process-name kill. This
    # also removes descendants when the regression intentionally fails.
    if not recorded and pid_file.exists():
        for pid in json.loads(pid_file.read_text()):
            try:
                recorded.append(psutil.Process(pid))
            except psutil.NoSuchProcess:
                pass
    cleanup = set(recorded)
    for process in recorded:
        try:
            cleanup.update(process.children(recursive=True))
        except psutil.NoSuchProcess:
            pass
    for process in reversed(list(cleanup)):
        try:
            process.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(cleanup, timeout=3)
    for run in roots:
        if run.process is not None:
            if run.process.poll() is None:
                run.process.kill()
            run.process.wait(timeout=3)
    for helper in helpers:
        helper.join(timeout=3)
        assert not helper.is_alive()


@pytest.mark.parametrize("action", ["cancel", "shutdown"])
@pytest.mark.parametrize("parent_exits", [False, True])
def test_real_descendants_stop_with_run(tmp_path, owned_process_tree, action, parent_exits):
    harness = CodexHarness(run_root=tmp_path)
    # An unrelated process owned by this test must survive the harness cleanup.
    unrelated = harness._spawn_process([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        run, descendants = owned_process_tree(harness, parent_exits=parent_exits)
        started = time.monotonic()
        if action == "cancel":
            harness.cancel_run(run.id)
        else:
            harness.shutdown(timeout=3)
        deadline = time.monotonic() + 2
        while any(process_alive(process) for process in descendants) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not any(process_alive(process) for process in descendants)
        assert time.monotonic() - started < 5
        assert run.status == "cancelled"
        assert unrelated.poll() is None
    finally:
        harness._terminate_process(unrelated, timeout=3)
        harness.shutdown(timeout=1)


def test_short_helper_timeout_stops_descendants(tmp_path, owned_process_tree):
    harness = CodexHarness(run_root=tmp_path)
    started = time.monotonic()
    helper, descendants, result = owned_process_tree(harness, short=True)
    helper.join(timeout=4)
    assert not helper.is_alive()
    deadline = time.monotonic() + 2
    while any(process_alive(process) for process in descendants) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert time.monotonic() - started < 5
    assert result["returncode"] == 1
    assert "timed out" in result["stderr"]
    assert not any(process_alive(process) for process in descendants)


def test_shutdown_does_not_signal_retained_completed_process(tmp_path):
    harness = CodexHarness(run_root=tmp_path)
    process = FakeProcess()
    run = CodexRun(id="retained", mode="test", command=[], sandbox_dir=tmp_path,
                   status="completed", process=process)
    harness._runs[run.id] = run
    harness.shutdown(timeout=0.1)
    assert not process.terminated and not process.killed


def test_cleanup_failure_is_reported(tmp_path, monkeypatch, caplog):
    harness = CodexHarness(run_root=tmp_path)
    run = CodexRun(id="cannot-stop", mode="test", command=[], sandbox_dir=tmp_path,
                   status="running", process=FakeProcess())
    harness._runs[run.id] = run

    def fail_cleanup(*args, **kwargs):
        raise OSError("access denied")

    monkeypatch.setattr(harness, "_terminate_process", fail_cleanup)
    with pytest.raises(CodexHarnessError, match="cleanup failed"):
        harness.cancel_run(run.id)
    assert "access denied" in run.error
    assert run.events[-1]["type"] == "run.cleanup_failed"
    assert "access denied" in caplog.text


@pytest.mark.skipif(codex_harness_module.os.name != "nt", reason="Windows suspended-process failure path")
@pytest.mark.parametrize("failure_stage", ["assignment", "resume"])
def test_windows_containment_failure_reaps_suspended_child(tmp_path, monkeypatch, failure_stage):
    harness = CodexHarness(run_root=tmp_path)
    created = []
    real_popen = subprocess.Popen

    def record_popen(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        created.append(process)
        return process

    def fail_job(process):
        raise OSError("containment failed")

    monkeypatch.setattr(codex_harness_module.subprocess, "Popen", record_popen)
    if failure_stage == "assignment":
        monkeypatch.setattr(codex_harness_module, "_WindowsJob", fail_job)
    else:
        monkeypatch.setattr(psutil.Process, "resume", fail_job)
    marker = tmp_path / "must-not-run"
    try:
        with pytest.raises(OSError, match="containment failed"):
            harness._spawn_process([sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).touch()"])
        assert len(created) == 1
        assert created[0].poll() is not None
        assert not marker.exists()
        if failure_stage == "resume":
            assert created[0]._codex_job._handle is None
    finally:
        for process in created:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=3)


def test_termination_uses_one_deadline(tmp_path, monkeypatch):
    clock = [0.0]
    waits = []

    class StubbornProcess(FakeProcess):
        def wait(self, timeout=None):
            waits.append(timeout)
            clock[0] += timeout
            raise subprocess.TimeoutExpired("fixture", timeout)

    monkeypatch.setattr(codex_harness_module.time, "monotonic", lambda: clock[0])
    process = StubbornProcess()
    with pytest.raises(CodexHarnessError, match="cleanup deadline"):
        CodexHarness._terminate_process(process, timeout=0.5)
    assert process.terminated and process.killed
    assert sum(waits) <= 0.5
