# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Recursion Limit Diagnostics

Comprehensive analysis and reporting for workflow recursion issues.
Helps users understand why their workflow hit the recursion limit and how to fix it.
"""

import logging
from typing import Dict, List, Any, Optional
from collections import Counter

logger = logging.getLogger(__name__)


class RecursionDiagnostics:
    """
    Analyzes workflow execution patterns to diagnose recursion limit issues.
    """

    @staticmethod
    def analyze_recursion_error(
        workflow: Any,
        task_id: int,
        agent_action_history: List[tuple],
        workflow_state: Dict[str, Any],
        error_msg: str
    ) -> Dict[str, Any]:
        """
        Perform comprehensive analysis of a recursion error.

        Args:
            workflow: WorkflowProfile object
            task_id: Task ID
            agent_action_history: List of (agent_name, action_type, timestamp) tuples
            workflow_state: Current state dict with messages
            error_msg: Original error message

        Returns:
            Dictionary with diagnostic data including detected issues and recommendations
        """

        diagnostic_data = {
            "detected_issues": [],
            "loop_pattern": None,
            "tool_loop_detected": False,
            "question_loop_detected": False,
            "graph_cycle_detected": False,
            "missing_end_edge": False,
            "agent_output_preview": "",
            "recommendations": [],
            "execution_summary": {}
        }

        logger.error("=" * 80)
        logger.error("🔍 RECURSION DIAGNOSTICS - DEEP ANALYSIS")
        logger.error("=" * 80)
        logger.error(f"Workflow: {workflow.name} (ID: {workflow.id})")
        logger.error(f"Task: {task_id}")
        logger.error(f"Error: {error_msg}")
        logger.error("")

        # 1. Analyze action history patterns
        if agent_action_history:
            diagnostic_data["execution_summary"] = RecursionDiagnostics._analyze_action_history(
                agent_action_history, diagnostic_data
            )

        # 2. Analyze message content for tool loops and questions
        if workflow_state and workflow_state.get("messages"):
            RecursionDiagnostics._analyze_messages(
                workflow_state.get("messages", []), diagnostic_data
            )

        # 3. Analyze workflow graph topology
        if workflow.workflow_data:
            RecursionDiagnostics._analyze_graph_structure(
                workflow.workflow_data, agent_action_history, diagnostic_data
            )

        # 4. Generate recommendations based on detected issues
        RecursionDiagnostics._generate_recommendations(diagnostic_data)

        # 5. Log comprehensive summary
        RecursionDiagnostics._log_summary(diagnostic_data)

        return diagnostic_data

    @staticmethod
    def _analyze_action_history(
        agent_action_history: List[tuple],
        diagnostic_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze agent action patterns."""

        logger.error("📊 EXECUTION PATTERN ANALYSIS:")
        logger.error(f"Total iterations: {len(agent_action_history)}")

        # Count actions per agent
        agent_counts = Counter(action[0] for action in agent_action_history)
        logger.error("\nActions per agent:")
        for agent, count in agent_counts.most_common():
            logger.error(f"  • {agent}: {count} iterations")
            if count > 15:
                diagnostic_data["detected_issues"].append(
                    f"Agent '{agent}' executed {count} times - possible infinite loop"
                )

        # Show last 20 actions to reveal pattern
        logger.error("\n📋 Last 20 actions:")
        for i, (agent, action_type, timestamp) in enumerate(agent_action_history[-20:], 1):
            logger.error(f"  {i:2d}. {agent} ({action_type})")

        # Detect cycle patterns
        if len(agent_action_history) >= 10:
            last_10_agents = [action[0] for action in agent_action_history[-10:]]
            unique_agents = len(set(last_10_agents))

            if unique_agents <= 2:
                logger.error("")
                logger.error(f"⚠️  LOOP DETECTED: Only {unique_agents} unique agent(s) in last 10 actions")
                logger.error(f"   Pattern: {' → '.join(last_10_agents)}")
                diagnostic_data["loop_pattern"] = ' → '.join(last_10_agents[-5:])
                diagnostic_data["detected_issues"].append("Agent execution loop detected")

                # Single agent repeating = graph topology issue
                if unique_agents == 1:
                    diagnostic_data["missing_end_edge"] = True
                    diagnostic_data["detected_issues"].append(
                        f"Node '{last_10_agents[0]}' executing repeatedly - missing outgoing edge"
                    )

        return {
            "total_iterations": len(agent_action_history),
            "agent_counts": dict(agent_counts),
            "last_10_pattern": ' → '.join([a[0] for a in agent_action_history[-10:]])
        }

    @staticmethod
    def _analyze_messages(
        messages: List[Any],
        diagnostic_data: Dict[str, Any]
    ) -> None:
        """Analyze message content for patterns."""

        logger.error("\n💬 RECENT AGENT MESSAGES:")

        last_messages = messages[-5:] if len(messages) > 5 else messages
        agent_output_lines = []
        tool_calls = []

        for i, msg in enumerate(last_messages, 1):
            msg_type = msg.__class__.__name__ if hasattr(msg, '__class__') else type(msg).__name__
            content = ""

            try:
                if hasattr(msg, 'content'):
                    if isinstance(msg.content, str):
                        content = msg.content
                    elif isinstance(msg.content, list):
                        # Parse structured content (tool calls, text)
                        for item in msg.content:
                            if isinstance(item, dict):
                                if item.get('type') == 'tool_use':
                                    tool_name = item.get('name', 'unknown')
                                    tool_calls.append(tool_name)
                                    content += f"[Tool: {tool_name}] "
                                elif item.get('type') == 'text':
                                    content += item.get('text', '')
                            else:
                                content += str(item)

                # Check for questions
                if '?' in content and 'AI' in msg_type:
                    diagnostic_data["question_loop_detected"] = True
                    diagnostic_data["detected_issues"].append(
                        "Agent asking questions instead of completing task"
                    )

                preview = content[:200] + "..." if len(content) > 200 else content
                logger.error(f"  {i}. [{msg_type}] {preview}")
                agent_output_lines.append(f"[{msg_type}] {preview}")

            except Exception as e:
                logger.warning(f"Could not parse message {i}: {e}")

        # Detect tool loops
        if len(tool_calls) >= 3:
            tool_counts = Counter(tool_calls)
            for tool, count in tool_counts.items():
                if count >= 3:
                    diagnostic_data["tool_loop_detected"] = True
                    diagnostic_data["detected_issues"].append(
                        f"Tool '{tool}' called {count} times in recent messages"
                    )
                    logger.error(f"\n🔄 TOOL LOOP: '{tool}' called {count} times")

        diagnostic_data["agent_output_preview"] = "\n".join(agent_output_lines[-3:])

    @staticmethod
    def _analyze_graph_structure(
        workflow_data: Dict[str, Any],
        agent_action_history: List[tuple],
        diagnostic_data: Dict[str, Any]
    ) -> None:
        """Analyze workflow graph for cycles and missing edges."""

        logger.error("\n🗺️  GRAPH TOPOLOGY ANALYSIS:")

        nodes = workflow_data.get("nodes", [])
        edges = workflow_data.get("edges", [])

        logger.error(f"  Nodes: {len(nodes)}")
        logger.error(f"  Edges: {len(edges)}")

        # Build adjacency list
        graph_adj = {}
        nodes_with_outgoing = set()

        for edge in edges:
            source = edge.get("source")
            target = edge.get("target")
            if source:
                if source not in graph_adj:
                    graph_adj[source] = []
                graph_adj[source].append(target)
                nodes_with_outgoing.add(source)

        # Find nodes without outgoing edges (leaf nodes)
        all_node_ids = {n["id"] for n in nodes if n.get("type") not in ["START_NODE", "END_NODE"]}
        leaf_nodes = all_node_ids - nodes_with_outgoing

        if leaf_nodes:
            logger.error(f"\n⚠️  LEAF NODES (no outgoing edges): {len(leaf_nodes)}")
            for node_id in leaf_nodes:
                node = next((n for n in nodes if n["id"] == node_id), {})
                label = node.get("data", {}).get("label", node_id)
                logger.error(f"  • {node_id} ({label})")

                # Check if this leaf node is the one causing issues
                if agent_action_history:
                    recent_agent = agent_action_history[-1][0]
                    if label == recent_agent or recent_agent in label:
                        diagnostic_data["missing_end_edge"] = True
                        diagnostic_data["detected_issues"].append(
                            f"Node '{label}' has no outgoing edge - workflow doesn't know where to go next"
                        )

        # Simple cycle detection
        def has_cycle(node, visited, rec_stack, path):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph_adj.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor, visited, rec_stack, path):
                        return True
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    cycle_path = path[cycle_start:] + [neighbor]
                    logger.error(f"\n🔄 CYCLE DETECTED: {' → '.join(cycle_path)}")
                    diagnostic_data["graph_cycle_detected"] = True
                    diagnostic_data["detected_issues"].append(
                        f"Graph cycle found: {' → '.join(cycle_path)}"
                    )
                    return True

            path.pop()
            rec_stack.remove(node)
            return False

        visited = set()
        for node_id in graph_adj.keys():
            if node_id not in visited:
                if has_cycle(node_id, visited, set(), []):
                    break

    @staticmethod
    def _generate_recommendations(diagnostic_data: Dict[str, Any]) -> None:
        """Generate specific recommendations based on detected issues."""

        recommendations = diagnostic_data["recommendations"]

        # Issue-specific recommendations
        if diagnostic_data["missing_end_edge"]:
            recommendations.append("🔗 Connect the leaf node to END or another node in the workflow canvas")
            recommendations.append("🎯 Ensure every node has a path to workflow completion")

        if diagnostic_data["graph_cycle_detected"]:
            recommendations.append("🔄 Remove the cycle in your workflow graph")
            recommendations.append("✅ Add conditional edges with proper exit conditions")
            recommendations.append("🛑 Ensure at least one path in every loop leads to END")

        if diagnostic_data["tool_loop_detected"]:
            recommendations.append("🛠️  Add completion criteria to system prompt: 'Stop after X tool calls'")
            recommendations.append("🎯 Check if the tool is returning useful results")
            recommendations.append("💡 Consider limiting tool iterations in the agent config")

        if diagnostic_data["question_loop_detected"]:
            recommendations.append("❓ Agent is asking questions - provide more complete context upfront")
            recommendations.append("📝 Update system prompt: 'Do not ask clarifying questions'")
            recommendations.append("🎯 Add explicit instructions for handling missing information")

        # General recommendations if no specific issues detected
        if not recommendations:
            recommendations.append("📝 Add clear completion criteria to agent system prompt")
            recommendations.append("🎯 Define when the agent should stop (e.g., 'after 10 searches')")
            recommendations.append("🗺️  Review workflow graph for unintended loops")
            recommendations.append("🔍 Check Live Execution Panel for agent behavior patterns")
            recommendations.append("⚙️  If legitimate, increase recursion_limit in node config")

    @staticmethod
    def _log_summary(diagnostic_data: Dict[str, Any]) -> None:
        """Log comprehensive diagnostic summary."""

        logger.error("\n" + "=" * 80)
        logger.error("📋 DIAGNOSTIC SUMMARY")
        logger.error("=" * 80)

        if diagnostic_data["detected_issues"]:
            logger.error("\n❌ DETECTED ISSUES:")
            for i, issue in enumerate(diagnostic_data["detected_issues"], 1):
                logger.error(f"  {i}. {issue}")

        if diagnostic_data["recommendations"]:
            logger.error("\n💡 RECOMMENDATIONS:")
            for i, rec in enumerate(diagnostic_data["recommendations"], 1):
                logger.error(f"  {i}. {rec}")

        logger.error("\n" + "=" * 80)
