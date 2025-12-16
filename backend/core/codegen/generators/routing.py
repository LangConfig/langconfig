# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Routing generators for the Executable Workflow Exporter.

Generates routing functions for conditional edges in workflows.
"""

from textwrap import dedent
from typing import Any, Dict, List


class RoutingGenerators:
    """Generators for workflow routing functions."""

    @staticmethod
    def generate_conditional_router(safe_id: str, node_id: str) -> str:
        """Generate a conditional routing function."""
        return dedent(f'''
            def route_{safe_id}(state: WorkflowState) -> str:
                """Route based on conditional node evaluation."""
                route = state.get("conditional_route", "default")
                # Map routes to next nodes - customize as needed
                route_map = {{
                    "true": "next_node_true",
                    "false": "next_node_false",
                    "default": END
                }}
                return route_map.get(route, END)
        ''').strip()

    @staticmethod
    def generate_loop_router(safe_id: str, node_id: str) -> str:
        """Generate a loop routing function."""
        return dedent(f'''
            def route_{safe_id}(state: WorkflowState) -> str:
                """Route based on loop state."""
                route = state.get("loop_route", "continue")
                route_map = {{
                    "continue": "loop_body_node",
                    "exit": "next_after_loop"
                }}
                return route_map.get(route, END)
        ''').strip()

    @staticmethod
    def generate_approval_router(safe_id: str, node_id: str) -> str:
        """Generate an approval routing function."""
        return dedent(f'''
            def route_{safe_id}(state: WorkflowState) -> str:
                """Route based on approval status."""
                route = state.get("approval_route", "reject")
                route_map = {{
                    "continue": "next_node_approved",
                    "reject": END
                }}
                return route_map.get(route, END)
        ''').strip()

    @staticmethod
    def generate_routing_module(nodes: List[Dict[str, Any]], sanitize_name_func) -> str:
        """
        Generate workflow/routing.py with conditional edge functions.

        Args:
            nodes: List of node configurations
            sanitize_name_func: Function to sanitize node names
        """
        routing_functions = []

        for node in nodes:
            node_id = node.get("id", "unknown")
            node_data = node.get("data", {})
            agent_type = node_data.get("agentType", "").lower()
            safe_id = sanitize_name_func(node_id)

            if agent_type in ("conditional", "conditional_node"):
                routing_functions.append(
                    RoutingGenerators.generate_conditional_router(safe_id, node_id)
                )
            elif agent_type in ("loop", "loop_node"):
                routing_functions.append(
                    RoutingGenerators.generate_loop_router(safe_id, node_id)
                )
            elif agent_type in ("approval", "hitl"):
                routing_functions.append(
                    RoutingGenerators.generate_approval_router(safe_id, node_id)
                )

        functions_str = "\n\n\n".join(routing_functions) if routing_functions else "# No routing functions needed"

        header = '''"""Routing functions for conditional edges."""

from langgraph.graph import END

from .state import WorkflowState


'''
        return header + functions_str
