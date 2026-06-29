# Dynamic Subagents and LangGraph Upgrade Plan

Status: implemented
Date: 2026-06-29

## Summary

LangChain's new dynamic subagents pattern lets a Deep Agent write JavaScript orchestration code in a QuickJS interpreter and call `task()` from code. For LangConfig, this creates a product opportunity to support inspectable dynamic workflows: loops, branches, parallel fan-out, typed subagent results, verification passes, tournament patterns, and recursive analysis.

LangConfig is already close architecturally. It has DeepAgents, a LangGraph runtime boundary, checkpointing, `astream_events(version="v2")`, workflow subgraph streaming, flat subagent events, and frontend subagent panels. The missing pieces are the QuickJS dependency, interpreter config, eval safety gates, dynamic event normalization, typed subagent results, and UI that teaches and visualizes dynamic phases.

## Sources

- Blog: https://www.langchain.com/blog/introducing-dynamic-subagents-in-deep-agents
- Dynamic subagents docs: https://docs.langchain.com/oss/python/deepagents/dynamic-subagents
- Interpreter docs: https://docs.langchain.com/oss/python/deepagents/interpreters
- Changelog: https://docs.langchain.com/oss/python/releases/changelog
- Package metadata checked from PyPI for `deepagents==0.6.12`, `langchain==1.3.11`, `langgraph==1.2.6`, and `langchain-quickjs==0.3.2`.

## Current State

Installed backend package versions:

- `deepagents 0.6.8`
- `langchain 1.3.7`
- `langchain-core 1.4.5`
- `langchain-anthropic 1.4.5`
- `langgraph 1.2.4`
- `langchain-quickjs` is not installed

Relevant repo files:

- `backend/services/deepagent_factory.py`: builds DeepAgents, passes `subagents`, `checkpointer`, `store`, `interrupt_on`, and cache. It already avoids duplicate TodoList/Filesystem middleware.
- `backend/models/deep_agent.py`: supports dictionary and compiled subagents, but not interpreter config, dynamic-subagent toggle, PTC allowlist, or subagent response schemas.
- `backend/core/runtimes/langgraph_runtime.py`: owns chat streaming through `astream_events(version="v2")`.
- `backend/core/workflows/executor.py`: already uses `include_subgraphs=True`, event limits, timeouts, cancellation, checkpoint resume, caching, and deferred nodes.
- `backend/core/workflows/events/emitter.py`: detects `task` tool calls and emits `SUBAGENT_START/END/ERROR`.
- `src/features/agents/ui/DeepAgentBuilder.tsx`: no interpreter or dynamic workflow controls yet.
- `src/features/workflows/execution/SubagentPanel.tsx`: flat subagent view, no eval phase grouping or orchestration code view yet.

## Dependency Plan

Recommended requirement floor:

```txt
langchain>=1.3.11,<2
langchain-core>=1.4.8,<2
langchain-anthropic>=1.4.8,<2
langgraph>=1.2.6,<1.3
deepagents[quickjs]>=0.6.12,<0.7
langchain-quickjs>=0.3.2,<0.4
```

Why:

- `deepagents==0.6.12` requires `langchain>=1.3.11`, `langchain-core>=1.4.8`, and `langchain-anthropic>=1.4.7`.
- `langchain-quickjs==0.3.2` requires `deepagents>=0.6.8,<0.8`, `langchain>=1.3.9`, `langchain-core>=1.4.7`, `langgraph>=1.2.5`, and `quickjs-rs>=0.2.3,<0.3.0`.
- `langgraph==1.2.6` keeps the existing `<1.3` line and requires `langchain-core>=1.4.7`.

High-risk changes to test:

1. `CodeInterpreterMiddleware` adds an `eval` tool and persistent QuickJS state.
2. Interpreter-side `task()` and PTC calls do not enforce parent `interrupt_on` per dispatch. Gate `eval`, add approvals inside subagents, or set `subagents=False`.
3. `quickjs-rs` is native. Verify Windows wheel availability.
4. Keep `astream_events(version="v2")`; existing tests show v3 is not compatible with current async iteration code.
5. Preserve the DeepAgents 0.6 duplicate-middleware fix. Do not manually append TodoList/Filesystem middleware.

## Backend Feature Plan

1. Add `InterpreterConfig` to `DeepAgentConfig`.

```python
class InterpreterConfig(BaseModel):
    enabled: bool = False
    mode: Literal["thread", "turn", "call"] = "thread"
    memory_limit_bytes: int = 64 * 1024 * 1024
    timeout_seconds: float = 5.0
    max_ptc_calls: int = 256
    max_result_chars: int = 4000
    capture_console: bool = True
    dynamic_subagents: bool = True
    ptc_tool_allowlist: list[str] = Field(default_factory=list)
    require_eval_approval: bool = True
```

