# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
LangConfig LangGraph Code Generator.

Automatically generates clean, portable Python LangGraph code from React Flow blueprint definitions.
Implements LangGraph best practices:
- Artifact-focused state management
- Nodes return only updates
- Conditional edges for branching logic
- Proper START/END connections
"""

import logging
from typing import Dict, Any, List, Optional
from textwrap import indent, dedent

logger = logging.getLogger(__name__)


class LangGraphCodeGenerator:
    """
    Generates LangGraph Python code from blueprint JSON definitions.

    Usage:
        generator = LangGraphCodeGenerator()
        code = generator.generate_from_blueprint(blueprint_data)
        with open('generated_workflow.py', 'w') as f:
            f.write(code)
    """

    def __init__(self):
        self.indent_level = 0

    def generate_from_workflow(self, workflow_dict: Dict[str, Any]) -> str:
        """
        Generate LangGraph code from a workflow dictionary.

        Args:
            workflow_dict: Workflow data from database including blueprint

        Returns:
            Generated Python code as string
        """
        blueprint = workflow_dict.get('blueprint', {})

        # Extract workflow metadata
        workflow_data = {
            'strategy_type': workflow_dict.get('strategy_type', 'CUSTOM'),
            'name': workflow_dict.get('name', 'Custom Workflow'),
            'description': workflow_dict.get('description', ''),
            'nodes': self._convert_reactflow_nodes(blueprint.get('nodes', [])),
            'edges': self._convert_reactflow_edges(blueprint.get('edges', []))
        }

        return self.generate_from_blueprint(workflow_data)

    def _convert_reactflow_nodes(self, reactflow_nodes: List[Dict]) -> List[Dict]:
        """Convert ReactFlow nodes to blueprint node format."""
        blueprint_nodes = []

        for node in reactflow_nodes:
            node_id = node.get('id', 'unknown')
            node_data = node.get('data', {})

            blueprint_node = {
                'node_id': node_id,
                'display_name': node_data.get('label', node_id),
                'node_type': 'EXECUTE',  # Default type
                'handler_function': f'node_{self._sanitize_name(node_id)}',
                'metadata': node_data.get('config', {})
            }

            blueprint_nodes.append(blueprint_node)

        return blueprint_nodes

    def _convert_reactflow_edges(self, reactflow_edges: List[Dict]) -> List[Dict]:
        """Convert ReactFlow edges to blueprint edge format."""
        blueprint_edges = []

        for edge in reactflow_edges:
            blueprint_edge = {
                'source_id': edge.get('source'),
                'target_id': edge.get('target'),
                'edge_type': edge.get('type', 'DIRECT').upper()
            }

            blueprint_edges.append(blueprint_edge)

        return blueprint_edges

    def generate_from_blueprint(self, blueprint: Dict[str, Any]) -> str:
        """
        Generate complete LangGraph workflow code from blueprint.

        Args:
            blueprint: Blueprint dictionary with nodes and edges

        Returns:
            Generated Python code as string
        """
        strategy_type = blueprint.get('strategy_type', 'CUSTOM')
        name = blueprint.get('name', 'Custom Workflow')
        description = blueprint.get('description', '')
        nodes = blueprint.get('nodes', [])
        edges = blueprint.get('edges', [])

        logger.info(f"Generating LangGraph code for: {name}")

        # Generate code sections
        imports = self._generate_imports()
        context_class = self._generate_context_class()
        state_class = self._generate_state_class(nodes, blueprint)
        strategy_class = self._generate_strategy_class(
            strategy_type,
            name,
            description,
            nodes,
            edges
        )

        # Generate usage example
        usage_example = self._generate_usage_example(strategy_type, name)
        middleware_example = self._generate_middleware_example()
        setup_guide = self._generate_setup_guide(nodes)

        # Combine all sections
        code = f"""{imports}


# =============================================================================
# RUNTIME CONTEXT (Not Checkpointed)
# =============================================================================

{context_class}


# =============================================================================
# WORKFLOW STATE (Checkpointed)
# =============================================================================

{state_class}


# =============================================================================
# WORKFLOW STRATEGY
# =============================================================================

{strategy_class}


# =============================================================================
# MIDDLEWARE & DYNAMIC PROMPTS
# =============================================================================

