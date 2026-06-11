# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Workflow Recipes - Pre-configured Multi-Node Workflow Templates.

These recipes define complete workflow patterns that can be inserted into the
canvas as a set of connected nodes, and seeded into the database as
ready-to-run template workflows.

Each recipe includes:
- nodes: List of node configurations with positions
- edges: List of edge connections between nodes
- metadata: Recipe name, description, category, icon, tags

EXECUTOR CONTRACTS (core/workflows/executor.py) that these recipes honor:

- Node shape: the executor resolves a node's type from top-level ``node["type"]``
  (falling back to ``node["data"]["agentType"]`` only when type == "default"),
  and reads ALL runtime configuration from top-level ``node["config"]`` - NOT
  from ``node["data"]["config"]`` (that is the ReactFlow/canvas shape). Recipes
  therefore carry the config in BOTH places: top-level for direct execution of
  seeded workflows, and under ``data`` so the canvas can render/edit them.
  ``recipe_to_dict()`` rewrites top-level ``type`` to "custom" for the canvas
  insert API (ReactFlow only knows the "custom" node component); on save the
  frontend regenerates top-level type/config from ``data``.

- CONDITIONAL_NODE: the executor evaluates ``config["condition"]`` (a Python
  expression with ``state`` in scope) and sets ``state["conditional_route"]``
  to ``config["routing_map"]["true"|"false"]``. The graph router then matches
  that value against the OUTGOING EDGE LABELS (``edge["data"]["label"]``).
  Routing therefore uses semantic route labels ("PASS"/"REVISE") as both
  routing_map values and edge data labels - never node ids, which would break
  when the canvas remaps node ids on recipe insertion.

- LOOP_NODE: the executor tracks per-node iteration counts, exits when
  ``iteration >= max_iterations`` (or when ``exit_condition`` evaluates True),
  and sets ``state["loop_route"]`` to "continue" or "exit". The graph router
  matches those against outgoing edge ``data.label`` values, so every loop
  node has exactly one edge labeled "continue" (back-edge) and one labeled
  "exit" (forward). ``loop_target`` in config is informational only - the
  "continue" edge does the actual wiring.

- Critic capture: when a node's label or agent type contains "critic", the
  executor copies the node's final message content into
  ``state["critic_output"]``, which conditions can then inspect. Critic
  prompts end with an explicit verdict contract (VERDICT: PASS / REVISE).

- Deferred fan-in: ``config["deferred"] = True`` compiles the node with
  LangGraph ``defer=True`` so it waits for all parallel branches to finish.
  Plain multiple out-edges from one node create the parallel fan-out.

- TOOL_NODE: executes a tool directly (no agent). Config keys: ``tool_type``
  ("mcp" loads native tools), ``tool_id``, ``tool_params``. String params
  support ``{{directive}}``, ``{{previous_output}}`` and ``{{state.<key>}}``
  interpolation. NOTE: a tool node OVERWRITES ``state["current_directive"]``
  with its output, so downstream tool nodes that need the ORIGINAL user input
  must use ``{{state.query}}``. Agent prompts do NOT get template
  interpolation - agents read tool outputs from the message history instead.
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass


@dataclass
class WorkflowRecipe:
    """A complete workflow recipe with nodes and edges."""
    recipe_id: str
    name: str
    description: str
    category: str
    icon: str
    tags: List[str]
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


# =============================================================================
# NODE / EDGE BUILDERS
# =============================================================================

def _base_config() -> Dict[str, Any]:
    """Full config field set every node ships with (executor + canvas)."""
    return {
        "model": "none",
        "temperature": 0,
        "system_prompt": "",
        "native_tools": [],
        "tools": [],
        "cli_tools": [],
        "custom_tools": [],
        "timeout_seconds": 0,
        "max_retries": 0,
        "enable_model_routing": False,
        "enable_parallel_tools": False,
        "enable_memory": False,
        "enable_rag": False,
    }