2. Wire `CodeInterpreterMiddleware` in `DeepAgentFactory`.

- Import `CodeInterpreterMiddleware` from `langchain_quickjs` only when enabled.
- Raise a clear validation error if missing. Do not silently fall back.
- Pass `subagents=config.interpreter.dynamic_subagents`.
- Resolve `ptc_tool_allowlist` against loaded tools.
- Merge `interrupt_on["eval"]` when eval approval is enabled.

3. Add typed dynamic results.

- Extend `SubAgentConfig` with `response_schema_name`, `response_schema`, and `response_format_strategy`.
- Resolve schemas through the existing custom schema registry.
- Pass `response_format` into dictionary subagent configs.

4. Normalize dynamic subagent stream events.

`langchain-quickjs` emits custom stream payloads shaped like:

```json
{
  "type": "subagent",
  "phase": "start|complete|error",
  "id": "ptc_task_...",
  "eval_id": "...",
  "subagent_type": "reviewer",
  "label": "Review foo.ts",
  "description": "...",
  "duration_ms": 1234,
  "error": "..."
}
```

Map these to the existing `subagent_start`, `subagent_end`, and `subagent_error` SSE frames with `is_dynamic`, `eval_id`, `phase`, and `duration_ms`.

5. Keep LangGraph streaming conservative.

- Upgrade to `langgraph 1.2.6`.
- Keep all `astream_events(..., version="v2")` call sites.
- Add tests for custom subagent events and `include_subgraphs=True`.
- Evaluate v3/StreamPart in a separate adapter project later.

## Frontend UX Plan

1. Add an Interpreter section to `DeepAgentBuilder`.

- Enable JavaScript interpreter.
- Enable dynamic subagents from interpreter `task()`.
- Choose persistence mode: `thread`, `turn`, `call`.
- Configure timeout, memory, max PTC calls, max result chars.
- Select PTC tool allowlist.
- Toggle eval approval.
- Show beta and safety warnings.

2. Extend subagent configuration.

- Structured result schema selector.
- JSON schema preview.
- Presets: analyzer, verifier, synthesizer, critic, reducer.
- Examples using `responseSchema` and `Promise.all`.

3. Upgrade execution visualization.

- Group dynamic subagents by `eval_id` as workflow phases.
- Show running, complete, error counts and durations.
- Add orchestration-code view for `eval` input and captured `console.log`.
- Render typed result summaries.
- Preserve current flat cards for normal configured `task` calls.

4. Add education and templates.

- Add a "Dynamic Workflow Agent" template with interpreter enabled, eval approval on, dynamic subagents on, and PTC disabled by default.
- Update `LearnLangChainTab` with current docs links and a safety section.

## Verification

Dependency checks:

- Resolver dry-run or temp venv install.
- `python -m pip check`.
- Import `deepagents`, `langchain_quickjs.CodeInterpreterMiddleware`, `langgraph`, and provider packages.

Backend tests:

- Existing `backend/tests/test_chat_stream_contract.py`.
- Existing `backend/tests/test_deepagent_checkpointer.py`.
- Add tests for interpreter config serialization, middleware attachment, missing package errors, eval approval merge, custom subagent event mapping, and PTC allowlist validation.

Frontend checks:

- `npm run build`.
- Type coverage for dynamic subagent event payloads.
- Visual QA for builder controls and execution panel overflow.

Manual smoke:

1. Create a dynamic workflow agent with two simple subagents and eval approval on.
2. Prompt a workflow that asks both reviewers to inspect text and synthesize disagreements.
3. Confirm eval approval appears.
4. Confirm dynamic subagents stream grouped by phase.
5. Confirm checkpointed chat history persists and cleanup still deletes checkpoints.

Implementation notes:

- Backend and frontend implementation completed on 2026-06-29.
- QuickJS packages installed successfully on Windows, including `quickjs-rs` and `wasmtime`.
- Import checks pass for `deepagents`, `langchain`, `langchain_core`, `langchain_anthropic`, `langgraph`, and `langchain_quickjs.CodeInterpreterMiddleware`.
- `pip check` still reports pre-existing dependency conflicts in the Google ADK, LlamaIndex, Kubernetes, OpenTelemetry, and Transformers dependency groups. These are not introduced by `langchain-quickjs`, but they should be resolved before treating the whole backend environment as dependency-clean.

## Phases

1. Dependency probe: patch requirements, install, run import checks and focused tests.
2. Backend feature gate: config, middleware, eval approval, PTC allowlist, event normalization.
3. Frontend controls and trace UI: builder settings, event types, phase grouping, schema selector.
4. Education/templates: dynamic workflow template and updated Learn LangChain content.
5. Advanced follow-up: DeltaChannel checkpoint diagnostics, v3 stream adapter, remote async subagents.