{middleware_example}


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

{usage_example}


# =============================================================================
# INFRASTRUCTURE SETUP GUIDE
# =============================================================================

{setup_guide}
"""
        return code

    def _generate_imports(self) -> str:
        """Generate import statements."""
        return dedent('''
        """
        Auto-generated LangGraph Workflow

        Generated by LangConfig Code Generator

        This file contains a complete, standalone LangGraph workflow.
        """

        import logging
        import operator
        from typing import Dict, Any, List, TypedDict, Literal, Optional, Annotated
        from dataclasses import dataclass
        from langgraph.graph import StateGraph, START, END
        from langgraph.graph.state import CompiledStateGraph
        from langchain_core.messages import HumanMessage, SystemMessage

        logger = logging.getLogger(__name__)
        ''').strip()

    def _generate_context_class(self) -> str:
        """Generate WorkflowContext class for runtime configuration."""
        return dedent('''
        @dataclass
        class WorkflowContext:
            """
            Runtime configuration context.

            Not checkpointed - passed at runtime.
            """
            model_name: str = "gpt-4o"
            temperature: float = 0.7
            max_tokens: Optional[int] = None
            user_id: Optional[int] = None
            session_id: Optional[str] = None
            max_iterations: int = 3
        ''').strip()

    def _generate_state_class(self, nodes: List[Dict], blueprint: Dict) -> str:
        """Generate artifact-focused state class."""
        state_lines = [
            "class WorkflowState(TypedDict):",
            '    """Workflow state definition."""',
            '    task: str  # Input task',
            '    workflow_status: str',
            '    iteration_count: int',
            '    step_history: Annotated[List[str], operator.add]',
        ]

        # Add artifact fields from nodes
        for node in nodes:
            node_id = node.get('node_id', 'unknown')
            sanitized = self._sanitize_name(node_id)
            state_lines.append(f'    {sanitized}_output: str')

        return '\n'.join(state_lines)

    def _generate_strategy_class(
        self,
        strategy_type: str,
        name: str,
        description: str,
        nodes: List[Dict],
        edges: List[Dict]
    ) -> str:
        """Generate the main strategy class."""
        class_name = self._sanitize_class_name(strategy_type)

        code_lines = [
            f'class {class_name}:',
            '    """',
            f'    {name}',
            '    ',
            f'    {description}',
            '    """',
            '',
            '    def __init__(self):',
            '        logger.info(f"{self.__class__.__name__} initialized")',
            '',
        ]

        # Generate node methods
        for node in nodes:
            node_method = self._generate_node_method(node)
            code_lines.append(indent(node_method, '    '))
            code_lines.append('')

        # Generate build_graph method
        build_graph = self._generate_build_graph_method(nodes, edges)
        code_lines.append(indent(build_graph, '    '))
        code_lines.append('')

        # Generate execute method
        execute_method = self._generate_execute_method(nodes)
        code_lines.append(indent(execute_method, '    '))

        return '\n'.join(code_lines)

    def _generate_node_method(self, node: Dict) -> str:
        """Generate a single node method."""
        node_id = node.get('node_id', 'unknown')
        display_name = node.get('display_name', node_id)
        metadata = node.get('metadata', {})
        model = metadata.get('model', 'gpt-4o')
        system_prompt = metadata.get('system_prompt', 'You are a helpful AI assistant.')

        method_name = f'node_{self._sanitize_name(node_id)}'
        output_field = f'{self._sanitize_name(node_id)}_output'

        lines = [
            f'async def {method_name}(self, state: WorkflowState, context: WorkflowContext) -> Dict[str, Any]:',
            '    """',
            f'    {display_name}',
            '    """',
            f'    logger.info(f"[{display_name}] Starting...")',
            '    ',
            f'    # TODO: Implement {display_name} logic',
            f'    output = f"Output from {display_name}"',
            '    ',
            '    return {',
            f'        "{output_field}": output,',
            f'        "workflow_status": "{display_name}",',
            '        "iteration_count": state.get("iteration_count", 0) + 1,',
            f'        "step_history": [f"{display_name} completed"],',
            '    }',
        ]

        return '\n'.join(lines)

    def _generate_build_graph_method(self, nodes: List[Dict], edges: List[Dict]) -> str:
        """Generate the build_graph method."""
        lines = [
            'def build_graph(self) -> CompiledStateGraph:',
            '    """Build the LangGraph workflow."""',
            '    logger.info("Building workflow graph...")',
            '    ',
            '    workflow = StateGraph(WorkflowState)',
            '    ',
            '    # Add nodes',
        ]

        # Add all nodes
        for node in nodes:
            node_id = node.get('node_id')
            method_name = f'node_{self._sanitize_name(node_id)}'
            lines.append(f'    workflow.add_node("{node_id}", self.{method_name})')

        lines.append('    ')

        # Add entry point
        if nodes:
            entry_point = nodes[0].get('node_id')
            lines.append(f'    workflow.add_edge(START, "{entry_point}")')

        lines.append('    ')

        # Add edges
        for edge in edges:
            source = edge.get('source_id')
            target = edge.get('target_id')
            if target and target != '__END__':
                lines.append(f'    workflow.add_edge("{source}", "{target}")')
            else:
                lines.append(f'    workflow.add_edge("{source}", END)')

        lines.extend([
            '    ',
            '    compiled_graph = workflow.compile(',
            '        context_schema=WorkflowContext',
            '    )',
            '    logger.info("✓ Workflow graph compiled")',
            '    return compiled_graph',
        ])

        return '\n'.join(lines)

    def _generate_execute_method(self, nodes: List[Dict]) -> str:
        """Generate the execute method."""
        # Build initial state with all output fields
        init_fields = ['        "task": task,']
        for node in nodes:
            node_id = node.get('node_id')
            field = f'{self._sanitize_name(node_id)}_output'
            init_fields.append(f'        "{field}": "",')

        init_fields.extend([
            '        "workflow_status": "Initializing",',
            '        "iteration_count": 0,',
            '        "step_history": [],',
        ])

        return dedent(f'''
        async def run(self, task: str, context: Optional[WorkflowContext] = None) -> Dict[str, Any]:
            """Execute the workflow."""
            if context is None:
                context = WorkflowContext()

            graph = self.build_graph()

            initial_state: WorkflowState = {{
{chr(10).join(init_fields)}
            }}

            try:
                final_state = await graph.ainvoke(initial_state, context=context)
                logger.info(f"✓ Workflow completed")
                return {{"success": True, "final_state": final_state}}
            except Exception as e:
                logger.error(f"Workflow failed: {{e}}")
                return {{"success": False, "error": str(e)}}
        ''').strip()

    def _generate_middleware_example(self) -> str:
        """Generate middleware example."""
        return '# Middleware can be added here'

    def _generate_usage_example(self, strategy_type: str, name: str) -> str:
        """Generate usage example."""
        class_name = self._sanitize_class_name(strategy_type)

        return dedent(f'''
        async def main():
            """Example usage."""
            logging.basicConfig(level=logging.INFO)

            workflow = {class_name}()
            context = WorkflowContext(model_name="gpt-4o")

            result = await workflow.run("Your task here", context=context)

            if result["success"]:
                print("✓ Workflow completed!")
                print(result["final_state"])
            else:
                print(f"✗ Workflow failed: {{result['error']}}")


        if __name__ == "__main__":
            import asyncio
            asyncio.run(main())
        ''').strip()

    def _generate_setup_guide(self, nodes: List[Dict]) -> str:
        """Generate setup guide."""
        return dedent('''
        """
        SETUP GUIDE

        Dependencies:
        ```bash
        pip install langgraph langchain langchain-openai
        ```

        Environment:
        ```bash
        export OPENAI_API_KEY=sk-...
        ```
        """
        ''').strip()

    def _sanitize_name(self, name: str) -> str:
        """Sanitize name for Python identifier."""
        sanitized = name.lower().replace(' ', '_').replace('-', '_')
        sanitized = ''.join(c if c.isalnum() or c == '_' else '' for c in sanitized)
        return sanitized

    def _sanitize_class_name(self, name: str) -> str:
        """Sanitize name for Python class name."""
        words = name.replace('_', ' ').split()
        class_name = ''.join(word.capitalize() for word in words)
        if not class_name:
            class_name = "CustomWorkflow"
        if not class_name.endswith('Workflow'):
            class_name += 'Workflow'
        return class_name