def _make_node(
    node_id: str,
    label: str,
    agent_type: str,
    x: int,
    y: int,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a node in DB/executor format with the canvas shape mirrored in data."""
    cfg = _base_config()
    cfg.update(config)
    return {
        "id": node_id,
        "type": agent_type,  # Executor resolves node type from here
        "position": {"x": x, "y": y},
        "config": cfg,       # Executor reads runtime config from here
        "data": {
            "label": label,
            "agentType": agent_type,
            "model": cfg.get("model", "none"),
            "config": cfg,   # Canvas reads/edits config from here
        },
    }


def _agent_node(
    node_id: str,
    label: str,
    agent_type: str,
    x: int,
    y: int,
    *,
    model: str,
    system_prompt: str,
    temperature: float = 0.3,
    fallback_models: Optional[List[str]] = None,
    native_tools: Optional[List[str]] = None,
    timeout_seconds: int = 300,
    max_retries: int = 2,
    enable_model_routing: bool = False,
    enable_parallel_tools: bool = False,
    enable_memory: bool = False,
    enable_rag: bool = False,
    deferred: bool = False,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build an LLM agent node with the complete config field set."""
    config: Dict[str, Any] = {
        "model": model,
        "fallback_models": fallback_models or [],
        "temperature": temperature,
        "system_prompt": system_prompt,
        "native_tools": native_tools or [],
        "timeout_seconds": timeout_seconds,
        "max_retries": max_retries,
        "enable_model_routing": enable_model_routing,
        "enable_parallel_tools": enable_parallel_tools,
        "enable_memory": enable_memory,
        "enable_rag": enable_rag,
    }
    if deferred:
        # LangGraph defer=True: node waits for ALL incoming parallel branches
        config["deferred"] = True
    if extra:
        config.update(extra)
    return _make_node(node_id, label, agent_type, x, y, config)


def _control_node(
    node_id: str,
    label: str,
    control_type: str,
    x: int,
    y: int,
    extra_config: Optional[Dict[str, Any]] = None,
    description: str = "",
) -> Dict[str, Any]:
    """Build a control node (START/END/OUTPUT/CHECKPOINT/CONDITIONAL/LOOP/APPROVAL)."""
    config: Dict[str, Any] = {
        "system_prompt": description or f"{control_type}: workflow control node.",
        "control_type": control_type,
    }
    if extra_config:
        config.update(extra_config)
    return _make_node(node_id, label, control_type, x, y, config)


def _tool_node(
    node_id: str,
    label: str,
    tool_id: str,
    tool_params: Dict[str, Any],
    x: int,
    y: int,
) -> Dict[str, Any]:
    """Build a deterministic TOOL_NODE that runs one native tool directly."""
    config = {
        "system_prompt": f"TOOL_NODE: deterministic call to native tool '{tool_id}'.",
        "tool_type": "mcp",  # "mcp" loads from tools.native_tools (TOOL_NAME_MAP)
        "tool_id": tool_id,
        "tool_params": tool_params,
    }
    return _make_node(node_id, label, "TOOL_NODE", x, y, config)


def _edge(
    edge_id: str,
    source: str,
    target: str,
    label: Optional[str] = None,
) -> Dict[str, Any]:
    """Build an edge. ``label`` is set both at top level (canvas display) and in
    ``data.label`` (what the executor's conditional/loop routers match against)."""
    edge: Dict[str, Any] = {
        "id": edge_id,
        "source": source,
        "target": target,
        "type": "smoothstep",
    }
    if label is not None:
        edge["label"] = label
        edge["data"] = {"label": label}
    return edge


# Shared verdict contract appended to every critic prompt. The executor's
# critic capture + our CONDITIONAL_NODE conditions depend on this exact line.
_VERDICT_CONTRACT = """
CRITICAL OUTPUT CONTRACT:
End your review with exactly one line, on its own line, and nothing after it:
VERDICT: PASS
or
VERDICT: REVISE"""

# Condition used by every PASS/REVISE gate. Matches the verdict line only
# (not any incidental use of the word "pass" in the critique body).
_PASS_CONDITION = "'VERDICT: PASS' in str(state.get('critic_output', '')).upper()"


# =============================================================================
# DEEP RESEARCH WORKFLOW RECIPE
# =============================================================================
# Pattern: Planner -> Researcher -> Writer -> Critic -> PASS/REVISE gate with
# a LOOP_NODE on the REVISE path (max 3 iterations) -> Output.
#
# Loop protection choice: the REVISE path routes through a LOOP_NODE with
# max_iterations=3 (rather than an iteration guard inside the conditional
# expression) because the executor natively tracks per-loop-node iteration
# counts and force-exits at the cap - no extra state bookkeeping required.

DEEP_RESEARCH_RECIPE = WorkflowRecipe(
    recipe_id="deep_research_workflow",
    name="Deep Research",
    description="Multi-agent research pipeline: plan, collect, synthesize, then iterate writer-vs-critic until the report passes review (capped at 3 revision loops).",
    category="research",
    icon="science",
    tags=["research", "multi-agent", "reflection", "parallelization"],
    nodes=[
        _control_node(
            "node-dr-start", "Start", "START_NODE", 50, 260,
            description="START node: Entry point for the deep research workflow.",
        ),
        _agent_node(
            "node-dr-planner", "Research Planner", "deep_research_planner", 310, 260,
            model="claude-sonnet-4-6",
            fallback_models=["gpt-5.4"],
            temperature=0.3,
            system_prompt="""ROLE: Expert Research Strategist.
EXPERTISE: Information architecture, research methodology, query formulation.
GOAL: Analyze the main research topic and decompose it into a comprehensive list of focused, independent sub-queries.

PROCESS:
1. Understand the scope and depth required for the main topic
2. Identify key concepts, entities, timelines, relationships, and perspectives
3. Formulate 4-8 specific questions that, when answered collectively, provide complete coverage
4. Ensure questions are independent and can be researched in parallel

CONSTRAINTS:
- Questions must be specific and answerable through web research
- Avoid overlap between questions
- Cover all essential aspects of the topic

OUTPUT FORMAT: JSON array of strings only. Example:
["What are the current market trends in X?", "Who are the key players in Y?", "What are the technical challenges in Z?"]

CRITICAL: Your response must be ONLY the JSON array, nothing else.""",
        ),
        _agent_node(
            "node-dr-researcher", "Field Researcher", "field_researcher", 570, 260,
            model="gpt-5.4-mini",
            fallback_models=["gpt-5.4", "gemini-2.5-flash"],
            temperature=0.3,
            native_tools=["web_search"],
            enable_model_routing=True,
            enable_parallel_tools=True,
            system_prompt="""ROLE: Diligent Data Collector and Analyst.
EXPERTISE: Web research, information synthesis, source evaluation, citation formatting.
GOAL: Investigate each research question from the plan using the 'web_search' tool and synthesize findings into factual summaries.

PROCESS:
1. Work through the research questions provided by the planner
2. Formulate precise search queries for each question
3. Use the 'web_search' tool to gather data from multiple sources
4. Evaluate source credibility and relevance
5. Synthesize findings into clear, factual summaries per question

CRITICAL REQUIREMENTS:
- Include citations for all claims using format: [Source Title](URL)
- Distinguish between facts and opinions
- Note any conflicting information from different sources
- Focus on recency and relevance

OUTPUT: A findings section per research question, each with inline citations.""",
        ),
        _agent_node(
            "node-dr-writer", "Report Writer", "report_writer", 830, 260,
            model="claude-sonnet-4-6",
            fallback_models=["gpt-5.4"],
            temperature=0.5,
            timeout_seconds=300,
            enable_memory=True,
            system_prompt="""ROLE: Expert Technical Writer and Research Analyst.
EXPERTISE: Report writing, information synthesis, technical communication, academic writing standards.
GOAL: Compile the research findings into a cohesive, professional, comprehensive report.

INPUTS PROVIDED IN CONTEXT:
- Original research query
- Research findings from the field researcher
- (On revision passes) Critique feedback from the report critic

PROCESS:
1. Analyze all findings, identifying themes, patterns, and connections
2. Reconcile any contradictory information
3. Structure the report logically:
   - Executive Summary
   - Introduction (context and scope)
   - Main Body (organized by themes or sub-topics)
   - Conclusions and Key Takeaways
   - Sources/References
4. Integrate citations accurately throughout: [Source Title](URL)

REVISION MODE (when a critique appears in the conversation):
- Address EVERY critique point systematically
- Enhance depth where requested, improve clarity and structure
- Add missing information and verify all citations

STYLE: Objective, professional Markdown. No self-referential language.""",
        ),
        _agent_node(
            "node-dr-critic", "Report Critic", "report_critic", 1090, 260,
            model="gpt-5.4",
            fallback_models=["claude-sonnet-4-6"],
            temperature=0.2,
            native_tools=["web_search"],
            system_prompt="""ROLE: Meticulous Editor and Quality Assurance Specialist.
EXPERTISE: Technical editing, fact-checking, academic standards, research methodology.
GOAL: Evaluate the report draft against quality standards and provide actionable feedback.

EVALUATION CRITERIA:
1. Accuracy & Source Quality - facts correct, sources credible and properly cited
2. Depth & Completeness - fully addresses the original query, no obvious gaps
3. Structure & Clarity - well-organized, logical, professional writing
4. Objectivity & Balance - viewpoints represented, bias minimized

OUTPUT FORMAT:
Numbered critique points, each naming the section concerned and the specific
revision required. If the report meets a high standard on all four criteria,
say so briefly instead.
""" + _VERDICT_CONTRACT,
        ),
        _control_node(
            "node-dr-conditional", "Quality Gate", "CONDITIONAL_NODE", 1350, 260,
            description="Routes on the critic's verdict: PASS publishes the report, REVISE sends it back through the revision loop.",
            extra_config={
                # Matches the critic's "VERDICT: PASS" line captured in state.critic_output.
                "condition": _PASS_CONDITION,
                # Values are semantic route labels matched against edge data.label
                # (NOT node ids - see module docstring). "default" makes eval
                # errors fail forward to publication instead of looping forever.
                "routing_map": {"true": "PASS", "false": "REVISE", "default": "PASS"},
            },
        ),
        _control_node(
            "node-dr-loop", "Revision Loop (max 3)", "LOOP_NODE", 1350, 430,
            description="Caps writer/critic revision cycles at 3, then force-exits to output with the latest draft.",
            extra_config={
                "max_iterations": 3,
                "exit_condition": "",
                # Informational only - the 'continue'-labeled edge does the wiring.
                "loop_target": "node-dr-writer",
            },
        ),
        _control_node(
            "node-dr-output", "Final Report", "OUTPUT_NODE", 1610, 260,
            description="OUTPUT node: formats the final research report and run transcript.",
        ),
        _control_node(
            "node-dr-end", "End", "END_NODE", 1610, 430,
            description="END node: terminus of the deep research workflow.",
        ),
    ],
    edges=[
        _edge("e-dr-1", "node-dr-start", "node-dr-planner"),
        _edge("e-dr-2", "node-dr-planner", "node-dr-researcher"),
        _edge("e-dr-3", "node-dr-researcher", "node-dr-writer"),
        _edge("e-dr-4", "node-dr-writer", "node-dr-critic"),
        _edge("e-dr-5", "node-dr-critic", "node-dr-conditional"),
        _edge("e-dr-6", "node-dr-conditional", "node-dr-output", label="PASS"),
        _edge("e-dr-7", "node-dr-conditional", "node-dr-loop", label="REVISE"),
        _edge("e-dr-8", "node-dr-loop", "node-dr-writer", label="continue"),
        _edge("e-dr-9", "node-dr-loop", "node-dr-output", label="exit"),
        _edge("e-dr-10", "node-dr-output", "node-dr-end"),
    ],
)


# =============================================================================
# LEARNING RESEARCH WORKFLOW RECIPE
# =============================================================================
# Pattern: Memory Review -> Plan -> Research -> Synthesize -> Assimilate -> Output

LEARNING_RESEARCH_RECIPE = WorkflowRecipe(
    recipe_id="learning_research_workflow",
    name="Learning Research",
    description="Research workflow with a learning loop: recalls prior knowledge, fills gaps with external research, synthesizes findings, and stores new insights for future runs.",
    category="research",
    icon="school",
    tags=["research", "memory", "learning", "rag", "multi-agent"],
    nodes=[
        _control_node(
            "node-lr-start", "Start", "START_NODE", 50, 260,
            description="START node: Entry point for the learning research workflow.",
        ),
        _agent_node(
            "node-lr-reviewer", "Internal Knowledge Reviewer", "learning_internal_reviewer", 310, 260,
            model="gpt-5.4",
            fallback_models=["claude-sonnet-4-6"],
            temperature=0.2,
            native_tools=["memory_recall"],
            enable_memory=True,
            enable_rag=True,
            system_prompt="""ROLE: Project Knowledge Archivist and Gap Analyst.

DOMAIN EXPERTISE: AI Operations, Agentic Workflows, LangChain/LangGraph, Vector Embeddings, LLM Infrastructure.

GOAL: Recall existing relevant knowledge for the user's research query, then identify the specific knowledge gaps requiring external research.

CRITICAL TOOL:
- 'memory_recall': Search the project's long-term memory for past learnings, decisions, patterns, and facts. Call it with several query variants.

Additional retrieved project context (RAG) may be injected into your context automatically - treat it as internal knowledge too.

PROCESS:
1. Analyze the user's research query carefully
2. Call 'memory_recall' with multiple query phrasings to surface prior knowledge
3. Synthesize ALL recalled and injected findings
4. Identify specific knowledge gaps that require external research

OUTPUT FORMAT:
## Internal Knowledge Summary
[Summarize recalled learnings, decisions, patterns, facts, and injected context]

## Knowledge Gaps Identified
[Numbered list of specific areas requiring external research]""",
        ),
        _agent_node(
            "node-lr-planner", "Learning Research Planner", "learning_research_planner", 570, 260,
            model="claude-sonnet-4-6",
            fallback_models=["gpt-5.4"],
            temperature=0.3,
            system_prompt="""ROLE: AI Operations Research Strategist.

GOAL: Create a focused external research plan targeting ONLY the identified knowledge gaps.

INPUTS (provided in context):
- Original user query
- Internal knowledge summary
- Knowledge gaps

PROCESS:
1. Review the knowledge gaps carefully
2. For each gap, formulate a specific, technical research question
3. Ensure questions target implementation details, best practices, or recent developments
4. Prioritize questions that will have the most impact

OUTPUT FORMAT: Return ONLY a valid JSON array of research question strings.

CRITICAL: Output must be valid JSON that can be parsed. No preamble, no markdown, just the JSON array.""",
        ),
        _agent_node(
            "node-lr-researcher", "Specialized Researcher", "learning_external_researcher", 830, 260,
            model="gpt-5.4-mini",
            fallback_models=["gpt-5.4", "gemini-2.5-flash"],
            temperature=0.3,
            native_tools=["web_search"],
            enable_model_routing=True,
            enable_parallel_tools=True,
            system_prompt="""ROLE: Technical Research Specialist.

DOMAIN FOCUS: AI/ML Infrastructure, Agentic Systems, LangChain Ecosystem, Vector Databases.

GOAL: Conduct focused external research on each planned question using specialized sources.

RESEARCH STRATEGY:
1. Academic sources: search for ArXiv papers
2. Code examples: find GitHub implementations
3. Official documentation: prioritize official docs
4. Technical blogs: target reputable sources

CRITICAL REQUIREMENTS:
- Use the 'web_search' tool actively for each research angle
- Include specific citations in format: [Source Title](URL)
- Extract code snippets when relevant
- Prefer recent information

OUTPUT FORMAT (per question):
## Research Findings: [Question]
### Key Findings
[Detailed summary]
### Implementation Examples
[Code snippets if applicable]
### Sources
- [Title 1](URL1)
- [Title 2](URL2)""",
        ),
        _agent_node(
            "node-lr-synthesizer", "Knowledge Synthesizer", "learning_synthesizer", 1090, 260,
            model="claude-sonnet-4-6",
            fallback_models=["gpt-5.4"],
            temperature=0.5,
            timeout_seconds=300,
            system_prompt="""ROLE: Senior AI Operations Consultant and Technical Advisor.

GOAL: Synthesize internal project knowledge and external research into actionable, expert guidance.

SYNTHESIS PROCESS:
1. Prioritize internal context: start with what's already known
2. Integrate external insights: layer in new findings
3. Identify contradictions: note any conflicts between sources
4. Provide actionable recommendations: specific steps, configurations, code patterns

OUTPUT FORMAT:

# [Query Topic] - Technical Advisory Report

## Executive Summary
[2-3 sentence overview]

## Internal Context & Baseline
[What we already knew from project memory]

## New Insights from Research
[Key findings from external sources with citations]

## Actionable Recommendations
1. **[Category]**: [Specific recommendation]
   - Implementation: [Code snippet or configuration]
   - Rationale: [Why this approach]

## Sources & Citations
[Complete list of references]""",
        ),
        _agent_node(
            "node-lr-curator", "Knowledge Curator", "learning_knowledge_curator", 1350, 260,
            model="gpt-5.4",
            fallback_models=["claude-sonnet-4-6"],
            temperature=0.2,
            native_tools=["memory_store"],
            enable_memory=True,
            system_prompt="""ROLE: Knowledge Management Specialist (The Learning Loop).

GOAL: Extract key insights from the advisory report and store them in the project's long-term memory for future runs.

CRITICAL TOOL: You MUST actively call the 'memory_store' tool to save insights.

EXTRACTION PROCESS:
1. Read the report carefully, identifying distinct insights
2. For EACH significant insight, call 'memory_store' with:
   - memory_content: a clear, self-contained statement
   - memory_type: FACT, DECISION, PATTERN, or LEARNING
   - importance: score 1-10
   - tags: relevant categorization

QUALITY CRITERIA:
- Each memory is atomic (one clear concept) and self-contained
- Skip redundant information; prioritize actionable knowledge
- Target 5-15 high-quality memories per report

OUTPUT FORMAT:
# Knowledge Assimilation Log
## Memories Stored: [count]
### FACTS / DECISIONS / PATTERNS / LEARNINGS
- Stored: [brief description per memory]
## Summary
[One paragraph on what was learned]""",
        ),
        _control_node(
            "node-lr-output", "Advisory Report", "OUTPUT_NODE", 1610, 260,
            description="OUTPUT node: formats the advisory report and knowledge assimilation log.",
        ),
        _control_node(
            "node-lr-end", "End", "END_NODE", 1610, 430,
            description="END node: terminus of the learning research workflow.",
        ),
    ],
    edges=[
        _edge("e-lr-1", "node-lr-start", "node-lr-reviewer"),
        _edge("e-lr-2", "node-lr-reviewer", "node-lr-planner"),
        _edge("e-lr-3", "node-lr-planner", "node-lr-researcher"),
        _edge("e-lr-4", "node-lr-researcher", "node-lr-synthesizer"),
        _edge("e-lr-5", "node-lr-synthesizer", "node-lr-curator"),
        _edge("e-lr-6", "node-lr-curator", "node-lr-output"),
        _edge("e-lr-7", "node-lr-output", "node-lr-end"),
    ],
)


# =============================================================================
# RESEARCH & CONTENT EDITOR WORKFLOW RECIPE
# =============================================================================
# Pattern: Researcher -> Editor (minimal two-agent starter)

RESEARCH_CONTENT_EDITOR_RECIPE = WorkflowRecipe(
    recipe_id="research_content_editor",
    name="Research & Content Editor",
    description="Minimal two-agent starter: a researcher produces a detailed, cited report and an editor verifies citations, enhances structure, and polishes the final output.",
    category="research",
    icon="edit_note",
    tags=["research", "editing", "content", "reports"],
    nodes=[
        _control_node(
            "node-rce-start", "Start", "START_NODE", 50, 260,
            description="START node: Entry point for the research & content editor workflow.",
        ),
        _agent_node(
            "node-rce-researcher", "Deep Researcher", "content_researcher", 310, 260,
            model="claude-sonnet-4-6",
            fallback_models=["gpt-5.4"],
            temperature=0.6,
            native_tools=["web_search"],
            enable_memory=True,
            extra={"max_tokens": 4000},
            system_prompt="""ROLE: Deep Research Specialist.

EXPERTISE: In-depth research, comprehensive report writing, academic formatting, source synthesis.

GOAL: Perform thorough research on the given topic using the 'web_search' tool and produce a comprehensive, well-structured report formatted as if it were an academic submission.

PROCESS:
1. Analyze the research topic and identify key areas to investigate
2. Use 'web_search' to gather information from reliable sources
3. Synthesize findings into a coherent narrative
4. Structure the report with clear sections and logical flow
5. Support all claims with evidence and proper citations: [Source Title](URL)

OUTPUT REQUIREMENTS:
- Thorough, well-structured report with professional academic formatting
- Detailed analysis reflecting deep understanding of the topic
- All sources credible and properly cited

After completing your report, hand it over to the Editor who will proofread and edit it for accuracy and quality.""",
        ),
        _agent_node(
            "node-rce-editor", "Editor", "content_editor", 570, 260,
            model="claude-sonnet-4-6",
            fallback_models=["gpt-5.4"],
            temperature=0.7,
            native_tools=["web_search", "memory_store", "memory_recall"],
            enable_parallel_tools=True,
            enable_memory=True,
            extra={"max_tokens": 4000},
            system_prompt="""ROLE: Professional Editor and Quality Assurance Specialist.

EXPERTISE: Proofreading, document structure enhancement, citation verification, academic standards.

GOAL: Review the research report received from the researcher. Meticulously proofread, enhance the structure, verify citations, and produce a publication-ready final document.

PROCESS:
1. Grammar & style review: correct errors, improve flow, ensure consistent tone
2. Structure enhancement: logical organization, clear headings, smooth transitions
3. Citation verification: cross-check citations for reliability (use 'web_search' when needed)
4. Content review: clarify ambiguous passages, flag unsupported claims
5. Final polish: professional, publication-ready quality

OUTPUT: The complete, fully edited final report with all improvements incorporated - not a list of suggested changes.""",
        ),
        _control_node(
            "node-rce-output", "Edited Report", "OUTPUT_NODE", 830, 260,
            description="OUTPUT node: formats the final edited report.",
        ),
        _control_node(
            "node-rce-end", "End", "END_NODE", 1090, 260,
            description="END node: terminus of the research & content editor workflow.",
        ),
    ],
    edges=[
        _edge("e-rce-1", "node-rce-start", "node-rce-researcher"),
        _edge("e-rce-2", "node-rce-researcher", "node-rce-editor"),
        _edge("e-rce-3", "node-rce-editor", "node-rce-output"),
        _edge("e-rce-4", "node-rce-output", "node-rce-end"),
    ],
)


# =============================================================================
# CODE REVIEW PANEL RECIPE
# =============================================================================
# Pattern: Planner -> three parallel specialist reviewers (multi-provider)
# -> deferred synthesizer (waits for all branches) -> Output

CODE_REVIEW_PANEL_RECIPE = WorkflowRecipe(
    recipe_id="code_review_panel",
    name="Code Review Panel",
    description="Three specialist reviewers (correctness, security, performance) review your code in parallel across providers, then a deferred synthesizer merges their findings into one prioritized review.",
    category="code-review",
    icon="rate_review",
    tags=["code-review", "parallelization", "deferred", "multi-provider"],
    nodes=[
        _control_node(
            "node-crp-start", "Start", "START_NODE", 50, 260,
            description="START node: Paste the diff or code to review as the workflow input.",
        ),
        _agent_node(
            "node-crp-planner", "Dispatch Planner", "review_dispatch_planner", 310, 260,
            model="claude-sonnet-4-6",
            fallback_models=["gpt-5.4"],
            temperature=0.2,
            system_prompt="""ROLE: Staff Engineer triaging an incoming code review.

TASK: Read the diff or code provided in the user input and frame the review for three specialist reviewers (correctness, security, performance).

PROCESS:
1. Identify the language(s), frameworks, and apparent purpose of the change
2. Summarize what the code does in 3-5 sentences
3. List the files/functions/regions most worth scrutiny and why
4. Pose 2-4 targeted questions PER specialty (correctness, security, performance) that the reviewers should answer

OUTPUT FORMAT:
## Change Summary
[What this code does and its context]
## Risk Hotspots
- [file/function]: [why it deserves attention]
## Review Goals
### Correctness
- [question]
### Security
- [question]
### Performance
- [question]

Do NOT review the code yourself - frame the review only. Include the essential code context the reviewers need.""",
        ),
        _agent_node(
            "node-crp-correctness", "Correctness Reviewer", "correctness_reviewer", 570, 90,
            model="gpt-5.4-mini",
            fallback_models=["gpt-5.4", "claude-haiku-4-5"],
            temperature=0.2,
            timeout_seconds=240,
            system_prompt="""ROLE: Correctness-focused Code Reviewer.

TASK: Review the code from the conversation for logic bugs, answering the planner's correctness goals first.

CHECK FOR: off-by-one errors, null/None handling, error handling and propagation, edge cases (empty inputs, boundaries, concurrency), incorrect conditionals, broken contracts/return types, unhandled failure modes.

RULES:
- Cite the exact line or snippet for every finding
- Rate each finding severity: BLOCKER / MAJOR / MINOR
- Do not comment on style, security, or performance - other reviewers own those
- If you find nothing, say so explicitly

OUTPUT FORMAT:
## Correctness Review
### Findings
1. [SEVERITY] [location]: [problem] -> [suggested fix]
### Answers to Review Goals
- [question]: [answer]
### Verdict
[One sentence: overall correctness assessment]""",
        ),
        _agent_node(
            "node-crp-security", "Security Reviewer", "security_reviewer", 570, 260,
            model="claude-haiku-4-5",
            fallback_models=["claude-sonnet-4-6", "gpt-5.4-mini"],
            temperature=0.2,
            timeout_seconds=240,
            system_prompt="""ROLE: Application Security Reviewer (OWASP-aligned).

TASK: Review the code from the conversation for security vulnerabilities, answering the planner's security goals first.

CHECK FOR: injection (SQL/command/template), XSS, path traversal, SSRF, insecure deserialization, authn/authz gaps, secrets or credentials in code, weak crypto, unvalidated input at trust boundaries, dependency risks.

RULES:
- Cite the exact line or snippet for every finding
- Rate each finding severity: CRITICAL / HIGH / MEDIUM / LOW
- Include a concrete exploit scenario for CRITICAL/HIGH findings
- Do not comment on correctness or performance - other reviewers own those
- If you find nothing, say so explicitly

OUTPUT FORMAT:
## Security Review
### Findings
1. [SEVERITY] [location]: [vulnerability] -> [exploit scenario] -> [remediation]
### Answers to Review Goals
- [question]: [answer]
### Verdict
[One sentence: overall security posture]""",
        ),
        _agent_node(
            "node-crp-performance", "Performance Reviewer", "performance_reviewer", 570, 430,
            model="gemini-2.5-flash",
            fallback_models=["gpt-5.4-mini", "claude-haiku-4-5"],
            temperature=0.2,
            timeout_seconds=240,
            system_prompt="""ROLE: Performance-focused Code Reviewer.

TASK: Review the code from the conversation for performance issues, answering the planner's performance goals first.

CHECK FOR: algorithmic complexity (accidental O(n^2)+), N+1 queries, unnecessary allocations or copies, blocking calls on hot/async paths, missing caching or memoization opportunities, unbounded growth (memory leaks, unbounded queues), chatty I/O.

RULES:
- Cite the exact line or snippet for every finding
- Estimate impact: HIGH (user-visible latency/cost) / MEDIUM / LOW
- Only flag optimizations that matter - no micro-optimization noise
- Do not comment on correctness or security - other reviewers own those
- If you find nothing, say so explicitly

OUTPUT FORMAT:
## Performance Review
### Findings
1. [IMPACT] [location]: [issue] -> [suggested fix]
### Answers to Review Goals
- [question]: [answer]
### Verdict
[One sentence: overall performance assessment]""",
        ),
        _agent_node(
            "node-crp-synthesizer", "Review Synthesizer", "review_synthesizer", 830, 260,
            model="claude-sonnet-4-6",
            fallback_models=["gpt-5.4"],
            temperature=0.3,
            deferred=True,  # Fan-in: wait for all three reviewers before running
            system_prompt="""ROLE: Lead Reviewer consolidating a three-person review panel.

INPUT: The conversation contains the planner's framing plus three specialist reviews (correctness, security, performance).

TASK: Merge all findings into ONE actionable review.

PROCESS:
1. Deduplicate overlapping findings, keeping the clearest articulation
2. Re-rank everything on a single severity scale: BLOCKER / MAJOR / MINOR / NIT
3. Resolve conflicts between reviewers (note the disagreement and your ruling)
4. Decide an overall recommendation

OUTPUT FORMAT:
# Consolidated Code Review
## Recommendation: APPROVE / APPROVE WITH CHANGES / REQUEST CHANGES
[One paragraph justification]
## Findings (ordered by severity)
1. [SEVERITY] [location]: [finding] -> [required action] (source: correctness/security/performance)
## Quick Wins
- [low-effort improvements worth doing now]
## Panel Disagreements
- [conflict and your ruling, or "None"]""",
        ),
        _control_node(
            "node-crp-output", "Consolidated Review", "OUTPUT_NODE", 1090, 260,
            description="OUTPUT node: formats the consolidated review for delivery.",
        ),
        _control_node(
            "node-crp-end", "End", "END_NODE", 1350, 260,
            description="END node: terminus of the code review panel workflow.",
        ),
    ],
    edges=[
        _edge("e-crp-1", "node-crp-start", "node-crp-planner"),
        # Parallel fan-out: three plain edges from the planner
        _edge("e-crp-2", "node-crp-planner", "node-crp-correctness"),
        _edge("e-crp-3", "node-crp-planner", "node-crp-security"),
        _edge("e-crp-4", "node-crp-planner", "node-crp-performance"),
        # Fan-in to the deferred synthesizer
        _edge("e-crp-5", "node-crp-correctness", "node-crp-synthesizer"),
        _edge("e-crp-6", "node-crp-security", "node-crp-synthesizer"),
        _edge("e-crp-7", "node-crp-performance", "node-crp-synthesizer"),
        _edge("e-crp-8", "node-crp-synthesizer", "node-crp-output"),
        _edge("e-crp-9", "node-crp-output", "node-crp-end"),
    ],
)


# =============================================================================
# PLAN-BUILD-VERIFY CODER RECIPE
# =============================================================================
# Pattern: Spec -> Implement (file tools) -> Verification critic ->
# PASS/REVISE gate -> human approval on PASS; LOOP_NODE (max 3) back to the
# implementer on REVISE, force-exiting to output with whatever exists.

PLAN_BUILD_VERIFY_RECIPE = WorkflowRecipe(
    recipe_id="plan_build_verify_coder",
    name="Plan-Build-Verify Coder",
    description="Evaluator-optimizer coding loop: spec it, build it with file tools, verify it with a critic, loop on failures (max 3), and gate the final result behind human approval.",
    category="coding",
    icon="construction",
    tags=["coding", "reflection", "hitl", "tools"],
    nodes=[
        _control_node(
            "node-pbv-start", "Start", "START_NODE", 50, 260,
            description="START node: Describe the coding task as the workflow input.",
        ),
        _agent_node(
            "node-pbv-planner", "Spec Planner", "coding_spec_planner", 310, 260,
            model="claude-sonnet-4-6",
            fallback_models=["gpt-5.4"],
            temperature=0.2,
            system_prompt="""ROLE: Senior Software Architect writing an implementation spec.

TASK: Turn the user's coding request into a precise, executable specification for an implementer agent that has file tools (write_file, read_file, edit_file, ls).

PROCESS:
1. Restate the goal and explicit constraints
2. Decide file layout: exact paths for every file to create or modify
3. Define behavior: inputs, outputs, edge cases, error handling
4. Define acceptance criteria the verifier will check - concrete and testable

OUTPUT FORMAT:
# Implementation Spec
## Goal
[One paragraph]
## Files
- [path]: [purpose]
## Behavior
[Functional requirements, including edge cases and error handling]
## Acceptance Criteria
1. [Checkable criterion]
2. [Checkable criterion]

Keep the spec minimal but unambiguous. Do not write the implementation code yourself.""",
        ),
        _agent_node(
            "node-pbv-implementer", "Implementer", "code_implementer", 570, 260,
            model="gpt-5.4",
            fallback_models=["claude-sonnet-4-6"],
            temperature=0.2,
            native_tools=["write_file", "read_file", "edit_file", "ls"],
            enable_parallel_tools=True,
            system_prompt="""ROLE: Disciplined Software Implementer.

TASK: Implement the spec from the conversation using your file tools. On revision passes, fix EVERY issue raised by the Verification Critic.

TOOLS: write_file (create), read_file (inspect), edit_file (modify), ls (list).

RULES:
1. Follow the spec's file layout exactly - create/modify only the listed files
2. Write complete, runnable code - no placeholders, no TODOs
3. Handle the edge cases and errors the spec calls out
4. On revision passes, read the critic's findings carefully and address each one; use read_file to check current file state before editing

OUTPUT FORMAT (after using your tools):
## Implementation Summary
- [path]: [what was written/changed]
## Spec Coverage
- [acceptance criterion]: [how it is satisfied]
## Notes
[Assumptions or deviations, if any]""",
        ),
        _agent_node(
            "node-pbv-critic", "Verification Critic", "verification_critic", 830, 260,
            model="claude-sonnet-4-6",
            fallback_models=["gpt-5.4"],
            temperature=0.1,
            native_tools=["read_file", "grep"],
            system_prompt="""ROLE: Verification Critic (QA gate for the implementation).

TASK: Verify the implementation against the spec's acceptance criteria. Do NOT trust the implementer's summary - inspect the actual files.

TOOLS: read_file (read each file the spec lists), grep (search for patterns, TODOs, placeholders).

PROCESS:
1. read_file every file named in the spec - confirm it exists and is complete
2. Check each acceptance criterion against the real code
3. grep for placeholder markers (TODO, FIXME, pass-only stubs, NotImplementedError)
4. Check edge cases and error handling required by the spec

OUTPUT FORMAT:
## Verification Report
### Criterion Results
- [criterion]: PASS/FAIL - [evidence from the actual files]
### Defects
1. [path:location]: [what is wrong and what must change]

Issue VERDICT: PASS only when every acceptance criterion is met and no defects remain.
""" + _VERDICT_CONTRACT,
        ),
        _control_node(
            "node-pbv-conditional", "Verification Gate", "CONDITIONAL_NODE", 1090, 260,
            description="Routes on the verification critic's verdict: PASS goes to human approval, REVISE loops back to the implementer.",
            extra_config={
                "condition": _PASS_CONDITION,
                # Semantic route labels matched against edge data.label.
                # "default": PASS fails forward to the human gate on eval errors.
                "routing_map": {"true": "PASS", "false": "REVISE", "default": "PASS"},
            },
        ),
        _control_node(
            "node-pbv-loop", "Fix Loop (max 3)", "LOOP_NODE", 1090, 430,
            description="Caps implement/verify cycles at 3, then force-exits to output with whatever exists.",
            extra_config={
                "max_iterations": 3,
                "exit_condition": "",
                "loop_target": "node-pbv-implementer",  # Informational; 'continue' edge wires it
            },
        ),
        _control_node(
            "node-pbv-approval", "Human Approval", "APPROVAL_NODE", 1350, 260,
            description="Human gate: review the verified implementation before the workflow finishes. Requires approval via the HITL panel/API.",
        ),
        _control_node(
            "node-pbv-output", "Delivery Report", "OUTPUT_NODE", 1610, 260,
            description="OUTPUT node: formats the implementation summary and verification report.",
        ),
        _control_node(
            "node-pbv-end", "End", "END_NODE", 1610, 430,
            description="END node: terminus of the plan-build-verify workflow.",
        ),
    ],
    edges=[
        _edge("e-pbv-1", "node-pbv-start", "node-pbv-planner"),
        _edge("e-pbv-2", "node-pbv-planner", "node-pbv-implementer"),
        _edge("e-pbv-3", "node-pbv-implementer", "node-pbv-critic"),
        _edge("e-pbv-4", "node-pbv-critic", "node-pbv-conditional"),
        _edge("e-pbv-5", "node-pbv-conditional", "node-pbv-approval", label="PASS"),
        _edge("e-pbv-6", "node-pbv-conditional", "node-pbv-loop", label="REVISE"),
        _edge("e-pbv-7", "node-pbv-loop", "node-pbv-implementer", label="continue"),
        _edge("e-pbv-8", "node-pbv-loop", "node-pbv-output", label="exit"),
        _edge("e-pbv-9", "node-pbv-approval", "node-pbv-output"),
        _edge("e-pbv-10", "node-pbv-output", "node-pbv-end"),
    ],
)


# =============================================================================
# PRIVACY-FIRST DOCUMENT ANALYST RECIPE
# =============================================================================
# Pattern: deterministic PII tool chain (detect -> redact) -> analysis agents.
# The LLMs only ever see the REDACTED text.
#
# Executor adaptations:
# - The pii_detect tool node overwrites state.current_directive with its
#   report, so the pii_redact node templates {{state.query}} (the original,
#   untouched user input) instead of {{directive}}.
# - Agent prompts do not support {{...}} interpolation (only TOOL_NODE params
#   do), so the analyst/reporter read the tool outputs - which execute_tool_node
#   appends to the message history - from the conversation instead of from
#   {{state.last_tool_output}}.

PRIVACY_DOCUMENT_ANALYST_RECIPE = WorkflowRecipe(
    recipe_id="privacy_document_analyst",
    name="Privacy-First Document Analyst",
    description="Deterministic PII pipeline: scan and redact the document with native tools first, then analyze the sanitized text and produce a compliance-grade report - the LLMs never see raw PII.",
    category="privacy",
    icon="privacy_tip",
    tags=["privacy", "pii", "tool-node", "compliance"],
    nodes=[
        _control_node(
            "node-pda-start", "Start", "START_NODE", 50, 260,
            description="START node: Paste the document text to analyze as the workflow input.",
        ),
        _tool_node(
            "node-pda-detect", "PII Scan", "pii_detect",
            {"text": "{{directive}}"},  # First tool node: directive == original input
            310, 260,
        ),
        _tool_node(
            "node-pda-redact", "PII Redaction", "pii_redact",
            # {{state.query}} = the ORIGINAL user input; {{directive}} would now
            # resolve to the pii_detect report (tool nodes overwrite the directive).
            {"text": "{{state.query}}", "strategy": "redact"},
            570, 260,
        ),
        _agent_node(
            "node-pda-analyst", "Insights Analyst", "document_insights_analyst", 830, 260,
            model="claude-sonnet-4-6",
            fallback_models=["gpt-5.4"],
            temperature=0.3,
            system_prompt="""ROLE: Senior Document Analyst working on privacy-sanitized text.

INPUT: The conversation contains the output of the `pii_redact` tool - the document with PII replaced by [REDACTED_*] placeholders, followed by a detection summary. Analyze ONLY that redacted text.

TASK: Extract the substantive insights from the redacted document.

PROCESS:
1. Identify document type, purpose, and audience
2. Summarize the key points, decisions, obligations, and dates
3. Surface risks, anomalies, or open questions
4. Treat [REDACTED_*] placeholders as opaque entities - never guess what is behind them

OUTPUT FORMAT:
## Document Profile
[Type, purpose, audience]
## Key Findings
1. [Finding with supporting quote from the redacted text]
## Risks & Open Questions
- [Item]
## Entity Map
- [REDACTED_TYPE placeholders encountered and the role each plays in the document]""",
        ),
        _agent_node(
            "node-pda-reporter", "Compliance Reporter", "compliance_reporter", 1090, 260,
            model="gpt-5.4-mini",
            fallback_models=["gpt-5.4", "claude-haiku-4-5"],
            temperature=0.2,
            timeout_seconds=240,
            system_prompt="""ROLE: Privacy Compliance Reporter.

INPUT: The conversation contains (1) the `pii_detect` tool report listing every PII item found, (2) the `pii_redact` tool output with its redaction summary, and (3) the analyst's insights on the sanitized document.

TASK: Produce a single structured compliance report that combines the privacy processing record with the document insights.

OUTPUT FORMAT (exactly these sections):
# Privacy-First Analysis Report
## 1. Processing Summary
[What was scanned, what was redacted - counts per PII type, drawn from the tool reports]
## 2. PII Inventory
| PII Type | Count | Handling |
|---|---|---|
[One row per detected type; Handling is always "Redacted"]
## 3. Document Insights
[Condensed version of the analyst's findings]
## 4. Residual Risk Notes
[Anything that may still warrant manual review, e.g. quasi-identifiers or context that survives redaction]
## 5. Attestation
[One sentence stating the analysis was performed exclusively on redacted text]

Be precise: copy counts and types verbatim from the tool reports; do not invent numbers.""",
        ),
        _control_node(
            "node-pda-output", "Compliance Report", "OUTPUT_NODE", 1350, 260,
            description="OUTPUT node: formats the privacy-first analysis report.",
        ),
        _control_node(
            "node-pda-end", "End", "END_NODE", 1610, 260,
            description="END node: terminus of the privacy-first document analyst workflow.",
        ),
    ],
    edges=[
        _edge("e-pda-1", "node-pda-start", "node-pda-detect"),
        _edge("e-pda-2", "node-pda-detect", "node-pda-redact"),
        _edge("e-pda-3", "node-pda-redact", "node-pda-analyst"),
        _edge("e-pda-4", "node-pda-analyst", "node-pda-reporter"),
        _edge("e-pda-5", "node-pda-reporter", "node-pda-output"),
        _edge("e-pda-6", "node-pda-output", "node-pda-end"),
    ],
)


# =============================================================================
# COMPETITIVE INTEL SWEEP RECIPE
# =============================================================================
# Pattern: Planner -> three parallel researchers -> deferred fact-checker
# -> CHECKPOINT (verified evidence persisted) -> strategy writer -> Output

COMPETITIVE_INTEL_SWEEP_RECIPE = WorkflowRecipe(
    recipe_id="competitive_intel_sweep",
    name="Competitive Intel Sweep",
    description="Parallel market research fan-out with adversarial fact-checking and a mid-pipeline checkpoint, synthesized into a strategy brief you can act on.",
    category="research",
    icon="query_stats",
    tags=["research", "parallelization", "fact-checking", "web"],
    nodes=[
        _control_node(
            "node-cis-start", "Start", "START_NODE", 50, 260,
            description="START node: Name the target company/market/question as the workflow input.",
        ),
        _agent_node(
            "node-cis-planner", "Intel Planner", "intel_planner", 310, 260,
            model="claude-sonnet-4-6",
            fallback_models=["gpt-5.4"],
            temperature=0.3,
            system_prompt="""ROLE: Competitive Intelligence Lead decomposing a research target.

TASK: Turn the user's target (company, market, or question) into three focused research briefs - one each for a company researcher, a market researcher, and a trends researcher.

OUTPUT FORMAT:
## Target Definition
[Precise restatement of what we are investigating and why]
## Brief A - Company Research
- Key questions: [3-5 questions on competitors' products, pricing, positioning, recent moves]
## Brief B - Market Research
- Key questions: [3-5 questions on market size, segments, customers, channels, regulation]
## Brief C - Trends Research
- Key questions: [3-5 questions on technology shifts, emerging entrants, funding, sentiment]

Questions must be specific, answerable via web search, and non-overlapping across briefs.""",
        ),
        _agent_node(
            "node-cis-company", "Company Researcher", "company_researcher", 570, 90,
            model="gpt-5.4-mini",
            fallback_models=["gemini-2.5-flash", "claude-haiku-4-5"],
            temperature=0.3,
            native_tools=["web_search"],
            enable_parallel_tools=True,
            timeout_seconds=240,
            system_prompt="""ROLE: Company Intelligence Researcher.

TASK: Answer Brief A (Company Research) from the planner using the 'web_search' tool. Investigate the named competitors: products, pricing, positioning, leadership, partnerships, and recent announcements.

RULES:
- Run multiple targeted searches; prefer primary sources (company sites, filings, press releases)
- Cite every claim: [Source Title](URL)
- Mark each claim's confidence: CONFIRMED (2+ sources) / SINGLE-SOURCE / RUMOR
- Note publication dates - recency matters

OUTPUT FORMAT:
## Company Research Findings
### [Question from Brief A]
[Findings with citations and confidence marks]
### Notable Recent Moves
- [Dated item with citation]""",
        ),
        _agent_node(
            "node-cis-market", "Market Researcher", "market_researcher", 570, 260,
            model="gpt-5.4-mini",
            fallback_models=["gemini-2.5-flash", "claude-haiku-4-5"],
            temperature=0.3,
            native_tools=["web_search"],
            enable_parallel_tools=True,
            timeout_seconds=240,
            system_prompt="""ROLE: Market Intelligence Researcher.

TASK: Answer Brief B (Market Research) from the planner using the 'web_search' tool. Investigate market size, growth, segmentation, customer needs, buying channels, and regulatory factors.

RULES:
- Run multiple targeted searches; prefer analyst reports, industry bodies, and government data
- Cite every claim: [Source Title](URL)
- Quote numbers exactly with their year and source; never average conflicting figures - report the range
- Mark each claim's confidence: CONFIRMED (2+ sources) / SINGLE-SOURCE / ESTIMATE

OUTPUT FORMAT:
## Market Research Findings
### [Question from Brief B]
[Findings with citations and confidence marks]
### Key Figures
| Metric | Value | Year | Source |
|---|---|---|---|""",
        ),
        _agent_node(
            "node-cis-trends", "Trends Researcher", "trends_researcher", 570, 430,
            model="gpt-5.4-mini",
            fallback_models=["gemini-2.5-flash", "claude-haiku-4-5"],
            temperature=0.3,
            native_tools=["web_search"],
            enable_parallel_tools=True,
            timeout_seconds=240,
            system_prompt="""ROLE: Trends & Signals Researcher.

TASK: Answer Brief C (Trends Research) from the planner using the 'web_search' tool. Investigate technology shifts, emerging entrants, funding activity, hiring signals, and sentiment.

RULES:
- Run multiple targeted searches; include news, funding databases coverage, and technical communities
- Cite every claim: [Source Title](URL)
- Date every signal; separate established trends from weak signals
- Mark each claim's confidence: CONFIRMED (2+ sources) / SINGLE-SOURCE / SPECULATIVE

OUTPUT FORMAT:
## Trends Research Findings
### [Question from Brief C]
[Findings with citations and confidence marks]
### Signal Radar
- ESTABLISHED: [trend, citation]
- EMERGING: [signal, citation]""",
        ),
        _agent_node(
            "node-cis-factcheck", "Fact Checker", "intel_fact_checker", 830, 260,
            model="claude-haiku-4-5",
            fallback_models=["gpt-5.4-mini"],
            temperature=0.1,
            native_tools=["web_fetch", "web_search"],
            deferred=True,  # Fan-in: wait for all three researchers
            timeout_seconds=300,
            system_prompt="""ROLE: Adversarial Fact Checker.

INPUT: The conversation contains three research reports (company, market, trends) with cited claims.

TASK: Verify the highest-impact claims before they reach the strategy writer.

PROCESS:
1. Select the 5-10 claims that would most change the strategy if wrong (big numbers, competitor moves, regulatory assertions)
2. Use 'web_fetch' to open the cited URLs and confirm the source actually supports the claim; use 'web_search' to find corroboration where a fetch fails
3. Flag claims that are unsupported, outdated, or misquoted
4. Leave unverified low-impact claims marked as such - do not delete them

OUTPUT FORMAT:
## Fact-Check Report
### Verified Claims
- [claim] - VERIFIED via [Source](URL)
### Corrected Claims
- [original claim] -> [correction] via [Source](URL)
### Unsupported Claims (treat with caution)
- [claim] - [why it failed verification]
### Confidence Statement
[One paragraph on the overall reliability of the evidence base]""",
        ),
        _control_node(
            "node-cis-checkpoint", "Evidence Checkpoint", "CHECKPOINT_NODE", 1090, 260,
            description="CHECKPOINT node: persists the verified evidence base before synthesis, so the expensive research phase survives restarts.",
        ),
        _agent_node(
            "node-cis-writer", "Strategy Writer", "intel_strategy_writer", 1350, 260,
            model="claude-sonnet-4-6",
            fallback_models=["gpt-5.4"],
            temperature=0.4,
            enable_memory=True,
            system_prompt="""ROLE: Strategy Consultant writing the final intelligence brief.

INPUT: The conversation contains three research reports and a fact-check report. Weight every claim by its verification status - corrected claims use the corrected value; unsupported claims may only appear flagged as unverified.

OUTPUT FORMAT:
# Competitive Intelligence Brief: [Target]
## Executive Summary
[5 bullet points a decision-maker can act on]
## Competitive Landscape
[Who matters, their position, their momentum]
## Market Reality
[Size, growth, segments - verified figures only, with citations]
## Trends & Disruption Risks
[What is changing and how fast]
## Strategic Implications
1. [Implication] -> Recommended response: [action]
## Evidence Quality
[Summary of what is verified vs. unverified, from the fact-check report]
## Sources
[Deduplicated citation list]""",
        ),
        _control_node(
            "node-cis-output", "Intelligence Brief", "OUTPUT_NODE", 1610, 260,
            description="OUTPUT node: formats the competitive intelligence brief.",
        ),
        _control_node(
            "node-cis-end", "End", "END_NODE", 1610, 430,
            description="END node: terminus of the competitive intel sweep workflow.",
        ),
    ],
    edges=[
        _edge("e-cis-1", "node-cis-start", "node-cis-planner"),
        # Parallel fan-out
        _edge("e-cis-2", "node-cis-planner", "node-cis-company"),
        _edge("e-cis-3", "node-cis-planner", "node-cis-market"),
        _edge("e-cis-4", "node-cis-planner", "node-cis-trends"),
        # Fan-in to deferred fact checker
        _edge("e-cis-5", "node-cis-company", "node-cis-factcheck"),
        _edge("e-cis-6", "node-cis-market", "node-cis-factcheck"),
        _edge("e-cis-7", "node-cis-trends", "node-cis-factcheck"),
        _edge("e-cis-8", "node-cis-factcheck", "node-cis-checkpoint"),
        _edge("e-cis-9", "node-cis-checkpoint", "node-cis-writer"),
        _edge("e-cis-10", "node-cis-writer", "node-cis-output"),
        _edge("e-cis-11", "node-cis-output", "node-cis-end"),
    ],
)


# =============================================================================
# CONTENT STUDIO PIPELINE RECIPE
# =============================================================================
# Pattern: brief -> research -> draft -> style critic with PASS/REVISE gate
# (LOOP_NODE cap 2 on the REVISE path) -> art direction -> deterministic
# image generation TOOL_NODE -> human approval -> output. The graph snakes
# onto a second row after the quality gate.

CONTENT_STUDIO_PIPELINE_RECIPE = WorkflowRecipe(
    recipe_id="content_studio_pipeline",
    name="Content Studio Pipeline",
    description="Creative production line: brief, research, draft, style-critique loop, then art direction and AI image generation - with a human approval gate before anything ships.",
    category="content",
    icon="palette",
    tags=["content", "creative", "image-generation", "hitl", "reflection"],
    nodes=[
        _control_node(
            "node-csp-start", "Start", "START_NODE", 50, 90,
            description="START node: Describe the content piece you need as the workflow input.",
        ),
        _agent_node(
            "node-csp-brief", "Brief Analyst", "content_brief_analyst", 310, 90,
            model="gpt-5.4-mini",
            fallback_models=["claude-haiku-4-5"],
            temperature=0.3,
            timeout_seconds=240,
            system_prompt="""ROLE: Content Strategist turning a request into a creative brief.

TASK: Analyze the user's content request and produce a tight creative brief for the rest of the pipeline.

OUTPUT FORMAT:
# Creative Brief
## Objective
[What this content must achieve]
## Audience
[Who it is for and what they care about]
## Format & Channel
[Content type, target length, where it will be published]
## Key Messages
1. [Message]
## Tone & Voice
[3-5 adjectives with one example sentence in that voice]
## Research Questions
- [2-4 specific questions the researcher should answer to ground the piece]

Make decisive choices where the request is ambiguous and state your assumptions.""",
        ),
        _agent_node(
            "node-csp-researcher", "Content Researcher", "content_pipeline_researcher", 570, 90,
            model="gpt-5.4-mini",
            fallback_models=["gemini-2.5-flash", "claude-haiku-4-5"],
            temperature=0.3,
            native_tools=["web_search"],
            enable_parallel_tools=True,
            timeout_seconds=240,
            system_prompt="""ROLE: Content Researcher grounding a creative piece in facts.

TASK: Answer the brief's research questions using the 'web_search' tool and gather supporting material the writer can use.

RULES:
- Answer every research question from the brief with citations: [Source Title](URL)
- Collect 3-5 concrete facts, statistics, or examples that make the piece credible
- Note anything recent that changes the angle
- Flag claims you could not verify

OUTPUT FORMAT:
## Research Pack
### Answers
- [question]: [answer with citation]
### Usable Facts & Examples
1. [Fact/stat/example with citation]
### Angle Notes
[Anything that should shape the draft]""",
        ),
        _agent_node(
            "node-csp-writer", "Draft Writer", "content_draft_writer", 830, 90,
            model="claude-sonnet-4-6",
            fallback_models=["gpt-5.4"],
            temperature=0.7,
            timeout_seconds=300,
            system_prompt="""ROLE: Senior Content Writer.

TASK: Write the content piece defined by the creative brief, grounded in the research pack. On revision passes, rewrite to fix EVERY issue the Style Critic raised.

RULES:
1. Follow the brief exactly: format, length, key messages, tone & voice
2. Weave in the research facts naturally - no fact dumps
3. Open strong: the first two sentences must earn the reader's attention
4. End with a clear call-to-action or takeaway aligned with the objective
5. On revision passes, address each critique point and keep what already worked

OUTPUT: The complete piece only - publication-ready, no meta-commentary.""",
        ),
        _agent_node(
            "node-csp-critic", "Style Critic", "style_critic", 1090, 90,
            model="claude-haiku-4-5",
            fallback_models=["gpt-5.4-mini"],
            temperature=0.2,
            timeout_seconds=240,
            system_prompt="""ROLE: Style Critic (editorial quality gate).

TASK: Judge the draft against the creative brief.

EVALUATION CRITERIA:
1. Brief fidelity - objective, audience, format, length, key messages all honored
2. Voice - matches the brief's tone adjectives consistently
3. Craft - strong opening, clear structure, no filler, no cliches, varied rhythm
4. Credibility - research facts used accurately and attributed where needed

OUTPUT FORMAT:
## Style Review
- Brief fidelity: [assessment]
- Voice: [assessment]
- Craft: [assessment with quoted examples]
- Credibility: [assessment]
### Required Changes (if any)
1. [Specific, actionable change]

Issue VERDICT: PASS only when the piece could ship as-is.
""" + _VERDICT_CONTRACT,
        ),
        _control_node(
            "node-csp-conditional", "Style Gate", "CONDITIONAL_NODE", 1350, 90,
            description="Routes on the style critic's verdict: PASS proceeds to art direction, REVISE loops the draft back to the writer.",
            extra_config={
                "condition": _PASS_CONDITION,
                # Semantic route labels matched against edge data.label;
                # "default": PASS fails forward on eval errors.
                "routing_map": {"true": "PASS", "false": "REVISE", "default": "PASS"},
            },
        ),
        _control_node(
            "node-csp-loop", "Rewrite Loop (max 2)", "LOOP_NODE", 1090, 260,
            description="Caps write/critique cycles at 2, then force-exits forward to art direction with the latest draft.",
            extra_config={
                "max_iterations": 2,
                "exit_condition": "",
                "loop_target": "node-csp-writer",  # Informational; 'continue' edge wires it
            },
        ),
        _agent_node(
            "node-csp-art", "Art Director", "content_art_director", 310, 430,
            model="gpt-5.4-mini",
            fallback_models=["claude-haiku-4-5"],
            temperature=0.6,
            timeout_seconds=240,
            system_prompt="""ROLE: Art Director writing a single hero-image prompt.

TASK: Read the final approved piece in the conversation and write ONE image-generation prompt for its hero visual.

PROMPT REQUIREMENTS:
- Subject: concrete scene or concept that captures the piece's core idea
- Style: medium, lighting, color palette, composition, mood
- Constraints: no text or lettering in the image, no brand logos, no real people's likenesses
- Length: 40-90 words, one paragraph

CRITICAL OUTPUT CONTRACT: Respond with ONLY the image prompt text. No headings, no quotes, no commentary - your entire response is fed verbatim to the image generation tool.""",
        ),
        _tool_node(
            "node-csp-image", "Hero Image Generation", "generate_image",
            # {{previous_output}} resolves to the last message content - the
            # art director's prompt (no earlier tool node sets last_tool_output).
            {"prompt": "{{previous_output}}", "size": "1536x1024", "quality": "high"},
            570, 430,
        ),
        _control_node(
            "node-csp-approval", "Human Approval", "APPROVAL_NODE", 830, 430,
            description="Human gate: review the final piece and generated hero image before publishing. Requires approval via the HITL panel/API.",
        ),
        _control_node(
            "node-csp-output", "Content Package", "OUTPUT_NODE", 1090, 430,
            description="OUTPUT node: formats the final piece, image artifact, and production transcript.",
        ),
        _control_node(
            "node-csp-end", "End", "END_NODE", 1350, 430,
            description="END node: terminus of the content studio pipeline.",
        ),
    ],
    edges=[
        _edge("e-csp-1", "node-csp-start", "node-csp-brief"),
        _edge("e-csp-2", "node-csp-brief", "node-csp-researcher"),
        _edge("e-csp-3", "node-csp-researcher", "node-csp-writer"),
        _edge("e-csp-4", "node-csp-writer", "node-csp-critic"),
        _edge("e-csp-5", "node-csp-critic", "node-csp-conditional"),
        _edge("e-csp-6", "node-csp-conditional", "node-csp-art", label="PASS"),
        _edge("e-csp-7", "node-csp-conditional", "node-csp-loop", label="REVISE"),
        _edge("e-csp-8", "node-csp-loop", "node-csp-writer", label="continue"),
        _edge("e-csp-9", "node-csp-loop", "node-csp-art", label="exit"),
        _edge("e-csp-10", "node-csp-art", "node-csp-image"),
        _edge("e-csp-11", "node-csp-image", "node-csp-approval"),
        _edge("e-csp-12", "node-csp-approval", "node-csp-output"),
        _edge("e-csp-13", "node-csp-output", "node-csp-end"),
    ],
)


# =============================================================================
# RECIPE REGISTRY
# =============================================================================

WORKFLOW_RECIPES = [
    DEEP_RESEARCH_RECIPE,
    LEARNING_RESEARCH_RECIPE,
    RESEARCH_CONTENT_EDITOR_RECIPE,
    CODE_REVIEW_PANEL_RECIPE,
    PLAN_BUILD_VERIFY_RECIPE,
    PRIVACY_DOCUMENT_ANALYST_RECIPE,
    COMPETITIVE_INTEL_SWEEP_RECIPE,
    CONTENT_STUDIO_PIPELINE_RECIPE,
]


def get_all_recipes() -> List[WorkflowRecipe]:
    """Get all available workflow recipes."""
    return WORKFLOW_RECIPES


def get_recipe_by_id(recipe_id: str) -> WorkflowRecipe:
    """Get a specific recipe by ID."""
    for recipe in WORKFLOW_RECIPES:
        if recipe.recipe_id == recipe_id:
            return recipe
    raise KeyError(f"Recipe '{recipe_id}' not found")


def recipe_to_dict(recipe: WorkflowRecipe) -> Dict[str, Any]:
    """Convert a WorkflowRecipe to a dictionary for the canvas-insert API.

    Top-level node ``type`` is rewritten to "custom" because ReactFlow renders
    every LangConfig node with the registered "custom" component; the semantic
    type survives in ``data.agentType`` and is restored to top-level type when
    the frontend saves the workflow.
    """
    canvas_nodes = [{**node, "type": "custom"} for node in recipe.nodes]
    return {
        "recipe_id": recipe.recipe_id,
        "name": recipe.name,
        "description": recipe.description,
        "category": recipe.category,
        "icon": recipe.icon,
        "tags": recipe.tags,
        "nodes": canvas_nodes,
        "edges": recipe.edges,
        "node_count": len(recipe.nodes),
        "edge_count": len(recipe.edges),
    }
