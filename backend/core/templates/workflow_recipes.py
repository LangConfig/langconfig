# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Workflow Recipes - Pre-configured Multi-Node Workflow Templates.

These recipes define complete workflow patterns that can be inserted into the canvas
as a set of connected nodes, rather than individual agent templates.

Each recipe includes:
- nodes: List of node configurations with positions
- edges: List of edge connections between nodes
- metadata: Recipe name, description, category, icon
"""

from typing import Dict, List, Any
from dataclasses import dataclass, field


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
# DEEP RESEARCH WORKFLOW RECIPE
# =============================================================================
# Pattern: Planner -> Parallel Researchers -> Writer <-> Critic (reflection loop)

DEEP_RESEARCH_RECIPE = WorkflowRecipe(
    recipe_id="deep_research_workflow",
    name="Deep Research",
    description="Multi-agent research workflow with planning, parallel data collection, synthesis, and iterative critique refinement.",
    category="research",
    icon="science",
    tags=["research", "multi-agent", "reflection", "parallelization"],
    nodes=[
        {
            "id": "node-dr-start",
            "type": "custom",
            "position": {"x": 50, "y": 200},
            "data": {
                "label": "Start",
                "agentType": "START_NODE",
                "model": "none",
                "config": {
                    "model": "none",
                    "temperature": 0,
                    "system_prompt": "START node: Entry point for deep research workflow.",
                    "native_tools": [],
                    "tools": [],
                    "cli_tools": [],
                    "custom_tools": [],
                    "timeout_seconds": 0,
                    "max_retries": 0,
                    "enable_model_routing": False,
                    "enable_parallel_tools": False,
                    "enable_memory": False,
                }
            }
        },
        {
            "id": "node-dr-planner",
            "type": "custom",
            "position": {"x": 300, "y": 200},
            "data": {
                "label": "Research Planner",
                "agentType": "deep_research_planner",
                "model": "claude-sonnet-4-5-20250929",
                "config": {
                    "model": "claude-sonnet-4-5-20250929",
                    "fallback_models": ["gpt-5"],
                    "temperature": 0.3,
                    "system_prompt": """ROLE: Expert Research Strategist.
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
                    "native_tools": [],
                    "tools": [],
                    "cli_tools": [],
                    "custom_tools": [],
                    "timeout_seconds": 300,
                    "max_retries": 2,
                    "enable_model_routing": False,
                    "enable_parallel_tools": False,
                    "enable_memory": False,
                }
            }
        },
        {
            "id": "node-dr-researcher",
            "type": "custom",
            "position": {"x": 600, "y": 200},
            "data": {
                "label": "Field Researcher",
                "agentType": "field_researcher",
                "model": "gpt-4o-mini",
                "config": {
                    "model": "gpt-4o-mini",
                    "fallback_models": ["gpt-5", "gemini-2.0-flash"],
                    "temperature": 0.3,
                    "system_prompt": """ROLE: Diligent Data Collector and Analyst.
EXPERTISE: Web research, information synthesis, source evaluation, citation formatting.
GOAL: Investigate the assigned research question using the 'web_search' tool and synthesize findings into a factual summary.

PROCESS:
1. Analyze the assigned question carefully
2. Formulate precise search queries to find relevant information
3. Use the 'web_search' tool to gather data from multiple sources
4. Evaluate source credibility and relevance
5. Synthesize findings into a clear, factual summary

CRITICAL REQUIREMENTS:
- Include citations for all claims using format: [Source Title](URL)
- Distinguish between facts and opinions
- Note any conflicting information from different sources
- Focus on recency and relevance

OUTPUT: A detailed summary of findings for the specific sub-question with inline citations.""",
                    "native_tools": ["web_search"],
                    "tools": [],
                    "cli_tools": [],
                    "custom_tools": [],
                    "timeout_seconds": 300,
                    "max_retries": 2,
                    "enable_model_routing": True,
                    "enable_parallel_tools": True,
                    "enable_memory": False,
                }
            }
        },
        {
            "id": "node-dr-writer",
            "type": "custom",
            "position": {"x": 900, "y": 200},
            "data": {
                "label": "Report Writer",
                "agentType": "report_writer",
                "model": "claude-sonnet-4-5-20250929",
                "config": {
                    "model": "claude-sonnet-4-5-20250929",
                    "fallback_models": ["gpt-5"],
                    "temperature": 0.5,
                    "system_prompt": """ROLE: Expert Technical Writer and Research Analyst.
EXPERTISE: Report writing, information synthesis, technical communication, academic writing standards.
GOAL: Compile diverse research findings into a cohesive, professional, and comprehensive report.

INPUTS PROVIDED IN CONTEXT:
- Original research query
- Research findings from multiple investigators
- (Optional) Critique feedback from previous iteration

PROCESS:
1. Analyze all findings, identifying themes, patterns, and connections
2. Reconcile any contradictory information
3. Structure the report logically:
   - Executive Summary
   - Introduction (context and scope)
   - Main Body (organized by themes or sub-topics)
   - Conclusions and Key Takeaways
   - Sources/References
4. Write the report using clear, professional language
5. Integrate citations accurately throughout
6. If critique feedback is provided, address ALL points raised

STYLE REQUIREMENTS:
- Objective and informative tone
- Use Markdown formatting (headers, lists, bold, links)
- Avoid self-referential language
- Use present tense for facts, past tense for historical events
- Proper citation format: [Source Title](URL)

REVISION MODE (if critique provided):
- Address each critique point systematically
- Enhance depth where requested
- Improve clarity and structure
- Add missing information
- Verify all citations""",
                    "native_tools": [],
                    "tools": [],
                    "cli_tools": [],
                    "custom_tools": [],
                    "timeout_seconds": 600,
                    "max_retries": 2,
                    "enable_model_routing": False,
                    "enable_parallel_tools": False,
                    "enable_memory": True,
                }
            }
        },
        {
            "id": "node-dr-critic",
            "type": "custom",
            "position": {"x": 900, "y": 400},
            "data": {
                "label": "Report Critic",
                "agentType": "report_critic",
                "model": "gpt-5",
                "config": {
                    "model": "gpt-5",
                    "fallback_models": ["claude-sonnet-4-5-20250929"],
                    "temperature": 0.2,
                    "system_prompt": """ROLE: Meticulous Editor and Quality Assurance Specialist.
EXPERTISE: Technical editing, fact-checking, academic standards, research methodology.
GOAL: Evaluate the report draft against quality standards and provide actionable feedback.

EVALUATION CRITERIA:
1. **Accuracy & Source Quality**
   - Are facts correct and verifiable?
   - Are sources credible and properly cited?

2. **Depth & Completeness**
   - Does the report fully address the original query?
   - Are there obvious gaps or missing perspectives?

3. **Structure & Clarity**
   - Is the report well-organized and logical?
   - Is the writing clear and professional?

4. **Objectivity & Balance**
   - Are different viewpoints represented?
   - Is bias minimized?

OUTPUT FORMAT:
Provide detailed critique highlighting specific areas needing revision.

CRITICAL: Conclude with a clear decision:
- If the report meets high standards: **[DECISION: PASS]**
- If revisions are needed: **[DECISION: REVISE]**""",
                    "native_tools": ["web_search"],
                    "tools": [],
                    "cli_tools": [],
                    "custom_tools": [],
                    "timeout_seconds": 300,
                    "max_retries": 2,
                    "enable_model_routing": False,
                    "enable_parallel_tools": False,
                    "enable_memory": False,
                }
            }
        },
        {
            "id": "node-dr-conditional",
            "type": "custom",
            "position": {"x": 1150, "y": 300},
            "data": {
                "label": "Quality Check",
                "agentType": "CONDITIONAL_NODE",
                "model": "none",
                "config": {
                    "model": "none",
                    "temperature": 0,
                    "system_prompt": "CONDITIONAL node: Routes based on critic decision (PASS/REVISE).",
                    "native_tools": [],
                    "tools": [],
                    "cli_tools": [],
                    "custom_tools": [],
                    "timeout_seconds": 0,
                    "max_retries": 0,
                    "enable_model_routing": False,
                    "enable_parallel_tools": False,
                    "enable_memory": False,
                    # Conditional node specific config
                    "control_type": "CONDITIONAL_NODE",
                    "condition_expression": "state.get('decision') == 'PASS'",
                    "routing_map": {
                        "true": "node-dr-end",
                        "false": "node-dr-writer"
                    }
                }
            }
        },
        {
            "id": "node-dr-end",
            "type": "custom",
            "position": {"x": 1400, "y": 200},
            "data": {
                "label": "End",
                "agentType": "END_NODE",
                "model": "none",
                "config": {
                    "model": "none",
                    "temperature": 0,
                    "system_prompt": "END node: Final output of research report.",
                    "native_tools": [],
                    "tools": [],
                    "cli_tools": [],
                    "custom_tools": [],
                    "timeout_seconds": 0,
                    "max_retries": 0,
                    "enable_model_routing": False,
                    "enable_parallel_tools": False,
                    "enable_memory": False,
                }
            }
        },
    ],
    edges=[
        {"id": "e-dr-1", "source": "node-dr-start", "target": "node-dr-planner", "type": "smoothstep"},
        {"id": "e-dr-2", "source": "node-dr-planner", "target": "node-dr-researcher", "type": "smoothstep"},
        {"id": "e-dr-3", "source": "node-dr-researcher", "target": "node-dr-writer", "type": "smoothstep"},
        {"id": "e-dr-4", "source": "node-dr-writer", "target": "node-dr-critic", "type": "smoothstep"},
        {"id": "e-dr-5", "source": "node-dr-critic", "target": "node-dr-conditional", "type": "smoothstep"},
        {"id": "e-dr-6", "source": "node-dr-conditional", "target": "node-dr-end", "type": "smoothstep", "label": "PASS"},
        {"id": "e-dr-7", "source": "node-dr-conditional", "target": "node-dr-writer", "type": "smoothstep", "label": "REVISE"},
    ]
)


