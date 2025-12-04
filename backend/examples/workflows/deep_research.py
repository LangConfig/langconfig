# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Deep Research Strategy Implementation.

Multi-agent collaboration workflow implementing:
- Decomposition (Chapter 6)
- Parallelization (Chapter 3)
- Reflection (Chapter 4)
- Web Search Integration (Chapter 14)

This strategy creates comprehensive research reports through iterative refinement.
"""

import logging
import asyncio
import json
from typing import Dict, Any, List, TypedDict, Literal, Optional
from langchain_core.output_parsers import JsonOutputParser
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from langchain_core.runnables.config import RunnableConfig
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

# =============================================================================
# Specialized State Definition
# =============================================================================

class ResearchState(TypedDict):
    """State definition for the Deep Research Strategy."""
    # Core inputs (Required for AgentFactory context)
    project_id: int
    task_id: int  # Used as a base identifier for agents
    original_query: str

    # Workflow Artifacts
    sub_questions: List[str]
    research_findings: Dict[str, str]  # Keyed by sub-question
    current_report_draft: str
    critique_feedback: str

    # Control Flow
    iteration_count: int
    max_iterations: int
    workflow_status: Literal["Planning", "Researching", "Writing", "Critiquing", "Revising", "Completed"]


# =============================================================================
# Strategy Handler
# =============================================================================

class DeepResearchStrategy(BaseStrategy):
    """
    Implements the Deep Research pattern (Multi-Agent Collaboration and Reflection).

    This is a standalone LangGraph workflow that can be invoked directly
    or integrated into the task execution system.
    """

    def __init__(self, config: Dict[str, Any], mcp_manager=None, vector_store=None):
        """Initialize Deep Research Strategy."""
        super().__init__(config)
        # Import AgentFactory here to avoid circular import at module level
        from core.agents.factory import AgentFactory
        self.agent_factory = AgentFactory()
        self.mcp_manager = mcp_manager
        self.vector_store = vector_store
        self.max_iterations = config.get("max_reflection_iterations", 3)
        logger.info(f"Deep Research Strategy initialized (max iterations: {self.max_iterations})")

    # =============================================================================
    # BaseStrategy Abstract Methods (Blueprint-based workflows don't use these)
    # =============================================================================

    async def determine_next_action(self, task, db) -> Dict[str, Any]:
        """Stub - blueprint-based workflows use graph routing instead."""
        raise NotImplementedError("Blueprint-based workflow - use execute() method directly")

    async def prepare_execution(self, task, db) -> Dict[str, Any]:
        """Stub - blueprint-based workflows configure agents within nodes."""
        raise NotImplementedError("Blueprint-based workflow - use execute() method directly")

    async def handle_execution_result(self, task, result, db) -> Dict[str, Any]:
        """Stub - blueprint-based workflows handle results within nodes."""
        raise NotImplementedError("Blueprint-based workflow - use execute() method directly")

    async def handle_qa_result(self, task, qa_result, db) -> Dict[str, Any]:
        """Stub - blueprint-based workflows handle QA within nodes."""
        raise NotImplementedError("Blueprint-based workflow - use execute() method directly")

    # =============================================================================
    # Strategy Nodes
    # =============================================================================

    async def node_plan_research(self, state: ResearchState) -> Dict[str, Any]:
        """
        (Chapter 6: Decomposition) Decomposes the main query using the Planner agent.
        """
        logger.info(f"[NODE: Plan] Decomposing query: {state['original_query'][:50]}...")

        try:
            # Instantiate Planner Agent via Factory
            planner_agent, _, callbacks = await self.agent_factory.create_agent(
                agent_config={
                    "template_id": "deep_research_planner",
                    "model": "claude-3-5-sonnet-20240620",
                    "temperature": 0.3,
                    "system_prompt": """ROLE: Expert Research Strategist.
