# September 2026 branch and review plan

This plan accounts for the 328 files staged on September 25, 2026, on top of
`943bf78` (`codex/onboarding-hermes-platform-tools`). The staged work contains
40,941 added and 16,496 removed lines, including lockfiles and generated data.
Those counts describe the captured source, not a single proposed pull request.

The complete path inventory is in [BRANCH_INVENTORY_2026-09.json](BRANCH_INVENTORY_2026-09.json).
Every original path has one primary owner. `shared_files` records files that
need intermediate versions in several branches; the inventory is not a list
to pass directly to `git add`.

## Preservation and base

The original staged tree remains in the main working directory. A local backup
ref, `backup/uncommitted-2026-09-25`, points to snapshot
`dabf36b313197854f9eeab62012918f1728a263c`. It is a recovery artifact and must not
be pushed as a feature branch. No existing public history is rewritten.

The existing onboarding branch has three commits above `origin/main`:

- `05ba60d`: guarded local automation workspace.
- `66f377a`: reproducible fresh-clone onboarding.
- `943bf78`: experimental Tauri shell configuration validation.

These are an explicit prerequisite. Initial review branches target that branch
or a prepared successor, so their diffs do not repeat the onboarding work.
The first wave was validated and merged into the onboarding branch as PRs
[#73](https://github.com/LangConfig/langconfig/pull/73),
[#74](https://github.com/LangConfig/langconfig/pull/74), and
[#75](https://github.com/LangConfig/langconfig/pull/75). The `main` integration
includes these three onboarding commits as well as those completed slices;
its final PR checks validate the combined tree against `main`.

## Branch queue

Branch names below are planned until a commit is recorded in the publication
table. Later branches build on reviewed prerequisites; separate branch names
do not imply independent cherry-pickability. Prefer the smaller boundaries
below, with explicit shared-file edits, over copying final integration files
into earlier branches.

| Branch (`codex/` prefix) | Changes and review boundary | Required verification |
| --- | --- | --- |
| `langchain-middleware-compat` | Inherit the public LangChain middleware contract, repair PII tools, resolve inherited audit failures, preserve existing encryption keys during setup, and contain local CLI process trees. | Middleware/PII/factory regressions, complete intermediate backend suite, real pinned embedding comparison, full resolved advisory scan, fail-closed policy tests, ciphertext preservation, and real Windows/Linux descendant cleanup. |
| `quality-gates` | Conventional lint/type/format commands, exact initial scopes, build import-graph guard, feature-push CI, contributor instructions and this inventory. Preserve existing runtime dependency versions. | Clean npm install, declared lint/format/type checks, build including lazy-import guard, disposable-DB safety tests, CI configuration review. |
| `runtime-schema-foundation` | Add migrations 023–026 and matching ORM fields/tables. No worker or API activation. Preserve populated revision-022 records. | Upgrade, downgrade and reupgrade on a disposable database; compare legacy rows; validate global/project skill uniqueness and ORM registration. |
| `dependency-refresh` | Universal hashed Python lock, compatible LangChain/Deep Agents packages, Vite 8/Rolldown/TypeScript 7, Tauri dependencies, fail-closed advisory assessment. Preserve `reactflow` until canvas migration. | Hashed install, pip consistency, universal lock comparison, Python OS/version resolution matrix, compatibility tests, npm audit, Rust audit/locked check, frontend build. |
| `mcp-stdio-sessions` | Official owned stdio sessions, cancellation/concurrency, discovery refresh, multimodal results, explicit regular-agent server bindings. Include only required direct SDK dependencies and factory integration. | Real fixture subprocess, simultaneous requests, timeout/cancellation/crash/cleanup, schema checks, actual factory binding, targeted lint and syntax checks. |
| `model-catalog` | Provider catalog/metadata, generation, request parameter compatibility, usage normalization, capability API. UI pricing changes must include all nullable-cost consumers when exposed. | Generation drift, provider-request fixtures, profile/capability tests, usage and unknown-cost behavior. No paid account or quality claims. |
| `agent-runtime-skills` | Trusted runtime context, structured output with tools, execution-policy middleware, scoped skill loading, native memory/search, schema validation, reliable tool loading and agent configuration persistence. | Actual factory/runtime tests, scope isolation, project RAG binding, schema/tool failures, native memory against PostgreSQL, supported SDK compatibility. |
| `durable-workflow-execution` | Per-run identity, stream contracts, cancellation/deadlines, leases/recovery, approvals, checkpoint inspection/continuation/fork/retention, budgets/cache rules and experimental background jobs. | Competing approvals, cancellation and stale events, process crash/restart, parent/child budgets, checkpoint selection, history cleanup; corresponding unit/browser contracts. |
| `standalone-workflow-exports` | Restricted condition grammar, validated standalone export subset, code-preview boundary, export UI and legacy exporter removal. | Independently installed archives execute supported graphs; unsupported enabled platform features fail explicitly; expression rejection tests and preview/API checks. |
| `workflow-evaluations` | Immutable version comparisons, fixture/provider budgets, separate correctness/token/cost/latency records, mounted comparison UI. | Saved comparison reload, fixture determinism and budget/unsupported-mode failures; graph-execution tests and browser comparison. |
| `verified-workflow-recipes` | Correct and refresh built-ins with provenance, preserve user copies/edits, retire unsupported starters, deterministic recipe execution gate. | Execute every supported recipe with fixture providers, revision/loop/approval/fan-in paths, template refresh preserving modified records. |
| `canvas-migration` | React Flow 12, saved graph/viewport/policy persistence, nullable run metrics, execution-panel integration and legacy node compatibility. Remove old `reactflow` only here. | Canvas save/reload/connect/reconnect/drag/zoom/keyboard/export/browser contracts, cost unknown vs zero, Spatial and export lazy-loading. |
| `agent-builder` | Simplified library creation, faithful runtime configuration transfer, scoped skill selection, capability picker, bounded help overlays, filesystem guidance, desktop/mobile layout. | Create/edit/reload/runtime-mode preservation, actual canvas insertion and Save to Library paths, keyboard/focus/layout tests at desktop/mobile sizes. |
| `release-integration` | Final generated API drift checks, expanded lint scopes, coverage baseline, all feature CI gates, environment isolation and consolidated setup/upgrade documentation. Feature-specific wiring lands with its feature, not postponed here. | Full disposable-DB backend suite and coverage, frontend units/browser/build, generated artifacts, locked dependencies/advisories, fresh-clone instructions, final diff review. |

The compatibility fix precedes tooling, and schema follows tooling. MCP must
follow the dependency refresh: its SDK 2.2.0 pin conflicts with the starting
branch's `google-adk>=1.22.0,<2.0.0`, which requires MCP below version 2.
Passing the MCP tests in the already-upgraded development environment does
not resolve that install conflict. The isolated MCP extraction is retained
locally, but must not be published until its parent supplies the ADK upgrade
and the complete dependency set resolves.
Dependency and model compatibility precede the new runtime. Exports,
evaluations and recipes depend on that runtime. Canvas and builder changes
need explicit integration with the corresponding backend contracts.

## Shared-file rules that prevent broken branches

1. Keep migrations in their existing linear chain: 023 dispatch → 024 skills →
   025 evaluations/runtime snapshots → 026 jobs. Recovery reads fields added in
   025 and ordinary recovery queries job records. This is why the complete
   additive schema lands before runtime activation.
2. Recovery and jobs currently call each other. Keep them in one runtime
   branch unless their hooks are deliberately separated and verified. Never
   commit recovery without the job service it imports.
3. Split `factory.py`, `deepagent_factory.py`, `executor.py`, workflow routes
   and `main.py` by behavior. For example, the MCP branch takes only explicit
   server-tool binding hooks; worker startup and evaluation routers wait for
   their services. The safe condition evaluator is needed by the runtime
   before the complete standalone export feature.
4. Several backend tests import fixtures from `test_workflow_evaluation.py`,
   which itself imports the evaluation service. Extract neutral fixtures before
   moving those tests earlier. Recovery/job and structured-output/skill tests
   also have shared fixture dependencies.
5. Regenerate API types from the routes present at each stack tip. The generator
   imports `main.app`; a final generated file must not appear before its routes.
6. `WorkflowCanvas`, `RealtimeExecutionPanel`, `WorkflowResults`,
   `NodeConfigPanel`, `api-client.ts`, and workflow types contain multiple
   features. Use deliberate intermediate versions, including the actual mounts
   and callers, and compile each branch. Model pricing returns `number | null`;
   change its consumers atomically rather than coercing unknown costs to zero.
7. Keep backend stream fixtures with frontend streaming tests. Keep evaluation
   E2E data with its component test. The canvas browser spec also contains a
   background-job case; move that case with its feature.
8. Add CI commands only when their scripts, fixtures and features exist. The
   staged final workflow references recipes, API generation and browser tests
   absent from the starting branch. The first tooling branch must not copy it
   wholesale.

## Documentation delivered with each feature

Every branch description must state the original problem, resulting behavior,
prerequisite branch, exact tests run and any limitations. Keep its behavior
documentation in the same branch as the code:

| Feature | Captured documentation |
| --- | --- |
| Schema foundation | [Runtime schema and migration guide](RUNTIME_SCHEMA.md) |
| Dependency/model upgrade | `docs/AUDIT_2026-09.md` (historical audit; retain its date) |
| MCP | `docs/MCP_STDIO.md` |
| Recovery/checkpoints and jobs | `docs/CHECKPOINTS.md`, `docs/BACKGROUND_JOBS.md` |
| Skills and agent builder | `docs/DEEP_AGENT_SKILLS.md`, `docs/DEEP_AGENTS.md`, `docs/DEEP_AGENT_BUILDER_2026-09.md` |
| Exports/evaluations | `docs/EXPORTS.md`, `docs/EVALUATIONS.md` |
| Recipes | `docs/WORKFLOW_RECIPES_2026-09.md`, `docs/RECIPE_EVALUATIONS.md` |
| Canvas | `docs/CANVAS_MIGRATION.md` |
| Consolidated upgrade | `docs/SETUP.md`, `docs/UPGRADE_2026-09.md`, README |

These feature files remain in the captured source until their owning branch
is prepared. Add explicit `.gitignore` exceptions for new public guides so
future edits/new clones do not depend on force-adding ignored documentation.

Use [QUALITY_GATES.md](QUALITY_GATES.md) for checks that exist on the bootstrap
branch. Later branches extend that guide together with their enforced scopes.
The final staged Biome configuration checks four interfaces, Ruff checks four
Python modules and mypy checks three. Those checks are incremental adoption,
not whole-repository lint/type coverage. The 12 Biome `any` warnings recorded
for that captured configuration belong to the unsplit source; they do not
describe the narrower first-wave lint gate.

## Fresh verification of the captured integration tree

The following evidence is from September 25, 2026, Windows, Node 22.17.0 and
the project's Python 3.12.10 environment. It validates the unsplit source,
not every future intermediate branch. Branch-specific checks are required
again after extraction.

| Gate | Result |
| --- | --- |
| Frontend unit/components | 116 passed in 26 files |
| Chromium browser contracts | 17 passed; expected error-path logs and some existing abort/deprecation console messages remain |
| Production build and lazy-import guard | Passed |
| TypeScript and focused Biome | Passed; 12 warnings in the current narrow scope |
| Focused mypy / Ruff | Passed (3 / 4 source modules) |
| Generated API/OpenAPI agreement | Passed |
| Installed Python dependency consistency | Passed |
| npm advisory check / dependency-policy regression tests | Zero npm advisories; 36 policy tests passed |
| Full backend suite with coverage | 1,297 passed, 8 skipped (manual Playwright tools script excluded); 2,036 warnings retained |
| Coverage / Python lock | 41.213% statements (13,539 / 32,851), above 22.4%; all five packages measured; universal hashed lock agrees with manifest |
| Current external dependency advisories / OS matrix / packaged desktop | Not established by the checks above |

Do not reuse September 9 test counts as fresh release evidence. Python and Rust
advisory exceptions in the captured policy expire October 8, 2026; do not
silently extend them. Paid model quality, remote MCP HTTP/OAuth and packaged
desktop behavior are outside the validated scope. The existing plan's
background-job evaluation UI cases remain outstanding even though separate
job integration/process tests exist.

## Publication record and continuation

| Branch | Pull request / publication | Validation scope |
| --- | --- | --- |
| `codex/langchain-middleware-compat` | [PR #73](https://github.com/LangConfig/langconfig/pull/73) | Complete backend suite, real pinned embeddings, dependency consistency/security, setup key preservation, and real subprocess cleanup on Windows and Linux |
| `codex/quality-gates` | [PR #74](https://github.com/LangConfig/langconfig/pull/74), follows #73 | Complete backend suite, database safety, scoped lint/format/types/build; includes the enforcing dependency-security prerequisite |
| `codex/runtime-schema-foundation` | [PR #75](https://github.com/LangConfig/langconfig/pull/75), follows #74 | Complete backend suite, populated migration downgrade/reupgrade, expanded Ruff, frontend lint/types/build and dependency security |
| `codex/mcp-stdio-sessions` | Local extraction; not published | Awaiting dependency-refresh parent (ADK 1 / MCP 2 install conflict) |
| Remaining queue | Not published | Requires extraction and branch-specific gates |

The shared CI failure was traced to inherited cryptography/embedding constraints
and an informational audit with broad advisory ignores. The compatibility
prerequisite now supplies four patched package pins and an enforcing assessment
gate; see [DEPENDENCY_SECURITY.md](DEPENDENCY_SECURITY.md). Only the existing
NLTK 3.10.3 assessment remains, with its October 8 expiry unchanged. A passing
policy gate does not mean zero vulnerabilities. The complete SDK/lock refresh
remains separate, and npm versions are still the earlier pins.

The first publication wave is #73 → #74 → #75. These PRs merged in dependency
order on `codex/onboarding-hermes-platform-tools`, ending at `60e53e3`.
The main integration branch carries that complete tree forward. The remaining
feature queue and the preserved staged source are outside this landing.
After the main-bound review fixes, the local backend run passed **734 tests**
with **7 skipped and 80 warnings**, using a disposable PostgreSQL database.
Focused Ruff, installed Python dependency consistency, frontend scoped lint,
formatting, application types, production build, and lazy-import checks passed.
The **8 Chromium Hermes tests** passed against the real component with mocked
APIs, covering draft approval, stream ownership, and visible activation failures.
These results describe the first-wave integration tree, not the
historical 1,297-test unsplit tree above. Current-head PR checks still need to
pass before the main merge; no release version is being created by this landing.
Their linked PR descriptions and checks record the final commit-specific CI
results and merge state. Every job must pass on the current PR head; the old
workflow's successful overall conclusion hid a failing informational audit.
Normal merges propagate fixes and establish each squash destination as an
ancestor of the next child without rewriting published history.
The branches have no configured required-check list; successful jobs should not
be confused with enforced branch protection. Next prepare the dependency refresh,
then rebase the local MCP extraction
onto that compatible parent and rerun its full install and runtime checks.

For each completed slice, commit its implementation, regressions and guide;
push with normal upstream tracking; open a draft PR against the stated parent;
record the commit and checks. Review and merge parents before children.
If a parent is squash-merged, integrate the updated destination into the child
before changing its PR base. A normal merge preserves published history and
establishes the destination as an ancestor; verify the resulting PR diff contains
only the child's changes and rerun CI. Do not merely change the PR base or
force-push published branches without coordinating a history change.

Before declaring the complete split finished, compare the assembled tip with
the preserved snapshot. Every difference must be an intentional, documented
cleanup. Keep the backup until all original changes are accounted for.

Additional cleanup beyond the captured source currently consists of the schema
constraint-name alignment, model export registration, new migration regressions
with clean schema teardown for repeatable database sequences,
the PII profile-failure regression, the enforcing security assessment gate and
its tests, preservation of existing setup encryption keys, and owned CLI
process-tree containment with real subprocess regressions. Main-bound review
also adds public-only native HTTP connections (including DNS and redirects),
Hermes draft approval/stream ownership browser regressions, and working schedule
and file-watch activation with explicit failure results. Preserve those
improvements when assembling the final tip. Do not restore obsolete Accelerate
exceptions from the captured snapshot: current resolution selects a patched version.
Bootstrap quality configurations intentionally remain narrower than the captured
final configurations until their corresponding features land.