# =============================================================================
# LEARNING RESEARCH WORKFLOW RECIPE
# =============================================================================
# Pattern: Memory Review -> Plan -> Research -> Synthesize -> Assimilate (learning loop)

LEARNING_RESEARCH_RECIPE = WorkflowRecipe(
    recipe_id="learning_research_workflow",
    name="Learning Research",
    description="Research workflow with memory integration. Retrieves prior knowledge, fills gaps with external research, synthesizes findings, and stores new insights for future use.",
    category="research",
    icon="school",
    tags=["research", "memory", "learning", "rag", "multi-agent"],
    nodes=[
        {
            "id": "node-lr-start",
            "type": "custom",
            "position": {"x": 50, "y": 200},
            "data": {
                "label": "Start",
                "agentType": "START_NODE",
                "model": "none",
                "config": {
                    "model": "none",
                    "temperature": 0,
                    "system_prompt": "START node: Entry point for learning research workflow.",
                    "native_tools": [],
                    "tools": [],
                    "cli_tools": [],
                    "custom_tools": [],
                    "timeout_seconds": 0,
                    "max_retries": 0,
                    "enable_model_routing": False,
                    "enable_parallel_tools": False,
                    "enable_memory": False,
                }
            }
        },
        {
            "id": "node-lr-reviewer",
            "type": "custom",
            "position": {"x": 300, "y": 200},
            "data": {
                "label": "Internal Knowledge Reviewer",
                "agentType": "learning_internal_reviewer",
                "model": "gpt-5",
                "config": {
                    "model": "gpt-5",
                    "fallback_models": ["claude-sonnet-4-5-20250929"],
                    "temperature": 0.2,
                    "system_prompt": """ROLE: Project Knowledge Archivist and Gap Analyst.

DOMAIN EXPERTISE: AI Operations, Agentic Workflows, LangChain/LangGraph, Vector Embeddings, LLM Infrastructure.

GOAL: Search the project's long-term memory AND embedded codebase knowledge for existing relevant information, then identify specific knowledge gaps.

CRITICAL TOOLS:
- 'memory_retrieve': Search for past learnings, decisions, patterns, and facts
- 'codebase_search': Search embedded codebase knowledge

PROCESS:
1. Analyze the user's research query carefully
2. Search BOTH memory and codebase
3. Synthesize ALL findings
4. Identify specific knowledge gaps that require external research

OUTPUT FORMAT:
## Internal Knowledge Summary

### From Project Memory
[Summarize learnings, decisions, patterns, and facts found]

### From Codebase
[Summarize relevant code and documentation found]

## Knowledge Gaps Identified
[List specific areas requiring external research]""",
                    "native_tools": [],
                    "tools": [],
                    "cli_tools": [],
                    "custom_tools": [],
                    "timeout_seconds": 300,
                    "max_retries": 2,
                    "enable_model_routing": False,
                    "enable_parallel_tools": False,
                    "enable_memory": True,
                    "enable_rag": True,
                }
            }
        },
        {
            "id": "node-lr-planner",
            "type": "custom",
            "position": {"x": 600, "y": 200},
            "data": {
                "label": "Learning Research Planner",
                "agentType": "learning_research_planner",
                "model": "claude-sonnet-4-5-20250929",
                "config": {
                    "model": "claude-sonnet-4-5-20250929",
                    "fallback_models": ["gpt-5"],
                    "temperature": 0.3,
                    "system_prompt": """ROLE: AI Operations Research Strategist.

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
                    "native_tools": [],
                    "tools": [],
                    "cli_tools": [],
                    "custom_tools": [],
                    "timeout_seconds": 300,
                    "max_retries": 2,
                    "enable_model_routing": False,
                    "enable_parallel_tools": False,
                    "enable_memory": False,
                }
            }
        },
        {
            "id": "node-lr-researcher",
            "type": "custom",
            "position": {"x": 900, "y": 200},
            "data": {
                "label": "Specialized Researcher",
                "agentType": "learning_external_researcher",
                "model": "gpt-4o-mini",
                "config": {
                    "model": "gpt-4o-mini",
                    "fallback_models": ["gpt-5", "gemini-2.0-flash"],
                    "temperature": 0.3,
                    "system_prompt": """ROLE: Technical Research Specialist.

DOMAIN FOCUS: AI/ML Infrastructure, Agentic Systems, LangChain Ecosystem, Vector Databases.

GOAL: Conduct focused external research on the assigned question using specialized sources.

RESEARCH STRATEGY:
1. **Academic Sources**: Search for ArXiv papers
2. **Code Examples**: Find GitHub implementations
3. **Official Documentation**: Prioritize official docs
4. **Technical Blogs**: Target reputable sources

CRITICAL REQUIREMENTS:
- Use 'web_search' tool actively for each research angle
- Include specific citations in format: [Source Title](URL)
- Extract code snippets when relevant
- Focus on recent information (prefer 2024-2025 content)

OUTPUT FORMAT:
## Research Findings: [Question]

### Key Findings
[Detailed summary of findings]

### Implementation Examples
[Code snippets if applicable]

### Sources
- [Title 1](URL1)
- [Title 2](URL2)""",
                    "native_tools": ["web_search"],
                    "tools": [],
                    "cli_tools": [],
                    "custom_tools": [],
                    "timeout_seconds": 300,
                    "max_retries": 2,
                    "enable_model_routing": True,
                    "enable_parallel_tools": True,
                    "enable_memory": False,
                }
            }
        },
        {
            "id": "node-lr-synthesizer",
            "type": "custom",
            "position": {"x": 1200, "y": 200},
            "data": {
                "label": "Knowledge Synthesizer",
                "agentType": "learning_synthesizer",
                "model": "claude-sonnet-4-5-20250929",
                "config": {
                    "model": "claude-sonnet-4-5-20250929",
                    "fallback_models": ["gpt-5"],
                    "temperature": 0.5,
                    "system_prompt": """ROLE: Senior AI Operations Consultant and Technical Advisor.

GOAL: Synthesize internal project knowledge and external research into actionable, expert guidance.

SYNTHESIS PROCESS:
1. **Prioritize Internal Context**: Start with what's already known
2. **Integrate External Insights**: Layer in new findings
3. **Identify Contradictions**: Note any conflicts
4. **Provide Actionable Recommendations**: Specific steps, configurations, code patterns

OUTPUT FORMAT:

# [Query Topic] - Technical Advisory Report

## Executive Summary
[2-3 sentence overview]

## Internal Context & Baseline
[What we already know from project memory]

## New Insights from Research
[Key findings from external sources with citations]

## Actionable Recommendations
1. **[Category]**: [Specific recommendation]
   - Implementation: [Code snippet or configuration]
   - Rationale: [Why this approach]

## Implementation Examples
```python
# Code examples
```

## Sources & Citations
[Complete list of references]""",
                    "native_tools": [],
                    "tools": [],
                    "cli_tools": [],
                    "custom_tools": [],
                    "timeout_seconds": 600,
                    "max_retries": 2,
                    "enable_model_routing": False,
                    "enable_parallel_tools": False,
                    "enable_memory": False,
                }
            }
        },
        {
            "id": "node-lr-curator",
            "type": "custom",
            "position": {"x": 1200, "y": 400},
            "data": {
                "label": "Knowledge Curator",
                "agentType": "learning_knowledge_curator",
                "model": "gpt-5",
                "config": {
                    "model": "gpt-5",
                    "fallback_models": ["claude-sonnet-4-5-20250929"],
                    "temperature": 0.2,
                    "system_prompt": """ROLE: Knowledge Management Specialist (The Learning Loop).

GOAL: Extract key insights from the research report and store them in the project's long-term memory for future use.

CRITICAL TOOL: You MUST actively use the 'memory_store' tool to save insights.

EXTRACTION PROCESS:
1. Read the report carefully, identifying distinct insights
2. For EACH significant insight, call 'memory_store' with:
   - **memory_content**: A clear, self-contained statement
   - **memory_type**: FACT, DECISION, PATTERN, or LEARNING
   - **importance**: Score 1-10
   - **tags**: Relevant categorization

QUALITY CRITERIA:
- Each memory should be atomic (one clear concept)
- Content should be self-contained
- Avoid storing redundant information
- Prioritize actionable knowledge

TARGET: Store 5-15 high-quality memories per report

OUTPUT FORMAT:
# Knowledge Assimilation Log

## Memories Stored: [Count]

### FACTS ([count])
- ✓ Stored: [Brief description]

### DECISIONS ([count])
- ✓ Stored: [Brief description]

### PATTERNS ([count])
- ✓ Stored: [Brief description]

### LEARNINGS ([count])
- ✓ Stored: [Brief description]

## Summary
[Brief summary of what was learned]""",
                    "native_tools": [],
                    "tools": [],
                    "cli_tools": [],
                    "custom_tools": [],
                    "timeout_seconds": 300,
                    "max_retries": 2,
                    "enable_model_routing": False,
                    "enable_parallel_tools": False,
                    "enable_memory": True,
                }
            }
        },
        {
            "id": "node-lr-end",
            "type": "custom",
            "position": {"x": 1500, "y": 300},
            "data": {
                "label": "End",
                "agentType": "END_NODE",
                "model": "none",
                "config": {
                    "model": "none",
                    "temperature": 0,
                    "system_prompt": "END node: Final output with synthesized report and learning log.",
                    "native_tools": [],
                    "tools": [],
                    "cli_tools": [],
                    "custom_tools": [],
                    "timeout_seconds": 0,
                    "max_retries": 0,
                    "enable_model_routing": False,
                    "enable_parallel_tools": False,
                    "enable_memory": False,
                }
            }
        },
    ],
    edges=[
        {"id": "e-lr-1", "source": "node-lr-start", "target": "node-lr-reviewer", "type": "smoothstep"},
        {"id": "e-lr-2", "source": "node-lr-reviewer", "target": "node-lr-planner", "type": "smoothstep"},
        {"id": "e-lr-3", "source": "node-lr-planner", "target": "node-lr-researcher", "type": "smoothstep"},
        {"id": "e-lr-4", "source": "node-lr-researcher", "target": "node-lr-synthesizer", "type": "smoothstep"},
        {"id": "e-lr-5", "source": "node-lr-synthesizer", "target": "node-lr-curator", "type": "smoothstep"},
        {"id": "e-lr-6", "source": "node-lr-synthesizer", "target": "node-lr-end", "type": "smoothstep"},
        {"id": "e-lr-7", "source": "node-lr-curator", "target": "node-lr-end", "type": "smoothstep"},
    ]
)


# =============================================================================
# RESEARCH & CONTENT EDITOR WORKFLOW RECIPE
# =============================================================================
# Pattern: Deep Researcher -> Editor

RESEARCH_CONTENT_EDITOR_RECIPE = WorkflowRecipe(
    recipe_id="research_content_editor",
    name="Research & Content Editor",
    description="Two-agent workflow that performs comprehensive research and then edits/proofreads the output. The researcher produces detailed, well-structured reports, and the editor verifies citations, enhances structure, and ensures quality.",
    category="research",
    icon="edit_note",
    tags=["research", "editing", "content", "reports"],
    nodes=[
        {
            "id": "node-rce-researcher",
            "type": "custom",
            "position": {"x": 100, "y": 200},
            "data": {
                "label": "Deep Researcher",
                "agentType": "EXECUTE",
                "model": "claude-sonnet-4-5-20250929",
                "config": {
                    "model": "claude-sonnet-4-5-20250929",
                    "fallback_models": ["gpt-5"],
                    "temperature": 0.6,
                    "max_tokens": 4000,
                    "system_prompt": """ROLE: Deep Research Specialist.

EXPERTISE: In-depth research, comprehensive report writing, academic formatting, source synthesis.

GOAL: Perform thorough research on the given topic and produce a comprehensive, well-structured report formatted as if it were an academic submission.

PROCESS:
1. Analyze the research topic and identify key areas to investigate
2. Gather information from reliable sources
3. Synthesize findings into a coherent narrative
4. Structure the report with clear sections and logical flow
5. Ensure all claims are supported with evidence
6. Include proper citations for all sources

OUTPUT REQUIREMENTS:
- Thorough, well-structured report
- Detailed analysis reflecting deep understanding of the topic
- All sources credible and properly cited
- Professional academic formatting
- Clear, logical structure

After completing your report, hand it over to the Editor who will proofread and make edits to ensure accuracy and quality.""",
                    "native_tools": [],
                    "tools": [],
                    "cli_tools": [],
                    "custom_tools": [],
                    "timeout_seconds": 600,
                    "max_retries": 2,
                    "enable_model_routing": False,
                    "enable_parallel_tools": False,
                    "enable_memory": True,
                    "enable_rag": False,
                }
            }
        },
        {
            "id": "node-rce-editor",
            "type": "custom",
            "position": {"x": 500, "y": 200},
            "data": {
                "label": "Editor",
                "agentType": "EXECUTE",
                "model": "claude-sonnet-4-5-20250929",
                "config": {
                    "model": "claude-sonnet-4-5-20250929",
                    "fallback_models": ["gpt-5"],
                    "temperature": 0.7,
                    "max_tokens": 4000,
                    "system_prompt": """ROLE: Professional Editor and Quality Assurance Specialist.

EXPERTISE: Proofreading, document structure enhancement, citation verification, URL validation, academic standards.

GOAL: Review the research report received from the researcher. Meticulously proofread and enhance the document structure, verify citations and URLs, and ensure the final output meets professional standards.

PROCESS:
1. **Grammar & Style Review**: Correct grammatical errors, improve sentence flow, ensure consistent tone
2. **Structure Enhancement**: Ensure logical organization, clear headings, smooth transitions
3. **Citation Verification**: Cross-check all citations for reliability and credibility
4. **URL Validation**: Verify that all URLs are active and lead to the intended information
5. **Content Review**: Identify areas needing clarification or additional detail
6. **Final Polish**: Ensure professional, publication-ready quality

CRITICAL REQUIREMENTS:
- Use 'web_search' to verify facts and citations when needed
- Ensure documents are grammatically correct AND well-organized
- Maintain focus on clarity and coherence
- Provide actionable improvements, not just identification of issues

OUTPUT: A fully edited and improved final report with all changes and improvements incorporated. The output should be the complete, polished document ready for publication.""",
                    "native_tools": ["web_search", "memory_store", "memory_recall"],
                    "tools": [],
                    "cli_tools": [],
                    "custom_tools": [],
                    "timeout_seconds": 600,
                    "max_retries": 2,
                    "enable_model_routing": False,
                    "enable_parallel_tools": True,
                    "enable_memory": True,
                    "enable_rag": False,
                }
            }
        },
    ],
    edges=[
        {"id": "e-rce-1", "source": "node-rce-researcher", "target": "node-rce-editor", "type": "smoothstep"},
    ]
)


# =============================================================================
# RECIPE REGISTRY
# =============================================================================

WORKFLOW_RECIPES = [
    DEEP_RESEARCH_RECIPE,
    LEARNING_RESEARCH_RECIPE,
    RESEARCH_CONTENT_EDITOR_RECIPE,
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
    """Convert a WorkflowRecipe to a dictionary for API response."""
    return {
        "recipe_id": recipe.recipe_id,
        "name": recipe.name,
        "description": recipe.description,
        "category": recipe.category,
        "icon": recipe.icon,
        "tags": recipe.tags,
        "nodes": recipe.nodes,
        "edges": recipe.edges,
        "node_count": len(recipe.nodes),
        "edge_count": len(recipe.edges),
    }