GOAL: Analyze the main research topic and decompose it into a comprehensive list of focused, independent sub-queries.
OUTPUT FORMAT: ONLY a JSON list of strings. Example: ["Q1...", "Q2...", "Q3..."]""",
                    "mcp_tools": []
                },
                project_id=state['project_id'],
                task_id=f"{state['task_id']}_planner",
                context=f"Main Research Topic: {state['original_query']}"
            )

            # Execute Planner
            directive = f"Generate the research plan for: {state['original_query']}\n\nOutput ONLY a JSON array of 4-8 specific research questions."
            result = await planner_agent.ainvoke(
                {"messages": [HumanMessage(content=directive)]},
                config={"callbacks": callbacks}
            )

            # Extract and Parse Output
            response_content = result.get("messages", [])[-1].content
            try:
                # Try to parse as JSON
                sub_questions = JsonOutputParser().parse(response_content)
                if not isinstance(sub_questions, list) or len(sub_questions) == 0:
                    raise ValueError("Output not a valid list")

                logger.info(f"✓ Planned {len(sub_questions)} sub-questions")
                return {"sub_questions": sub_questions, "workflow_status": "Researching"}

            except Exception as parse_error:
                # Resilience: Fallback if planning fails
                logger.error(f"Planner output parsing failed: {parse_error}. Using original query.")
                return {
                    "sub_questions": [state['original_query']],
                    "workflow_status": "Researching"
                }

        except Exception as e:
            logger.error(f"Planning node failed: {e}")
            # Fallback: Use original query as single question
            return {
                "sub_questions": [state['original_query']],
                "workflow_status": "Researching"
            }

    async def node_execute_research(self, state: ResearchState) -> Dict[str, Any]:
        """
        (Chapter 3 & 14: Parallelization + Web Search) Executes research concurrently.
        """
        logger.info(f"[NODE: Research] Executing {len(state['sub_questions'])} research tasks in parallel...")

        # Prepare tasks for parallel execution
        research_tasks = []
        for i, question in enumerate(state['sub_questions']):
            # Create a researcher agent instance for the task
            try:
                researcher_agent, _, callbacks = await self.agent_factory.create_agent(
                    agent_config={
                        "template_id": "field_researcher",
                        "model": "gpt-4o-mini",
                        "temperature": 0.3,
                        "system_prompt": """ROLE: Research Analyst.
GOAL: Investigate the assigned question using web_search and synthesize findings.
CRITICAL: Include citations [Title](URL).""",
                        "mcp_tools": ["web_search"]
                    },
                    project_id=state['project_id'],
                    task_id=f"{state['task_id']}_researcher_{i}",
                    context=f"Overall Context: {state['original_query']}"
                )

                # Define the execution task
                task = researcher_agent.ainvoke(
                    {"messages": [HumanMessage(content=f"Conduct research on: {question}")]},
                    config={"callbacks": callbacks}
                )
                research_tasks.append((question, task))

            except Exception as e:
                logger.error(f"Failed to create researcher for question '{question}': {e}")
                # Add error placeholder
                research_tasks.append((question, None))

        # Execute concurrently with exception handling
        results = await asyncio.gather(
            *[task if task else asyncio.sleep(0) for _, task in research_tasks],
            return_exceptions=True
        )

        # Process results
        findings = {}
        for i, (question, _) in enumerate(research_tasks):
            result = results[i]
            if isinstance(result, Exception):
                logger.error(f"Research task failed for '{question}': {result}")
                findings[question] = f"[Research Error: Unable to gather information on this topic]"
            elif result is None:
                findings[question] = "[Research Error: Agent creation failed]"
            else:
                # Extract content from agent's final message
                content = result.get("messages", [])[-1].content if result.get("messages") else "No response"
                # Ensure content is a string (handle cases where content might be a list of blocks)
                if isinstance(content, list):
                    # Extract text from content blocks: [{'text': '...', 'type': 'text'}, ...]
                    content = "".join(
                        block.get("text", "") if isinstance(block, dict) else str(block)
                        for block in content
                    )
                elif not isinstance(content, str):
                    content = str(content)
                findings[question] = content

        logger.info(f"✓ Research phase completed ({len(findings)} questions answered)")
        return {"research_findings": findings, "workflow_status": "Writing"}

    async def node_write_report(self, state: ResearchState) -> Dict[str, Any]:
        """
        (Producer) Synthesizes findings into a comprehensive report draft.
        """
        iteration = state.get('iteration_count', 0) + 1
        logger.info(f"[NODE: Write] Synthesizing report (Iteration {iteration})...")

        # Prepare context for the Writer
        context = f"Original Query: {state['original_query']}\n\n--- RESEARCH FINDINGS ---\n"
        for question, finding in state['research_findings'].items():
            context += f"## Question: {question}\nFindings:\n{finding}\n\n"

        # Add critique if this is a revision (Chapter 4: Closed Loop)
        if state.get('critique_feedback'):
            context += f"\n--- CRITIQUE TO ADDRESS ---\n{state['critique_feedback']}\n"
            directive = "Revise the report based on the critique and the research findings. Address ALL feedback points."
        else:
            directive = "Generate a comprehensive research report based on the findings."

        try:
            # Instantiate Writer Agent
            writer_agent, _, callbacks = await self.agent_factory.create_agent(
                agent_config={
                    "template_id": "report_writer",
                    "model": "claude-3-5-sonnet-20240620",
                    "temperature": 0.5,
                    "system_prompt": """ROLE: Expert Technical Writer.
