# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Deep Research Agent Templates.

Implements a multi-agent deep research workflow with:
- Research Planner (Decomposition)
- Field Researcher (Data Collection)
- Report Writer (Synthesis)
- Report Critic (Reflection/Quality Control)

Based on patterns from:
- Chapter 3: Parallelization
- Chapter 4: Reflection
- Chapter 6: Decomposition
- Chapter 14: Web Search Integration
"""

from core.agents.templates import AgentTemplate, AgentCategory

# Use current model types from your existing templates
MODEL_REASONING = "claude-sonnet-4-5-20250929"  # Best for complex reasoning and writing
MODEL_FAST = "gpt-4o-mini"  # Best for fast data gathering
MODEL_BALANCED = "gpt-5"  # Good balance for critique and general tasks

# =============================================================================
# 1. RESEARCH PLANNER (Decomposition/Chapter 6)
# =============================================================================

RESEARCH_PLANNER = AgentTemplate(
    template_id="deep_research_planner",
    name="Research Planner",
    description="Analyzes research topics and decomposes them into focused sub-queries for comprehensive investigation.",
    category=AgentCategory.PLANNING,
    model=MODEL_REASONING,
    fallback_models=[MODEL_BALANCED],
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
    mcp_tools=[],  # Planner primarily reasons, no tools needed
    enable_model_routing=False,  # Always use powerful model for planning
    enable_parallel_tools=False,
    enable_memory=False,
    tags=["research", "planning", "decomposition"]
)

# =============================================================================
# 2. FIELD RESEARCHER (Data Collection/Chapter 14)
# =============================================================================

FIELD_RESEARCHER = AgentTemplate(
    template_id="field_researcher",
    name="Field Researcher",
    description="Conducts focused web research on specific questions using search tools. Optimized for speed and accuracy.",
    category=AgentCategory.RESEARCH,
    model=MODEL_FAST,  # Optimized for fast data gathering
    fallback_models=[MODEL_BALANCED, "gemini-2.0-flash"],
    temperature=0.3,
    system_prompt="""ROLE: Diligent Data Collector and Analyst.
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
    mcp_tools=["web_search"],  # Requires the web search MCP tool
    enable_model_routing=True,  # Can use cheaper models for straightforward searches
    enable_parallel_tools=True,  # Multiple searches can run concurrently
    enable_memory=False,  # Research is task-specific
    tags=["research", "web-search", "data-collection", "fast"]
)

# =============================================================================
# 3. REPORT WRITER (Synthesis/Producer)
# =============================================================================

REPORT_WRITER = AgentTemplate(
    template_id="report_writer",
    name="Report Writer",
    description="Compiles research findings into comprehensive, professional reports with proper structure and citations.",
    category=AgentCategory.DOCUMENTATION,
    model=MODEL_REASONING,  # Strong synthesis and writing capabilities
    fallback_models=[MODEL_BALANCED],
    temperature=0.5,  # Slightly higher for more natural writing
    system_prompt="""ROLE: Expert Technical Writer and Research Analyst.
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
- Avoid self-referential language (e.g., "I found that...", "In my research...")
- Use present tense for facts, past tense for historical events
- Proper citation format: [Source Title](URL)

REVISION MODE (if critique provided):
- Address each critique point systematically
- Enhance depth where requested
- Improve clarity and structure
- Add missing information
- Verify all citations""",
    mcp_tools=[],
    enable_model_routing=False,  # Always use powerful model for synthesis
    enable_parallel_tools=False,
    enable_memory=True,  # Writer benefits from memory of past reports
    memory_types=["pattern", "learning", "fact"],
    tags=["writing", "synthesis", "documentation", "research"]
)

# =============================================================================
# 4. REPORT CRITIC (Reflection/Chapter 4)
# =============================================================================

REPORT_CRITIC = AgentTemplate(
    template_id="report_critic",
    name="Report Critic",
    description="Evaluates report drafts against quality standards. Provides detailed feedback for iterative improvement.",
    category=AgentCategory.CODE_REVIEW,  # Reusing category for review tasks
    model=MODEL_BALANCED,
    fallback_models=[MODEL_REASONING],
    temperature=0.2,  # Low temperature for consistent, objective evaluation
    system_prompt="""ROLE: Meticulous Editor and Quality Assurance Specialist.
EXPERTISE: Technical editing, fact-checking, academic standards, research methodology.
GOAL: Evaluate the report draft against quality standards and provide actionable feedback.

INPUTS PROVIDED IN CONTEXT:
- Original research query
- Report draft to evaluate

EVALUATION CRITERIA:
1. **Accuracy & Source Quality**
   - Are facts correct and verifiable?
   - Are sources credible and properly cited?
   - Are citations formatted correctly?

2. **Depth & Completeness**
   - Does the report fully address the original query?
   - Is the analysis thorough enough?
   - Are there obvious gaps or missing perspectives?
   - Are key concepts explained adequately?

3. **Structure & Clarity**
   - Is the report well-organized and logical?
   - Are transitions smooth?
   - Is the writing clear and professional?
   - Is formatting consistent?

4. **Objectivity & Balance**
   - Are different viewpoints represented?
   - Is bias minimized?
   - Are limitations acknowledged?

PROCESS:
1. Read the report carefully against the original query
2. Evaluate each criterion systematically
3. Note specific issues with line references where possible
4. Provide actionable suggestions for improvement
5. Optionally use 'web_search' to verify questionable facts

OUTPUT FORMAT:
Provide detailed critique highlighting specific areas needing revision.

CRITICAL: Conclude with a clear decision:
- If the report meets high standards: **[DECISION: PASS]**
- If revisions are needed: **[DECISION: REVISE]**

Be constructive but maintain high standards. The goal is excellence.""",
    mcp_tools=["web_search"],  # Critic can verify facts
    enable_model_routing=False,
    enable_parallel_tools=False,
    enable_memory=False,
    tags=["review", "quality-assurance", "critique", "research"]
)

# =============================================================================
# TEMPLATE REGISTRATION
# =============================================================================

# These templates will be automatically discovered by the registry
# when this module is imported
DEEP_RESEARCH_TEMPLATES = [
    RESEARCH_PLANNER,
    FIELD_RESEARCHER,
    REPORT_WRITER,
    REPORT_CRITIC
]
