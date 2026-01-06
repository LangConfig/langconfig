# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Executable Workflow Exporter for LangConfig.

Exports user-created workflows as fully executable, standalone Python packages
that can be dropped into any repository and run immediately.

Uses LangChain v1.1 / LangGraph v1.x / DeepAgents v2.x APIs.
"""

import io
import logging
import zipfile
from typing import Any, Dict, Set

from .generators import (
    NodeGenerators,
    ToolGenerators,
    CustomToolGenerators,
    RoutingGenerators,
    TemplateGenerators,
    StreamlitAppGenerator,
    ApiServerGenerator,
    ConfigurableStreamlitGenerator,
    CONFIGURABLE_AVAILABLE,
)
from .generators.nodes_configurable import ConfigurableNodeGenerators

logger = logging.getLogger(__name__)


class ExecutableWorkflowExporter:
    """
    Exports workflows as executable Python packages.

    Generated package structure:
    workflow_{name}_{id}/
    ├── README.md
    ├── requirements.txt
    ├── .env.example
    ├── main.py
    ├── streamlit_app.py        # Optional Streamlit UI
    ├── api_server.py           # Optional FastAPI server
    ├── workflow/
    │   ├── __init__.py
    │   ├── graph.py
    │   ├── state.py
    │   ├── nodes.py
    │   └── routing.py
    ├── agents/
    │   ├── __init__.py
    │   └── factory.py
    ├── tools/
    │   ├── __init__.py
    │   ├── native.py
    │   └── custom.py
    └── config/
        └── settings.py
    """

    def __init__(
        self,
        workflow: Dict[str, Any],
        project_id: int,
        include_ui: bool = True,
        include_api: bool = True,
        export_mode: str = "standard"
    ):
        """
        Initialize the exporter.

        Args:
            workflow: Workflow data including configuration, blueprint, nodes, edges
            project_id: Project ID for fetching custom tools
            include_ui: Whether to include Streamlit UI (default: True)
            include_api: Whether to include FastAPI server (default: True)
            export_mode: Export mode - 'standard' (fixed config) or 'configurable' (runtime config UI)
        """
        self.workflow = workflow
        self.project_id = project_id
        self.include_ui = include_ui
        self.include_api = include_api
        self.export_mode = export_mode
        self.workflow_id = workflow.get("id", 0)
        self.workflow_name = workflow.get("name", "Exported Workflow")

        # Extract nodes and edges from configuration or blueprint
        config = workflow.get("configuration", {})
        blueprint = workflow.get("blueprint", {})

        self.nodes = config.get("nodes", []) or blueprint.get("nodes", [])
        self.edges = config.get("edges", []) or blueprint.get("edges", [])

        # Track what features are used for requirements
        self._used_models: Set[str] = set()
        self._used_native_tools: Set[str] = set()
        self._used_custom_tools: Set[str] = set()
        self._has_deepagents = False

        # Analyze workflow to detect features
        self._analyze_workflow()

    def _analyze_workflow(self) -> None:
        """Analyze workflow to detect used features."""
        for node in self.nodes:
            node_data = node.get("data", {})
            # Config can be in multiple places
            node_config_top = node.get("config", {})
            node_config_nested = node_data.get("config", {})
            node_config = {**node_config_nested, **node_config_top}

            # Detect model usage - check ALL locations
            model = (
                node_config_top.get("model") or
                node_data.get("model") or
                node_config_nested.get("model") or
                ""
            )
            if model:
                self._used_models.add(model)
                logger.info(f"Detected model: {model}")

            # Detect native tools
            native_tools = node_config.get("native_tools", [])
            self._used_native_tools.update(native_tools)

            # Detect custom tools
            custom_tools = node_config.get("custom_tools", [])
            self._used_custom_tools.update(custom_tools)

            # Detect DeepAgents
            if node_config.get("use_deepagents") or node_data.get("subagents"):
                self._has_deepagents = True

        logger.info(f"Workflow analysis: models={self._used_models}, native_tools={self._used_native_tools}")

    def _sanitize_name(self, name: str) -> str:
        """Sanitize name for filesystem and Python identifiers."""
        sanitized = name.lower().replace(" ", "_").replace("-", "_")
        sanitized = "".join(c if c.isalnum() or c == "_" else "" for c in sanitized)
        return sanitized or "workflow"

    async def export_to_zip(self) -> bytes:
        """
        Export workflow as a ZIP file containing all necessary files.

        Returns:
            ZIP file as bytes
        """
        logger.info(f"Exporting workflow {self.workflow_id}: {self.workflow_name}")
        logger.info(f"Workflow has {len(self.nodes)} nodes, {len(self.edges)} edges")

        # Debug: Log raw node structure to understand data format
        for i, node in enumerate(self.nodes[:3]):  # First 3 nodes
            logger.info(f"[EXPORT DEBUG] Node {i}: {node.get('id')}")
            logger.info(f"[EXPORT DEBUG]   Top-level keys: {list(node.keys())}")
            top_config = node.get("config", {})
            logger.info(f"[EXPORT DEBUG]   node.config: {top_config}")
            logger.info(f"[EXPORT DEBUG]   node.config.model: {top_config.get('model')}")
            logger.info(f"[EXPORT DEBUG]   node.config.system_prompt: {top_config.get('system_prompt', '')[:50]}...")

        # Create in-memory ZIP file
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Sanitize workflow name for folder
            safe_name = self._sanitize_name(self.workflow_name)
            base_path = f"workflow_{safe_name}_{self.workflow_id}"

            # Generate and add all files using generators
            files = {
                "README.md": TemplateGenerators.generate_readme(
                    self.workflow_name,
                    self.nodes,
                    self.edges,
                    self.include_ui,
                    self._sanitize_name,
                    self.include_api
                ),
                "requirements.txt": TemplateGenerators.generate_requirements(
                    self._used_models,
                    self._used_native_tools,
                    self._has_deepagents,
                    self.include_ui,
                    self.include_api
                ),
                ".env.example": TemplateGenerators.generate_env_example(
                    self._used_models,
                    self._used_custom_tools,
                    self.workflow_name,
                    self._sanitize_name
                ),
                "main.py": TemplateGenerators.generate_main(),
                "workflow/__init__.py": TemplateGenerators.generate_workflow_init(),
                "workflow/graph.py": TemplateGenerators.generate_graph_module(
                    self.nodes,
                    self.edges,
                    self._sanitize_name
                ),
                "workflow/state.py": TemplateGenerators.generate_state_module(),
                "workflow/nodes.py": (
                    ConfigurableNodeGenerators.generate_nodes_module(
                        self.nodes,
                        self._used_models,
                        self._sanitize_name
                    ) if self.export_mode == "configurable" else
                    NodeGenerators.generate_nodes_module(
                        self.nodes,
                        self._used_models,
                        self._sanitize_name
                    )
                ),
                "workflow/routing.py": RoutingGenerators.generate_routing_module(
                    self.nodes,
                    self._sanitize_name
                ),
                "agents/__init__.py": TemplateGenerators.generate_agents_init(),
                "agents/factory.py": TemplateGenerators.generate_agents_module(),
                "tools/__init__.py": ToolGenerators.generate_tools_init(),
                "tools/native.py": ToolGenerators.generate_native_tools_module(
                    self._used_native_tools
                ),
                "tools/custom.py": await CustomToolGenerators.generate_custom_tools_module(
                    self._used_custom_tools,
                    self._sanitize_name
                ),
                "config/__init__.py": "",
                "config/settings.py": TemplateGenerators.generate_settings_module(),
            }

            # Add Streamlit UI if enabled
            if self.include_ui:
                if self.export_mode == "configurable" and CONFIGURABLE_AVAILABLE:
                    files["streamlit_app.py"] = ConfigurableStreamlitGenerator.generate(
                        self.workflow_name,
                        self.nodes,
                        self.edges
                    )
                elif self.export_mode == "configurable":
                    # Fallback if configurable not available
                    logger.warning("ConfigurableStreamlitGenerator not available, using standard")
                    files["streamlit_app.py"] = StreamlitAppGenerator.generate_streamlit_app(
                        self.workflow_name,
                        self.nodes,
                        self.edges
                    )
                else:
                    files["streamlit_app.py"] = StreamlitAppGenerator.generate_streamlit_app(
                        self.workflow_name,
                        self.nodes,
                        self.edges
                    )

            # Add FastAPI server if enabled
            if self.include_api:
                files["api_server.py"] = ApiServerGenerator.generate_api_server(
                    self.workflow_name,
                    self.nodes,
                    self.edges
                )

            for filepath, content in files.items():
                zf.writestr(f"{base_path}/{filepath}", content)

        logger.info(f"Export complete: {len(files)} files generated")
        return zip_buffer.getvalue()