GOAL: Compile research findings into a cohesive, professional report.
STRUCTURE: Executive Summary, Introduction, Main Body, Conclusions, Sources.
STYLE: Objective, professional, with proper Markdown formatting and citations.""",
                    "mcp_tools": []
                },
                project_id=state['project_id'],
                task_id=f"{state['task_id']}_writer_{iteration}",
                context=context
            )

            # Execute Writer
            result = await writer_agent.ainvoke(
                {"messages": [HumanMessage(content=directive)]},
                config={"callbacks": callbacks}
            )

            report_draft = result.get("messages", [])[-1].content
            logger.info("✓ Report draft generated/revised")

            return {
                "current_report_draft": report_draft,
                "workflow_status": "Critiquing",
                "iteration_count": iteration
            }

        except Exception as e:
            logger.error(f"Writing node failed: {e}")
            # Return a basic report from findings if writer fails
            basic_report = "# Research Report\n\n" + "\n\n".join(
                [f"## {q}\n{f}" for q, f in state['research_findings'].items()]
            )
            return {
                "current_report_draft": basic_report,
                "workflow_status": "Completed",  # Skip critique if writer failed
                "iteration_count": iteration
            }

    async def node_critique_report(self, state: ResearchState) -> Dict[str, Any]:
        """
        (Chapter 4: Reflection) Evaluates the report draft for quality.
        """
        logger.info("[NODE: Critique] Evaluating report draft...")

        # Prepare context for the Critic
        context = f"""Original Query: {state['original_query']}

--- REPORT DRAFT TO REVIEW ---
{state['current_report_draft']}
--- END DRAFT ---"""

        try:
            # Instantiate Critic Agent
            critic_agent, _, callbacks = await self.agent_factory.create_agent(
                agent_config={
                    "template_id": "report_critic",
                    "model": "gpt-4o",
                    "temperature": 0.2,
                    "system_prompt": """ROLE: Quality Assurance Specialist.
