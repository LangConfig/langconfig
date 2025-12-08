# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Workflow Config Service for LangConfig.

Handles export and import of .langconfig JSON files for sharing
workflows between LangConfig instances.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from config import settings
from models.custom_tool import CustomTool
from models.workflow import WorkflowProfile

logger = logging.getLogger(__name__)

# Current .langconfig format version
LANGCONFIG_VERSION = "1.0"


class WorkflowConfigService:
    """
    Service for exporting and importing .langconfig workflow configurations.

    The .langconfig format is a JSON interchange format that allows users
    to share complete workflow configurations between LangConfig instances.
    """

    def __init__(self, db: Session):
        """
        Initialize the service.

        Args:
            db: Database session
        """
        self.db = db

    async def export_workflow_config(
        self,
        workflow_id: int,
        include_custom_tools: bool = True,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Export a workflow as a .langconfig JSON configuration.

        Args:
            workflow_id: ID of the workflow to export
            include_custom_tools: Whether to include custom tool definitions
            include_metadata: Whether to include export metadata

        Returns:
            Dictionary containing the complete workflow configuration

        Raises:
            ValueError: If workflow not found
        """
        # Fetch workflow
        workflow = self.db.query(WorkflowProfile).filter(
            WorkflowProfile.id == workflow_id
        ).first()

        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")

        logger.info(f"Exporting workflow {workflow_id}: {workflow.name}")

        # Build configuration
        config = {
            "version": LANGCONFIG_VERSION,
            "langconfig_version": getattr(settings, "VERSION", "1.0.0"),
            "export_type": "workflow",
        }

        if include_metadata:
            config["metadata"] = {
                "exported_at": datetime.utcnow().isoformat(),
                "source_workflow_id": workflow.id,
            }

        # Core workflow data
        config["workflow"] = {
            "name": workflow.name,
            "description": workflow.description or "",
            "strategy_type": workflow.strategy_type,
            "configuration": workflow.configuration or {},
            "blueprint": workflow.blueprint or {},
        }

        # Extract custom tools if requested
        if include_custom_tools:
            custom_tools = self._extract_custom_tools(workflow)
            if custom_tools:
                config["custom_tools"] = custom_tools

        # Extract DeepAgent configurations if present
        deepagent_configs = self._extract_deepagent_configs(workflow)
        if deepagent_configs:
            config["deepagents"] = deepagent_configs

        logger.info(
            f"Export complete: {len(config.get('custom_tools', []))} custom tools, "
            f"{len(config.get('deepagents', []))} deepagent configs"
        )

        return config

    def _extract_custom_tools(self, workflow: WorkflowProfile) -> List[Dict[str, Any]]:
        """Extract custom tool definitions used in the workflow."""
        custom_tools = []
        custom_tool_ids = set()

        # Scan nodes for custom tools
        config = workflow.configuration or {}
        nodes = config.get("nodes", [])

        for node in nodes:
            node_data = node.get("data", {})
            node_config = node_data.get("config", {})
            tool_ids = node_config.get("custom_tools", [])
            custom_tool_ids.update(tool_ids)

        # Fetch tool definitions from database
        if custom_tool_ids:
            tools = self.db.query(CustomTool).filter(
                CustomTool.tool_id.in_(custom_tool_ids)
            ).all()

            for tool in tools:
                custom_tools.append({
                    "tool_id": tool.tool_id,
                    "name": tool.name,
                    "description": tool.description,
                    "tool_type": tool.tool_type.value if hasattr(tool.tool_type, "value") else str(tool.tool_type),
                    "template_type": tool.template_type.value if tool.template_type and hasattr(tool.template_type, "value") else None,
                    "input_schema": tool.input_schema,
                    "output_format": tool.output_format,
                    "implementation_config": tool.implementation_config,
                })

        return custom_tools

    def _extract_deepagent_configs(self, workflow: WorkflowProfile) -> List[Dict[str, Any]]:
        """Extract DeepAgent configurations from workflow nodes."""
        deepagent_configs = []

        config = workflow.configuration or {}
        nodes = config.get("nodes", [])

        for node in nodes:
            node_data = node.get("data", {})
            node_config = node_data.get("config", {})

            if node_config.get("use_deepagents") or node_data.get("subagents"):
                deepagent_configs.append({
                    "node_id": node.get("id"),
                    "model": node_config.get("model"),
                    "system_prompt": node_config.get("system_prompt"),
                    "subagents": node_data.get("subagents", []),
                    "middleware": node_config.get("middleware", []),
                })

        return deepagent_configs

    async def import_workflow_config(
        self,
        config: Dict[str, Any],
        project_id: int,
        owner_id: int,
        name_override: Optional[str] = None,
        create_custom_tools: bool = True
    ) -> Dict[str, Any]:
        """
        Import a .langconfig configuration to create a new workflow.

        Args:
            config: The .langconfig configuration dictionary
            project_id: Project to import the workflow into
            owner_id: Owner user ID
            name_override: Optional name to use instead of the original
            create_custom_tools: Whether to create custom tools from the config

        Returns:
            Dictionary with import results including new workflow ID

        Raises:
            ValueError: If config is invalid or incompatible
        """
        # Validate config
        validation_result = self._validate_config(config)
        if not validation_result["valid"]:
            raise ValueError(f"Invalid config: {validation_result['errors']}")

        logger.info(f"Importing workflow config version {config.get('version')}")

        # Create custom tools first if included
        created_tools = []
        tool_id_mapping = {}  # old_id -> new_id

        if create_custom_tools and "custom_tools" in config:
            for tool_config in config["custom_tools"]:
                try:
                    new_tool = await self._create_custom_tool(tool_config, project_id)
                    created_tools.append(new_tool.tool_id)
                    # Map old ID to new ID (in case we generate new IDs)
                    tool_id_mapping[tool_config["tool_id"]] = new_tool.tool_id
                except Exception as e:
                    logger.warning(f"Failed to create custom tool: {e}")

        # Get workflow data
        workflow_data = config.get("workflow", {})

        # Remap custom tool IDs in nodes if needed
        if tool_id_mapping:
            workflow_data = self._remap_tool_ids(workflow_data, tool_id_mapping)

        # Create workflow
        workflow_name = name_override or workflow_data.get("name", "Imported Workflow")

        # Check for name conflicts
        existing = self.db.query(WorkflowProfile).filter(
            WorkflowProfile.name == workflow_name,
            WorkflowProfile.project_id == project_id
        ).first()

        if existing:
            # Append timestamp to make unique
            workflow_name = f"{workflow_name} (imported {datetime.utcnow().strftime('%Y%m%d_%H%M%S')})"

        new_workflow = WorkflowProfile(
            name=workflow_name,
            description=workflow_data.get("description", ""),
            strategy_type=workflow_data.get("strategy_type"),
            configuration=workflow_data.get("configuration", {}),
            blueprint=workflow_data.get("blueprint", {}),
            project_id=project_id,
            # owner_id=owner_id,  # Uncomment if your model has owner_id
        )

        self.db.add(new_workflow)
        self.db.commit()
        self.db.refresh(new_workflow)

        logger.info(f"Imported workflow: {new_workflow.id} - {new_workflow.name}")

        return {
            "workflow_id": new_workflow.id,
            "workflow_name": new_workflow.name,
            "status": "imported",
            "created_tools": created_tools,
            "tool_mapping": tool_id_mapping,
        }

    def _validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a .langconfig configuration.

        Args:
            config: Configuration to validate

        Returns:
            Dictionary with validation results
        """
        errors = []
        warnings = []

        # Check version
        version = config.get("version")
        if not version:
            errors.append("Missing version field")
        elif version != LANGCONFIG_VERSION:
            warnings.append(f"Config version {version} may not be fully compatible with current version {LANGCONFIG_VERSION}")

        # Check required fields
        if "workflow" not in config:
            errors.append("Missing workflow field")
        else:
            workflow = config["workflow"]
            if not workflow.get("name"):
                errors.append("Workflow missing name")
            if not workflow.get("configuration") and not workflow.get("blueprint"):
                errors.append("Workflow missing configuration or blueprint")

        # Validate custom tools if present
        if "custom_tools" in config:
            for i, tool in enumerate(config["custom_tools"]):
                if not tool.get("tool_id"):
                    errors.append(f"Custom tool {i} missing tool_id")
                if not tool.get("name"):
                    errors.append(f"Custom tool {i} missing name")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    async def _create_custom_tool(
        self,
        tool_config: Dict[str, Any],
        project_id: int
    ) -> CustomTool:
        """Create a custom tool from config."""
        from models.custom_tool import ToolType, TemplateType

        # Check if tool already exists
        existing = self.db.query(CustomTool).filter(
            CustomTool.tool_id == tool_config["tool_id"]
        ).first()

        if existing:
            logger.info(f"Custom tool {tool_config['tool_id']} already exists, skipping")
            return existing

        # Parse enums
        tool_type_str = tool_config.get("tool_type", "custom")
        try:
            tool_type = ToolType(tool_type_str)
        except (ValueError, KeyError):
            tool_type = ToolType.CUSTOM

        template_type = None
        if tool_config.get("template_type"):
            try:
                template_type = TemplateType(tool_config["template_type"])
            except (ValueError, KeyError):
                pass

        # Create tool
        new_tool = CustomTool(
            tool_id=tool_config["tool_id"],
            name=tool_config["name"],
            description=tool_config.get("description", ""),
            tool_type=tool_type,
            template_type=template_type,
            input_schema=tool_config.get("input_schema"),
            output_format=tool_config.get("output_format"),
            implementation_config=tool_config.get("implementation_config", {}),
            project_id=project_id,
        )

        self.db.add(new_tool)
        self.db.commit()
        self.db.refresh(new_tool)

        logger.info(f"Created custom tool: {new_tool.tool_id}")
        return new_tool

    def _remap_tool_ids(
        self,
        workflow_data: Dict[str, Any],
        tool_id_mapping: Dict[str, str]
    ) -> Dict[str, Any]:
        """Remap tool IDs in workflow configuration."""
        if not tool_id_mapping:
            return workflow_data

        # Deep copy to avoid modifying original
        import copy
        data = copy.deepcopy(workflow_data)

        # Remap in configuration
        config = data.get("configuration", {})
        nodes = config.get("nodes", [])

        for node in nodes:
            node_data = node.get("data", {})
            node_config = node_data.get("config", {})

            if "custom_tools" in node_config:
                node_config["custom_tools"] = [
                    tool_id_mapping.get(tid, tid)
                    for tid in node_config["custom_tools"]
                ]

        # Also check blueprint
        blueprint = data.get("blueprint", {})
        bp_nodes = blueprint.get("nodes", [])

        for node in bp_nodes:
            node_data = node.get("data", {})
            node_config = node_data.get("config", {})

            if "custom_tools" in node_config:
                node_config["custom_tools"] = [
                    tool_id_mapping.get(tid, tid)
                    for tid in node_config["custom_tools"]
                ]

        return data

    def get_config_info(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get information about a .langconfig file without importing.

        Args:
            config: Configuration to analyze

        Returns:
            Summary information about the config
        """
        validation = self._validate_config(config)

        workflow = config.get("workflow", {})
        custom_tools = config.get("custom_tools", [])
        deepagents = config.get("deepagents", [])

        nodes = []
        config_data = workflow.get("configuration", {})
        blueprint = workflow.get("blueprint", {})
        nodes = config_data.get("nodes", []) or blueprint.get("nodes", [])

        return {
            "version": config.get("version"),
            "langconfig_version": config.get("langconfig_version"),
            "valid": validation["valid"],
            "errors": validation["errors"],
            "warnings": validation["warnings"],
            "workflow": {
                "name": workflow.get("name"),
                "description": workflow.get("description"),
                "node_count": len(nodes),
                "edge_count": len(config_data.get("edges", []) or blueprint.get("edges", [])),
            },
            "custom_tools_count": len(custom_tools),
            "deepagents_count": len(deepagents),
            "metadata": config.get("metadata", {}),
        }