GOAL: Evaluate report draft against quality standards.
EVALUATE: Accuracy, Depth, Structure, Clarity.
CONCLUDE: [DECISION: PASS] or [DECISION: REVISE] with specific feedback.""",
                    "mcp_tools": ["web_search"]  # Can verify facts
                },
                project_id=state['project_id'],
                task_id=f"{state['task_id']}_critic_{state['iteration_count']}",
                context=context
            )

            # Execute Critic
            directive = "Evaluate the report draft. Provide actionable critique and conclude with [DECISION: PASS] or [DECISION: REVISE]."
            result = await critic_agent.ainvoke(
                {"messages": [HumanMessage(content=directive)]},
                config={"callbacks": callbacks}
            )

            critique = result.get("messages", [])[-1].content

            # Determine decision based on the marker
            if "[DECISION: PASS]" in critique:
                logger.info("✓ Critique passed - report approved")
                return {"critique_feedback": critique, "workflow_status": "Completed"}
            else:
                logger.info("Critique identified revisions needed")
                return {"critique_feedback": critique, "workflow_status": "Revising"}

        except Exception as e:
            logger.error(f"Critique node failed: {e}. Passing report by default.")
            return {
                "critique_feedback": "Critique failed - accepting report",
                "workflow_status": "Completed"
            }

    # =============================================================================
    # Blueprint-Compatible Strategy Methods
    # =============================================================================

    async def process_research_plan(self, state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
        """
        Process the planner agent's output and extract sub-questions into strategy_state.

        This is called after the plan_research node executes. The planner outputs a JSON array
        of research questions in a handoff structure. This method extracts that array and
        populates strategy_state['sub_questions'] for use by parallel_field_research.

        Args:
            state: WorkflowState with agent handoffs
            config: LangGraph runtime configuration

        Returns:
            State updates with sub_questions in strategy_state
        """
        logger.info("[STRATEGY] Processing research plan output...")

        # Extract the planner's handoff actions (contains JSON output)
        handoffs = state.get('handoffs', [])
        sub_questions = []

        # Find the most recent handoff (from plan_research node)
        if handoffs:
            latest_handoff = handoffs[-1]
            actions = latest_handoff.get('actions', [])

            # The JSON array should be in the first action's content or rationale
            if actions:
                action_content = actions[0].get('content', '')

                # Try to parse as JSON array
                try:
                    # Remove markdown code blocks if present
                    content = action_content.strip()
                    if content.startswith('```'):
                        # Extract content between ``` markers
                        lines = content.split('\n')
                        content = '\n'.join(lines[1:-1]) if len(lines) > 2 else content
                        content = content.replace('```json', '').replace('```', '').strip()

                    # Parse JSON
                    parsed = json.loads(content)

                    if isinstance(parsed, list) and len(parsed) > 0:
                        sub_questions = parsed
                        logger.info(f"✓ Extracted {len(sub_questions)} sub-questions from planner output")
                    else:
                        logger.warning(f"Planner output is not a valid list: {parsed}")

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse planner output as JSON: {e}")
                    logger.error(f"Content was: {action_content[:200]}")

        # Fallback: use original directive if no questions extracted
        if not sub_questions:
            logger.warning("No sub-questions extracted from planner. Using original directive.")
            sub_questions = [state.get('current_directive', 'Research query not provided')]

        # Update strategy_state with extracted questions
        strategy_state = state.get('strategy_state', {})
        updated_strategy_state = {
            **strategy_state,
            'sub_questions': sub_questions,
            'planning_completed': True
        }

        return {
            'strategy_state': updated_strategy_state,
            'workflow_status': f"Planned {len(sub_questions)} research questions"
        }

    async def execute_parallel_research(
        self,
        state: Dict[str, Any],
        config: RunnableConfig,
        node_agent_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute parallel field research. Compatible with blueprint-based workflows.

        AGENT-LEVEL PARALLELISM:
        This method spawns multiple independent AGENT instances in parallel (not multiple tools).
        Each agent operates independently with its own LLM calls, tools, and reasoning.
        This is different from tool-level parallelism, which is handled automatically
        by LangGraph's ToolNode when a single agent calls multiple tools.

        Implementation:
        - Uses asyncio.gather() to run multiple agent invocations concurrently
        - Each agent processes one sub-question from the research plan
        - Results are aggregated after all agents complete

        Args:
            state: WorkflowState dictionary containing 'strategy_state' with 'sub_questions'
            config: LangGraph runtime configuration
            node_agent_config: Optional agent configuration from blueprint (NEW)

        Returns:
            State updates with research findings from all parallel agents
        """
        logger.info("[STRATEGY] Executing parallel field research...")

        # Extract sub-questions from strategy_state
        strategy_state = state.get('strategy_state', {})
        sub_questions = strategy_state.get('sub_questions', [])

        if not sub_questions:
            logger.warning("No sub-questions found in strategy_state. Using original directive as single question.")
            sub_questions = [state.get('current_directive', 'Research query not found')]

        logger.info(f"Launching {len(sub_questions)} parallel research tasks...")

        # Build agent config from blueprint with defaults for missing fields
        if node_agent_config:
            logger.info(f"[PARALLEL_RESEARCH] Using blueprint agent config: "
                       f"model={node_agent_config.get('model')}, "
                       f"DeepAgents={node_agent_config.get('deep_agents_config', {}).get('enabled', False)}, "
                       f"MCP tools={node_agent_config.get('mcp_tools', [])}")
            researcher_config = node_agent_config.copy()
            researcher_config['template_id'] = 'field_researcher'  # Ensure correct template

            # CRITICAL: Add defaults for missing/empty fields (blueprint may be incomplete)
            # Check both: key doesn't exist OR value is empty/falsy
            if not researcher_config.get('mcp_tools'):
                researcher_config['mcp_tools'] = ["web_search"]  # Default MCP tool for research
                logger.info(f"[PARALLEL_RESEARCH] Added default mcp_tools: {researcher_config['mcp_tools']}")
        else:
            logger.warning("[PARALLEL_RESEARCH] No blueprint config provided, using hardcoded defaults")
            researcher_config = {
                "template_id": "field_researcher",
                "model": "gpt-4o-mini",
                "temperature": 0.3,
                "mcp_tools": ["web_search", "puppeteer-browser"],
                "enable_model_routing": True,
                "enable_parallel_tools": True
            }

        # Build descriptive status message for UI
        questions_summary = "\n".join([f"  {i+1}. {q}" for i, q in enumerate(sub_questions)])
        status_message = f"Running {len(sub_questions)} parallel researchers:\n{questions_summary}"

        # Execute research tasks concurrently
        research_tasks = []
        for i, question in enumerate(sub_questions):
            try:
                # Determine whether to use DeepAgents
                use_deep_agents = researcher_config.get('deep_agents_config', {}).get('enabled', False)

                logger.info(f"[RESEARCHER_{i}] Creating agent with DeepAgents={use_deep_agents}, "
                           f"model={researcher_config.get('model')}")

                # Create researcher agent for this question
                if use_deep_agents:
                    researcher_agent, _, callbacks = await self.agent_factory.create_deep_agent(
                        agent_config=researcher_config,
                        project_id=state.get('project_id'),
                        task_id=f"{state.get('task_id')}_researcher_{i}",
                        context=f"Overall Research Topic: {state.get('original_directive', '')}",
                        mcp_manager=self.mcp_manager,
                        vector_store=self.vector_store
                    )
                else:
                    researcher_agent, _, callbacks = await self.agent_factory.create_agent(
                        agent_config=researcher_config,
                        project_id=state.get('project_id'),
                        task_id=f"{state.get('task_id')}_researcher_{i}",
                        context=f"Overall Research Topic: {state.get('original_directive', '')}",
                        mcp_manager=self.mcp_manager,
                        vector_store=self.vector_store
                    )

                # Create task for this researcher
                task = researcher_agent.ainvoke(
                    {"messages": [HumanMessage(content=f"Conduct research on: {question}")]},
                    config={"callbacks": callbacks}
                )
                research_tasks.append((question, task))

            except Exception as e:
                logger.error(f"Failed to create researcher for question '{question}': {e}")
                research_tasks.append((question, None))

        # Execute all research tasks concurrently
        results = await asyncio.gather(
            *[task if task else asyncio.sleep(0) for _, task in research_tasks],
            return_exceptions=True
        )

        # Process results into findings dictionary
        findings = {}
        for i, (question, _) in enumerate(research_tasks):
            result = results[i]
            if isinstance(result, Exception):
                logger.error(f"Research task failed for '{question}': {result}")
                findings[question] = f"[Research Error: {str(result)}]"
            elif result is None:
                findings[question] = "[Research Error: Agent creation failed]"
            else:
                # Extract content from agent's response
                content = result.get("messages", [])[-1].content if result.get("messages") else "No response"
                # Ensure content is a string (handle cases where content might be a list of blocks)
                if isinstance(content, list):
                    # Extract text from content blocks: [{'text': '...', 'type': 'text'}, ...]
                    content = "".join(
                        block.get("text", "") if isinstance(block, dict) else str(block)
                        for block in content
                    )
                elif not isinstance(content, str):
                    content = str(content)
                findings[question] = content

        logger.info(f"✓ Parallel research completed ({len(findings)} questions researched)")

        # Update strategy_state with findings
        updated_strategy_state = {
            **strategy_state,
            "research_findings": findings,
            "research_completed": True,
            "parallel_agent_summary": status_message  # Store for UI display
        }

        # Preserve existing scratchpad - don't wipe it!
        existing_scratchpad = state.get('workflow_scratchpad', '')

        return {
            "strategy_state": updated_strategy_state,
            "workflow_status": f"Completed {len(findings)}/{len(sub_questions)} parallel research tasks",
            "workflow_scratchpad": existing_scratchpad,  # Preserve scratchpad
            "current_step": "parallel_field_research"  # Set current step for UI display
        }

    async def synchronize_parallel_agents(self, state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
        """
        Synchronize and aggregate results from parallel research agents.

        This method waits for all parallel agents to complete and aggregates their
        findings into a structured format for the report writer.

        Args:
            state: WorkflowState dictionary containing strategy_state with research_findings
            config: LangGraph runtime configuration

        Returns:
            State updates with aggregated research findings in workflow_scratchpad
        """
        logger.info("[STRATEGY] Synchronizing parallel research results...")

        strategy_state = state.get('strategy_state', {})
        findings = strategy_state.get('research_findings', {})

        if not findings:
            logger.warning("No research findings found to synchronize")
            return {
                "workflow_scratchpad": "No research findings available.",
                "workflow_status": "RESEARCH_FAILED"
            }

        # Aggregate findings into a formatted summary
        aggregated_output = "# Research Findings\n\n"
        for i, (question, finding) in enumerate(findings.items(), 1):
            aggregated_output += f"## Finding {i}: {question}\n\n{finding}\n\n"

        logger.info(f"✓ Synchronized {len(findings)} research findings")

        # APPEND to existing scratchpad, don't replace!
        existing_scratchpad = state.get('workflow_scratchpad', '')
        new_scratchpad = f"{existing_scratchpad}\n\n=== Research Findings ===\n{aggregated_output}" if existing_scratchpad else aggregated_output

        return {
            "workflow_scratchpad": new_scratchpad,  # Append, don't replace
            "workflow_status": f"Synchronized {len(findings)} research findings into report draft",
            "current_step": "synchronize_researchers",  # Set current step for UI display
            "strategy_state": {
                **strategy_state,
                "aggregated_research": aggregated_output
            }
        }

    def route_after_critique(self, state: Dict[str, Any]) -> str:
        """
        Route workflow after critique evaluation.

        Returns one of: "PASS", "REVISE", or "MAX_REVISIONS"

        Increments iteration_count when routing to REVISE.

        Args:
            state: WorkflowState dictionary

        Returns:
            Routing key for conditional edge
        """
        strategy_state = state.get('strategy_state', {})
        iteration_count = strategy_state.get('iteration_count', 0)
        workflow_status = state.get('workflow_status', '')

        # Get max revision settings
        max_revisions = strategy_state.get('max_revisions', 2)

        # Check if max revisions reached (check BEFORE incrementing)
        if iteration_count >= max_revisions:
            logger.warning(f"Max revisions ({max_revisions}) reached - routing to HITL")
            return "MAX_REVISIONS"

        # DISABLED: Forced revisions are broken and blocking workflows
        # # Force revision if we haven't met minimum requirement
        # min_revisions = strategy_state.get('min_revisions', 0)
        # if iteration_count < min_revisions:
        #     logger.info(f"Forcing revision {iteration_count + 1} of {min_revisions} (min_revisions={min_revisions})")
        #     state['strategy_state']['iteration_count'] = iteration_count + 1
        #     return "REVISE"

        # Check if critique passed
        if "PASS" in workflow_status.upper() or workflow_status == "COMPLETED":
            logger.info("✓ Critique passed - routing to completion")
            return "PASS"

        # Need revision based on critique feedback
        logger.info(f"Critique requires revision (iteration {iteration_count + 1})")
        # Increment iteration counter when routing to REVISE
        state['strategy_state']['iteration_count'] = iteration_count + 1
        return "REVISE"

    # =============================================================================
    # Routing Logic (Legacy - for standalone graph execution)
    # =============================================================================

    def route_after_critique_legacy(self, state: ResearchState) -> Literal["revise", "end"]:
        """Determines whether to revise the report or finalize (legacy standalone graph)."""
        if state['workflow_status'] == "Completed":
            return "end"

        if state['iteration_count'] >= self.max_iterations:
            logger.warning(f"Max reflection iterations ({self.max_iterations}) reached. Finalizing.")
            return "end"

        # If status is "Revising", loop back to the writer
        return "revise"

    # =============================================================================
    # Graph Construction
    # =============================================================================

    def build_graph(self) -> CompiledStateGraph:
        """
        Defines the structure of the Deep Research workflow.

        Returns:
            Compiled LangGraph workflow ready for execution.
        """
        logger.info("Building Deep Research workflow graph...")

        workflow = StateGraph(ResearchState)

        # Define Nodes
        workflow.add_node("plan_research", self.node_plan_research)
        workflow.add_node("execute_research", self.node_execute_research)
        workflow.add_node("write_report", self.node_write_report)
        workflow.add_node("critique_report", self.node_critique_report)

        # Define Edges
        workflow.add_edge(START, "plan_research")
        workflow.add_edge("plan_research", "execute_research")
        workflow.add_edge("execute_research", "write_report")
        workflow.add_edge("write_report", "critique_report")

        # Reflection Loop (Conditional Edge)
        workflow.add_conditional_edges(
            "critique_report",
            self.route_after_critique,
            {
                "PASS": END,  # Critique passed - finalize
                "REVISE": "write_report",  # Loop back for refinement
                "MAX_REVISIONS": END  # Max iterations reached - finalize
            }
        )

        # Compile the graph
        compiled_graph = workflow.compile()
        logger.info("✓ Deep Research workflow graph compiled successfully")

        return compiled_graph

    async def execute(
        self,
        query: str,
        project_id: int,
        task_id: int,
        max_iterations: int = 3
    ) -> Dict[str, Any]:
        """
        Execute the deep research workflow.

        Args:
            query: Research question/topic
            project_id: Project context ID
            task_id: Task context ID
            max_iterations: Maximum reflection iterations

        Returns:
            Dictionary with final report and metadata
        """
        logger.info(f"Executing Deep Research for: {query[:100]}...")

        # Build the workflow
        graph = self.build_graph()

        # Initialize state
        initial_state: ResearchState = {
            "project_id": project_id,
            "task_id": task_id,
            "original_query": query,
            "sub_questions": [],
            "research_findings": {},
            "current_report_draft": "",
            "critique_feedback": "",
            "iteration_count": 0,
            "max_iterations": max_iterations,
            "workflow_status": "Planning"
        }

        # Execute workflow
        try:
            final_state = await graph.ainvoke(initial_state)

            logger.info(f"✓ Deep Research completed (iterations: {final_state['iteration_count']})")

            return {
                "success": True,
                "report": final_state['current_report_draft'],
                "iterations": final_state['iteration_count'],
                "sub_questions": final_state['sub_questions'],
                "workflow_status": final_state['workflow_status']
            }

        except Exception as e:
            logger.error(f"Deep Research workflow failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "report": "Research workflow encountered an error."
            }
