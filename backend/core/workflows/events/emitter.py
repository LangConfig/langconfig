# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Execution Event Emission for Live Workflow Monitoring.

Enhanced with LangChain Callbacks for comprehensive agent observability.

This module provides event emission capabilities for the dynamic executor,
enabling real-time visualization of workflow execution in the frontend.

Events are published to in-memory event bus and consumed by SSE endpoints
for streaming to connected clients.

Key Enhancements:
- ExecutionEventCallbackHandler for LangChain/LangGraph integration
- Tool usage tracking (on_tool_start/end/error)
- Agent thought process capture (on_agent_action)
- Node lifecycle monitoring (on_chain_start/end/error)
- Sensitive data sanitization for security
- Token usage tracking
- Error capture and reporting
"""

import asyncio
import logging
import re
from typing import Optional, Dict, Any, List, Sequence, Union
from datetime import datetime
from uuid import UUID

# LangChain callback imports
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult
from langchain_core.agents import AgentAction, AgentFinish

logger = logging.getLogger(__name__)


# =============================================================================
# Legacy Event Emission Functions (Backwards Compatibility)
# =============================================================================

async def emit_node_start_event(
    project_id: Optional[int],
    task_id: Optional[int],
    node_id: str,
    node_type: str
):
    """
    Emit NODE_START event when a workflow node begins execution.

    Args:
        project_id: Project ID (for channel routing)
        task_id: Task ID
        node_id: Node identifier from blueprint
        node_type: Type of node (strategy method or workflow_node)
    """
    await _emit_node_event(
        event_type='NODE_START',
        project_id=project_id,
        task_id=task_id,
        node_id=node_id,
        node_type=node_type,
        success=True
    )


async def emit_node_complete_event(
    project_id: Optional[int],
    task_id: Optional[int],
    node_id: str,
    node_type: str,
    success: bool = True,
    error: Optional[str] = None,
    result_keys: Optional[list] = None
):
    """
    Emit NODE_COMPLETE event when a workflow node finishes execution.

    Args:
        project_id: Project ID (for channel routing)
        task_id: Task ID
        node_id: Node identifier from blueprint
        node_type: Type of node (strategy method or workflow_node)
        success: Whether node execution succeeded
        error: Error message if failed
        result_keys: Keys of state updates returned
    """
    await _emit_node_event(
        event_type='NODE_COMPLETE',
        project_id=project_id,
        task_id=task_id,
        node_id=node_id,
        node_type=node_type,
        success=success,
        error=error,
        result_keys=result_keys
    )


async def emit_checkpoint_event(
    project_id: Optional[int],
    task_id: Optional[int],
    node_id: str,
    checkpoint_data: Optional[Dict[str, Any]] = None
):
    """
    Emit CHECKPOINT event when a workflow checkpoint is reached.

    Args:
        project_id: Project ID (for channel routing)
        task_id: Task ID
        node_id: Node identifier
        checkpoint_data: Metadata about the checkpoint
    """
    if not project_id:
        logger.debug(f"Skipping checkpoint event emission: no project_id for node {node_id}")
        return

    try:
        from services.event_bus import get_event_bus
        event_bus = get_event_bus()

        event_payload = {
            "type": "CHECKPOINT_EVENT",
            "project_id": project_id,
            "task_id": task_id,
            "node_id": node_id,
            "checkpoint_data": checkpoint_data or {},
            "timestamp": datetime.utcnow().isoformat(),
        }

        channel = f"project_{project_id}"
        await event_bus.publish(channel, event_payload)
        logger.debug(f"Published CHECKPOINT event for node {node_id}")
    except Exception as e:
        logger.error(f"Failed to emit checkpoint event: {e}", exc_info=True)


async def emit_handoff_event(
    project_id: Optional[int],
    task_id: Optional[int],
    source_node: str,
    target_node: Optional[str],
    handoff_summary: Optional[Dict[str, Any]] = None
):
    """
    Emit HANDOFF event when control passes between workflow nodes.

    Args:
        project_id: Project ID (for channel routing)
        task_id: Task ID
        source_node: Node that completed and is handing off
        target_node: Node that will execute next (if known)
        handoff_summary: Summary of what was passed (actions, decisions, etc.)
    """
    if not project_id:
        logger.debug(f"Skipping handoff event emission: no project_id for handoff")
        return

    try:
        from services.event_bus import get_event_bus
        event_bus = get_event_bus()

        event_payload = {
            "type": "HANDOFF_EVENT",
            "project_id": project_id,
            "task_id": task_id,
            "source_node": source_node,
            "target_node": target_node,
            "handoff_summary": handoff_summary or {},
            "timestamp": datetime.utcnow().isoformat(),
        }

        channel = f"project_{project_id}"
        await event_bus.publish(channel, event_payload)
        logger.debug(f"Published HANDOFF event from {source_node} to {target_node}")
    except Exception as e:
        logger.error(f"Failed to emit handoff event: {e}", exc_info=True)


async def _emit_node_event(
    event_type: str,
    project_id: Optional[int],
    task_id: Optional[int],
    node_id: str,
    node_type: str,
    success: bool = True,
    error: Optional[str] = None,
    result_keys: Optional[list] = None
):
    """
    Internal function to emit workflow node execution event.

    This function publishes events to in-memory event bus that are consumed
    by the SSE endpoint and streamed to frontend clients for
    real-time workflow visualization.

    Args:
        event_type: 'NODE_START' or 'NODE_COMPLETE'
        project_id: Project ID (for channel routing)
        task_id: Task ID
        node_id: Node identifier from blueprint
        node_type: Type of node (strategy method or workflow_node)
        success: Whether node execution succeeded (for COMPLETE events)
        error: Error message if failed (for COMPLETE events)
        result_keys: Keys of state updates returned (for COMPLETE events)
    """
    if not project_id:
        logger.debug(f"Skipping event emission: no project_id for node {node_id}")
        return

    try:
        # Import here to avoid circular dependencies
        from services.event_bus import get_event_bus

        # Get event bus
        event_bus = get_event_bus()

        # Build event payload
        event_payload = {
            "type": "NODE_EXECUTION_EVENT",
            "event_type": event_type,
            "project_id": project_id,
            "task_id": task_id,
            "node_id": node_id,
            "node_type": node_type,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Add event-specific fields
        if event_type == 'NODE_COMPLETE':
            event_payload.update({
                "success": success,
                "error": error,
                "result_keys": result_keys or []
            })

        # Publish to project-specific execution channel
        channel = f"project:{project_id}:execution"
        await event_bus.publish(channel, event_payload)

        logger.debug(
            f"Emitted {event_type} event: node={node_id}, "
            f"project={project_id}, task={task_id}"
        )

    except Exception as e:
        # Don't let event emission failures break workflow execution
        logger.warning(
            f"Failed to emit node event for {node_id}: {e}",
            exc_info=False
        )


# =============================================================================
# LangChain Callback Handler for Agent Observability
# =============================================================================

class ExecutionEventCallbackHandler(AsyncCallbackHandler):
    """
    LangChain AsyncCallbackHandler for comprehensive agent execution monitoring.

    This callback handler integrates with LangChain/LangGraph workflows to emit
    real-time events for:
    - Node/chain lifecycle (start, end, error)
    - Tool invocations (start, end, error)
    - Agent reasoning (thoughts, actions, observations)
    - LLM token usage
    - Error tracking

    Events are published to event bus for consumption by SSE endpoints.

    Usage:
        callback_handler = ExecutionEventCallbackHandler(
            project_id=123,
            task_id=456,
            workflow_id=789  # Required for SSE channel routing
        )

        # Pass to LangGraph workflow invocation
        result = await agent_graph.ainvoke(
            {"messages": [...]},
            config={"callbacks": [callback_handler]}
        )
    """

    def __init__(
        self,
        project_id: int,
        task_id: int,
        workflow_id: Optional[int] = None,
        user_id: Optional[str] = None,
        enable_sanitization: bool = True,
        node_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
        save_to_db: bool = True
    ):
        """
        Initialize the callback handler.

        Args:
            project_id: Project ID for event attribution
            task_id: Task ID for event attribution
            workflow_id: Workflow ID for channel routing (required for SSE streaming)
            user_id: Optional user ID for audit trails
            enable_sanitization: Whether to sanitize sensitive data (recommended)
            node_metadata: Map of node_id to {label, agent_type, config} for proper event labeling
            save_to_db: Whether to persist events to database for historical viewing
        """
        super().__init__()
        self.project_id = project_id
        self.task_id = task_id
        self.workflow_id = workflow_id
        self.user_id = user_id
        self.node_metadata = node_metadata or {}
        self.enable_sanitization = enable_sanitization
        self.save_to_db = save_to_db

        # Track execution metrics
        self.tool_call_count = 0
        self.llm_call_count = 0
        self.total_tokens = 0
        self.error_count = 0

        # Track current executing node for agent_action event labeling
        self.current_node_info = {}  # {run_id: {agent_label, node_name, agent_type}}

        # Track current executing tools for on_tool_end events
        self.current_tool_info = {}  # {run_id: {tool_name, agent_label}}

        # Track active subagent runs for nested visualization
        # Maps run_id -> {subagent_name, parent_agent_label, parent_run_id}
        self.active_subagents = {}

        # Track pending database persist tasks to ensure completion on workflow end
        self._pending_persist_tasks: list = []

        logger.info(
            f"ExecutionEventCallbackHandler initialized "
            f"(project={project_id}, task={task_id}, workflow={workflow_id}, save_to_db={save_to_db})"
        )

        if save_to_db:
            logger.info("📝 Database persistence ENABLED - execution events will be saved for historical viewing")
        else:
            logger.warning("⚠️  Database persistence DISABLED - execution events will NOT be saved")

    # =========================================================================
    # Chain/Node Lifecycle Hooks
    # =========================================================================

    async def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> None:
        """
        Called when a chain/node starts execution.

        Maps to NODE_START events for workflow visualization.
        """
        # Handle case where serialized might be None
        if not serialized:
            serialized = {}

        # Try to extract node_id from metadata or tags to look up in node_metadata
        node_id = None
        if metadata:
            node_id = metadata.get("node_id")

        # Try tags if no metadata
        if not node_id and tags:
            for tag in tags:
                if isinstance(tag, str) and (tag.startswith("node-") or tag in self.node_metadata):
                    node_id = tag
                    break

        # Look up node info from metadata map (passed from simple_executor)
        node_info = self.node_metadata.get(node_id, {}) if node_id else {}

        # Extract agent info from node_metadata
        agent_label = node_info.get("label")
        agent_type = node_info.get("agent_type")

        # ENHANCED DEBUG: Log full lookup chain
        logger.info(
            f"[CHAIN START DEBUG] run_id={str(run_id)[:8]}, parent_run_id={str(parent_run_id)[:8] if parent_run_id else None}, "
            f"node_id={node_id}, agent_label={agent_label}, "
            f"metadata={metadata}, tags={tags}, "
            f"available_nodes={list(self.node_metadata.keys())}"
        )

        # Build node name with priority: metadata label > metadata agent_type > serialized name > fallback
        node_name = None

        # 1. Try node metadata first (most reliable)
        if agent_label:
            node_name = agent_label
        elif agent_type:
            node_name = agent_type

        # 2. Try serialized name
        elif serialized.get("name"):
            node_name = serialized.get("name")

        # 3. Try kwargs name
        elif kwargs.get("name"):
            node_name = kwargs.get("name")

        # 4. Try to extract from serialized id/repr
        elif serialized.get("id"):
            node_id_from_ser = serialized.get("id")
            if isinstance(node_id_from_ser, list) and len(node_id_from_ser) > 0:
                node_name = str(node_id_from_ser[-1])
            else:
                node_name = str(node_id_from_ser)

        # 5. Try tags (but filter out langsmith tags)
        if not node_name or node_name == "unknown":
            if tags:
                for tag in tags:
                    if isinstance(tag, str) and not tag.startswith("langsmith:") and not tag.startswith("seq:") and not tag.startswith("node-"):
                        node_name = tag
                        break

        # 6. Final fallback
        if not node_name or node_name == "unknown":
            if serialized.get("graph", {}).get("__class__"):
                node_name = serialized["graph"]["__class__"].get("__name__", "Workflow Step")
            else:
                node_name = "Workflow Step"

        # Node type from metadata or serialized
        node_type = agent_type or serialized.get("graph", {}).get("__class__", {}).get("__name__", "agent")

        # Extract input data for more context
        input_preview = None
        if kwargs.get("inputs"):
            inputs = kwargs["inputs"]
            if isinstance(inputs, dict):
                # Try to get meaningful preview
                if "messages" in inputs and inputs["messages"]:
                    last_msg = inputs["messages"][-1] if isinstance(inputs["messages"], list) else inputs["messages"]
                    if hasattr(last_msg, 'content'):
                        input_preview = last_msg.content[:100] + "..." if len(last_msg.content) > 100 else last_msg.content
                elif "query" in inputs:
                    input_preview = str(inputs["query"])[:100]
                elif "input" in inputs:
                    input_preview = str(inputs["input"])[:100]

        logger.debug(f"[CHAIN START] {node_name} (type={node_type}, input_preview={input_preview})")

        # Store current node info for agent_action events (including node_id for tool grouping)
        self.current_node_info[run_id] = {
            "agent_label": agent_label,
            "node_name": node_name,
            "agent_type": agent_type,
            "node_id": node_id  # Needed to group tools with parent agent in frontend
        }

        # SIMPLIFIED EVENT EMISSION:
        # Only emit agent_label (user-friendly name that matches canvas nodes)
        # Removed node_name, node_type, agent_type to prevent duplication/confusion
        # Frontend uses agent_label for matching (see useNodeExecutionStatus.ts:108)
        await self._emit_event(
            event_type="CHAIN_START",
            data={
                "agent_label": agent_label or node_name,  # Primary field for node matching
                "run_id": str(run_id),
                "parent_run_id": str(parent_run_id) if parent_run_id else None,
                "tags": tags or [],
                "metadata": metadata or {},
                "input_preview": input_preview
            }
        )

    async def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any
    ) -> None:
        """
        Called when a chain/node completes execution.

        Maps to NODE_COMPLETE events for workflow visualization.
        """
        logger.debug(f"[CHAIN END] run_id={run_id}")

        # Sanitize outputs if enabled
        sanitized_outputs = self._sanitize_arguments(outputs) if self.enable_sanitization else outputs

        await self._emit_event(
            event_type="CHAIN_END",
            data={
                "run_id": str(run_id),
                "parent_run_id": str(parent_run_id) if parent_run_id else None,
                "output_keys": list(sanitized_outputs.keys()) if isinstance(sanitized_outputs, dict) else [],
                "success": True
            }
        )

        # Clean up node tracking to prevent memory leaks
        if run_id in self.current_node_info:
            del self.current_node_info[run_id]

    async def on_chain_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any
    ) -> None:
        """
        Called when a chain/node encounters an error.

        Maps to NODE_COMPLETE events with error details.
        """
        self.error_count += 1
        error_message = str(error)
        error_type = type(error).__name__

        logger.error(f"[CHAIN ERROR] {error_type}: {error_message} (run_id={run_id})")

        await self._emit_event(
            event_type="CHAIN_ERROR",
            data={
                "run_id": str(run_id),
                "parent_run_id": str(parent_run_id) if parent_run_id else None,
                "error_type": error_type,
                "error": error_message,  # Changed from 'error_message' to 'error' for frontend compatibility
                "success": False
            }
        )

        # Clean up node tracking to prevent memory leaks
        if run_id in self.current_node_info:
            del self.current_node_info[run_id]

    # =========================================================================
    # Tool Invocation Hooks
    # =========================================================================

    async def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        inputs: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> None:
        """
        Called when a tool starts execution.

        Tracks tool usage for observability and debugging.
        """
        self.tool_call_count += 1
        tool_name = serialized.get("name", "unknown_tool")

        logger.debug(f"[TOOL START] {tool_name} (run_id={run_id})")

        # Look up agent_label and node_id from parent_run_id so frontend can map tool to correct node
        node_info = self.current_node_info.get(parent_run_id, {})
        agent_label = node_info.get("agent_label")
        node_id = node_info.get("node_id")  # Frontend needs this to group tool with agent

        # FALLBACK: If no agent_label found, try to find ANY tracked node (for single-agent workflows)
        # This handles cases where parent_run_id chain hierarchy doesn't match what we stored
        if not agent_label and self.current_node_info:
            # Use the most recently added node info as fallback
            fallback_info = list(self.current_node_info.values())[-1] if self.current_node_info else {}
            if fallback_info:
                agent_label = fallback_info.get("agent_label")
                node_id = fallback_info.get("node_id")
                logger.debug(f"[TOOL START] Using fallback agent_label: {agent_label}")

        # DEBUG: Log lookup to diagnose why agent_label is missing
        logger.debug(
            f"[TOOL START] Agent label lookup: tool={tool_name}, "
            f"parent_run_id={parent_run_id}, found_node_info={bool(node_info)}, "
            f"agent_label={agent_label}, node_id={node_id}, tracked_nodes={list(self.current_node_info.keys())}"
        )

        # Store tool info for on_tool_end to use
        self.current_tool_info[run_id] = {
            "tool_name": tool_name,
            "agent_label": agent_label,
            "node_id": node_id  # Pass through to on_tool_end
        }

        # SUBAGENT DETECTION: Check for known subagent invocation tool patterns
        # DeepAgents uses 'task' tool, but other patterns might include:
        # - delegate, handoff, invoke_agent, call_agent, run_agent
        subagent_tool_patterns = ['task', 'delegate', 'handoff', 'invoke_agent', 'call_agent', 'run_agent']
        is_subagent_tool = tool_name.lower() in subagent_tool_patterns or 'subagent' in tool_name.lower()

        # DEBUG: Log all tool calls to help identify subagent patterns
        logger.info(f"[TOOL DEBUG] tool_name={tool_name}, inputs_keys={list(inputs.keys()) if inputs else 'None'}, is_subagent={is_subagent_tool}")

        if is_subagent_tool:
            subagent_name = None
            task_description = None

            if inputs:
                # First try explicit name fields
                subagent_name = (
                    inputs.get('name') or
                    inputs.get('agent') or
                    inputs.get('subagent') or
                    inputs.get('agent_name')
                )

                # Get task description for generating a better name
                task_description = inputs.get('description') or inputs.get('task') or inputs.get('prompt')

                # If no explicit name, try to generate one from description
                if not subagent_name and task_description:
                    # Extract a meaningful task name from the first 50 chars of description
                    desc_preview = task_description[:50].strip()
                    # Find first sentence or meaningful phrase
                    for delim in ['.', ':', '\n', ' - ']:
                        if delim in desc_preview:
                            desc_preview = desc_preview.split(delim)[0].strip()
                            break

                    # Get subagent type for context
                    subagent_type = inputs.get('subagent_type', 'task')

                    # Create descriptive name: "Research: AMD report" instead of "general-purpose"
                    if desc_preview:
                        # Capitalize and shorten the description preview
                        short_desc = desc_preview[:30] + ('...' if len(desc_preview) > 30 else '')
                        subagent_name = f"{subagent_type.title()}: {short_desc}"
                    else:
                        subagent_name = subagent_type.replace('-', ' ').title()

                # Final fallback to subagent_type
                if not subagent_name:
                    subagent_name = inputs.get('subagent_type', 'Subagent').replace('-', ' ').title()

            if not subagent_name and input_str:
                # Try to extract from input string if structured
                import json
                try:
                    parsed = json.loads(input_str)
                    subagent_name = (
                        parsed.get('name') or
                        parsed.get('agent') or
                        parsed.get('agent_name') or
                        parsed.get('subagent_type', 'Subagent').replace('-', ' ').title()
                    )
                except:
                    pass

            # Fallback: use tool name if no subagent name found
            if not subagent_name:
                subagent_name = tool_name.replace('_', ' ').title()

            # Track this as an active subagent run
            self.active_subagents[run_id] = {
                "subagent_name": subagent_name,
                "parent_agent_label": agent_label,
                "parent_run_id": str(parent_run_id) if parent_run_id else None,
                "task_description": task_description  # Store for reference
            }

            # Emit dedicated SUBAGENT_START event for frontend nested panels
            # Use task_description for human-readable input, not raw dict string
            await self._emit_event(
                event_type="SUBAGENT_START",
                data={
                    "subagent_name": subagent_name,
                    "subagent_run_id": str(run_id),
                    "parent_agent_label": agent_label,
                    "parent_run_id": str(parent_run_id) if parent_run_id else None,
                    "input_preview": task_description if task_description else (input_str[:500] if input_str else "")
                }
            )
            logger.info(f"[SUBAGENT START] {subagent_name} invoked by {agent_label}")
            # IMPORTANT: Return early - don't emit TOOL_START for subagent tools
            # This prevents duplicate events (SUBAGENT_START + TOOL_START)
            return

        # Sanitize tool inputs
        sanitized_inputs = self._sanitize_arguments(inputs or {}) if self.enable_sanitization else inputs

        # Get subagent context for tools used within subagent execution
        subagent_context = self._get_subagent_context_for_run(run_id, parent_run_id)

        await self._emit_event(
            event_type="TOOL_START",
            data={
                "tool_name": tool_name,
                "run_id": str(run_id),
                "parent_run_id": str(parent_run_id) if parent_run_id else None,
                "input_preview": input_str[:200] if input_str else "",  # Truncate for brevity
                "inputs": sanitized_inputs,
                "tags": tags or [],
                "tool_call_number": self.tool_call_count,
                "agent_label": agent_label,  # User-friendly name
                "node_id": node_id,  # Frontend uses this to group tool with agent in same bubble
                # SUBAGENT FIELDS: Enable frontend to route to SubagentPanel
                "subagent_run_id": subagent_context.get("subagent_run_id") if subagent_context else None,
                "subagent_name": subagent_context.get("subagent_name") if subagent_context else None,
            }
        )

    async def on_tool_end(
        self,
        output: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any
    ) -> None:
        """
        Called when a tool completes execution.

        Captures tool results for agent observation tracking.
        """
        logger.debug(f"[TOOL END] run_id={run_id}")

        # Look up tool info from on_tool_start (includes tool_name, agent_label, and node_id)
        tool_info = self.current_tool_info.get(run_id, {})
        tool_name = tool_info.get("tool_name", "unknown")
        agent_label = tool_info.get("agent_label")
        node_id = tool_info.get("node_id")  # For grouping with parent agent

        # Handle case where output might not be a string
        try:
            if isinstance(output, str):
                full_output = output
                # Increase preview limit for better visibility
                output_preview = output[:2000] if output else ""
            else:
                # Convert to string if it's not already
                full_output = str(output) if output else ""
                output_preview = full_output[:2000]
        except Exception as e:
            logger.warning(f"Error processing tool output: {e}")
            output_preview = "[Output could not be processed]"
            full_output = output_preview

        # For write_file tool, include the full output (it contains the written content)
        # Supports both new standard naming (write_file) and legacy aliases (file_write)
        include_full_output = tool_name in ['write_file', 'file_write', 'task', 'delegate']

        # SUBAGENT COMPLETION: If this was a subagent (task tool), emit ONLY SUBAGENT_END
        # This mirrors the early return in on_tool_start - we don't emit both TOOL_END and SUBAGENT_END
        if run_id in self.active_subagents:
            subagent_info = self.active_subagents[run_id]
            await self._emit_event(
                event_type="SUBAGENT_END",
                data={
                    "subagent_name": subagent_info["subagent_name"],
                    "subagent_run_id": str(run_id),
                    "parent_agent_label": subagent_info["parent_agent_label"],
                    "parent_run_id": subagent_info["parent_run_id"],
                    "output_preview": output_preview,
                    "full_output": full_output,  # Full output for complete display
                    "success": True
                }
            )
            logger.info(f"[SUBAGENT END] {subagent_info['subagent_name']} completed")
            del self.active_subagents[run_id]
            # Clean up tool tracking and return early - don't emit TOOL_END
            if run_id in self.current_tool_info:
                del self.current_tool_info[run_id]
            return

        # Get subagent context for tools used within subagent execution
        subagent_context = self._get_subagent_context_for_run(run_id, parent_run_id)

        await self._emit_event(
            event_type="TOOL_END",
            data={
                "tool_name": tool_name,  # Include tool name so frontend knows which tool completed
                "run_id": str(run_id),
                "parent_run_id": str(parent_run_id) if parent_run_id else None,
                "output_preview": output_preview,
                "full_output": full_output if include_full_output else None,
                "success": True,
                "agent_label": agent_label,  # User-friendly name
                "node_id": node_id,  # Maps tool to correct node for grouping
                # SUBAGENT FIELDS: Enable frontend to route to SubagentPanel
                "subagent_run_id": subagent_context.get("subagent_run_id") if subagent_context else None,
                "subagent_name": subagent_context.get("subagent_name") if subagent_context else None,
            }
        )

        # Clean up tool tracking to prevent memory leaks
        if run_id in self.current_tool_info:
            del self.current_tool_info[run_id]

    async def on_tool_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any
    ) -> None:
        """
        Called when a tool encounters an error.

        Critical for debugging tool integration issues.
        """
        self.error_count += 1
        error_message = str(error)
        error_type = type(error).__name__

        # Enhanced error messaging for common tool validation errors
        # This helps the LLM understand what went wrong and how to fix it
        # Support both new (write_file) and legacy (file_write) tool names
        if error_type == "ValidationError" and ("write_file" in error_message or "file_write" in error_message):
            if "content" in error_message and "Field required" in error_message:
                error_message = (
                    "write_file tool validation error: You must provide BOTH file_path AND content parameters. "
                    "You called write_file with only file_path but forgot to include the content parameter. "
                    "Please call write_file again with BOTH parameters: "
                    "write_file(file_path='...', content='your full file content here'). "
                    "Wait until you have the complete content ready before calling write_file."
                )

        logger.error(f"[TOOL ERROR] {error_type}: {error_message} (run_id={run_id})")

        # Check if this was a subagent tool - emit SUBAGENT_ERROR instead of TOOL_ERROR
        if run_id in self.active_subagents:
            subagent_info = self.active_subagents[run_id]
            await self._emit_event(
                event_type="SUBAGENT_ERROR",
                data={
                    "subagent_name": subagent_info["subagent_name"],
                    "subagent_run_id": str(run_id),
                    "parent_agent_label": subagent_info["parent_agent_label"],
                    "parent_run_id": subagent_info["parent_run_id"],
                    "error_type": error_type,
                    "error": error_message,
                    "success": False
                }
            )
            logger.error(f"[SUBAGENT ERROR] {subagent_info['subagent_name']} failed: {error_message}")
            del self.active_subagents[run_id]
            # Clean up tool tracking
            if run_id in self.current_tool_info:
                del self.current_tool_info[run_id]
            return

        await self._emit_event(
            event_type="TOOL_ERROR",
            data={
                "run_id": str(run_id),
                "parent_run_id": str(parent_run_id) if parent_run_id else None,
                "error_type": error_type,
                "error": error_message,  # Changed from 'error_message' to 'error' for frontend compatibility
                "success": False
            }
        )

        # Clean up tool tracking
        if run_id in self.current_tool_info:
            del self.current_tool_info[run_id]

    # =========================================================================
    # Agent Reasoning Hooks
    # =========================================================================

    async def on_agent_action(
        self,
        action: AgentAction,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any
    ) -> None:
        """
        Called when an agent decides to take an action.

        Captures the agent's reasoning process and tool selection.
        This is critical for understanding agent decision-making.
        """
        tool_name = action.tool
        tool_input = action.tool_input
        reasoning = action.log  # Agent's thought process

        logger.debug(f"[AGENT ACTION] Tool={tool_name} (run_id={run_id})")

        # Get current node info from parent_run_id (agent actions are child of chain)
        node_info = self.current_node_info.get(parent_run_id, {})
        agent_label = node_info.get("agent_label")
        node_name = node_info.get("node_name")
        agent_type = node_info.get("agent_type")

        # Sanitize tool inputs
        sanitized_input = self._sanitize_arguments(tool_input) if self.enable_sanitization else tool_input

        await self._emit_event(
            event_type="AGENT_ACTION",
            data={
                "tool_name": tool_name,
                "tool_input": sanitized_input,
                "reasoning": reasoning if reasoning else "",  # Full reasoning for frontend display
                "reasoning_preview": reasoning[:200] if reasoning else "",  # Short preview for lists
                "thought_process": "analyzing",  # Status indicator for UI
                "run_id": str(run_id),
                "parent_run_id": str(parent_run_id) if parent_run_id else None,
                # Add node identification for frontend matching
                "agent_label": agent_label,
                "node_name": node_name,
                "agent_type": agent_type
            }
        )

    async def on_agent_finish(
        self,
        finish: AgentFinish,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any
    ) -> None:
        """
        Called when an agent completes its execution.

        Captures the final output and reasoning.
        """
        output = finish.return_values
        reasoning = finish.log

        logger.debug(f"[AGENT FINISH] run_id={run_id}")

        # Sanitize output
        sanitized_output = self._sanitize_arguments(output) if self.enable_sanitization else output

        await self._emit_event(
            event_type="AGENT_FINISH",
            data={
                "output": sanitized_output,
                "reasoning": reasoning[:500] if reasoning else "",
                "run_id": str(run_id),
                "parent_run_id": str(parent_run_id) if parent_run_id else None,
                "metrics": {
                    "tool_calls": self.tool_call_count,
                    "llm_calls": self.llm_call_count,
                    "total_tokens": self.total_tokens,
                    "errors": self.error_count
                }
            }
        )

    # =========================================================================
    # LLM Hooks (for token tracking)
    # =========================================================================

    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any
    ) -> None:
        """
        Called when an LLM completes generation.

        Tracks token usage for cost monitoring.
        """
        self.llm_call_count += 1

        # Extract token usage if available
        if response.llm_output and "token_usage" in response.llm_output:
            token_usage = response.llm_output["token_usage"]
            tokens_used = token_usage.get("total_tokens", 0)
            self.total_tokens += tokens_used

            # Lookup agent context from parent_run_id (critical for per-agent cost tracking)
            node_info = self.current_node_info.get(parent_run_id, {})
            agent_label = node_info.get("agent_label", "Unknown")

            # Extract model name from response (try multiple possible locations)
            model_name = "unknown"
            if response.llm_output:
                # Try model_name first (common in OpenAI/Anthropic responses)
                model_name = response.llm_output.get("model_name",
                            response.llm_output.get("model", "unknown"))

            # Fallback: try to extract from generations metadata
            if model_name == "unknown" and response.generations:
                for gen_list in response.generations:
                    if gen_list and hasattr(gen_list[0], 'generation_info'):
                        gen_info = gen_list[0].generation_info or {}
                        model_name = gen_info.get("model", model_name)
                        if model_name != "unknown":
                            break

            logger.debug(f"[LLM END] Agent={agent_label}, Model={model_name}, Tokens={tokens_used} (run_id={run_id})")

            await self._emit_event(
                event_type="LLM_END",
                data={
                    "run_id": str(run_id),
                    "agent_label": agent_label,  # NEW: For per-agent cost aggregation
                    "model": model_name,          # NEW: For accurate cost calculation
                    "tokens_used": tokens_used,
                    "prompt_tokens": token_usage.get("prompt_tokens", 0),
                    "completion_tokens": token_usage.get("completion_tokens", 0),
                    "cumulative_tokens": self.total_tokens
                }
            )

    async def on_chat_model_stream(
        self,
        chunk: Any,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any
    ) -> None:
        """
        Called when a chat model streams a token/chunk.

        Enables real-time streaming of LLM output to frontend for
        "thinking" visualization.
        """
        # Extract content from chunk
        chunk_content = None
        if hasattr(chunk, 'content') and chunk.content:
            chunk_content = chunk.content
        elif isinstance(chunk, dict) and 'content' in chunk:
            chunk_content = chunk['content']
        elif isinstance(chunk, str):
            chunk_content = chunk

        if chunk_content:
            # Look up agent_label from current_node_info using parent_run_id
            # This allows frontend to map streaming tokens to the correct node
            node_info = self.current_node_info.get(parent_run_id, {})
            agent_label = node_info.get("agent_label")

            # SUBAGENT CONTEXT: Check if this streaming token belongs to an active subagent
            # This enables the frontend to route tokens to the correct SubagentPanel
            subagent_context = self._get_subagent_context_for_run(run_id, parent_run_id)
            subagent_run_id = subagent_context.get("subagent_run_id") if subagent_context else None
            subagent_name = subagent_context.get("subagent_name") if subagent_context else None

            # ENHANCED DEBUG: Log streaming event lookup
            logger.info(
                f"[STREAM DEBUG] run_id={str(run_id)[:8]}, parent_run_id={str(parent_run_id)[:8] if parent_run_id else None}, "
                f"agent_label={agent_label}, subagent_run_id={subagent_run_id}, "
                f"tracked_parents={list(self.current_node_info.keys())}"
            )

            await self._emit_event(
                event_type="CHAT_MODEL_STREAM",
                data={
                    "run_id": str(run_id),
                    "parent_run_id": str(parent_run_id) if parent_run_id else None,
                    "content": chunk_content,  # Standardized field name for streaming content
                    "agent_label": agent_label,  # CRITICAL: Maps stream to correct node
                    "tags": tags or [],
                    # SUBAGENT FIELDS: Enable frontend to route to SubagentPanel
                    "subagent_run_id": subagent_run_id,
                    "subagent_name": subagent_name,
                }
            )

    def _get_subagent_context_for_run(
        self,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find if this run_id is inside an active subagent's execution scope.

        When a subagent is spawned via task() tool, all events with parent_run_id
        matching the task tool's run_id belong to that subagent.

        Returns:
            Dict with subagent_run_id and subagent_name if found, None otherwise
        """
        # First check if run_id itself is a subagent
        if run_id in self.active_subagents:
            subagent_info = self.active_subagents[run_id]
            return {
                "subagent_run_id": str(run_id),
                "subagent_name": subagent_info.get("subagent_name")
            }

        # Check if parent_run_id is a subagent (streaming happens inside tool execution)
        if parent_run_id and parent_run_id in self.active_subagents:
            subagent_info = self.active_subagents[parent_run_id]
            return {
                "subagent_run_id": str(parent_run_id),
                "subagent_name": subagent_info.get("subagent_name")
            }

        # Walk up the parent chain to find if any ancestor is an active subagent
        current_id = parent_run_id
        visited = set()  # Prevent infinite loops

        while current_id and current_id not in visited:
            visited.add(current_id)

            if current_id in self.active_subagents:
                subagent_info = self.active_subagents[current_id]
                return {
                    "subagent_run_id": str(current_id),
                    "subagent_name": subagent_info.get("subagent_name")
                }

            # Look up parent from current_node_info
            node_info = self.current_node_info.get(current_id)
            if node_info and "parent_run_id" in node_info:
                current_id = node_info.get("parent_run_id")
            else:
                break

        return None

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _emit_event(
        self,
        event_type: str,
        data: Dict[str, Any]
    ) -> None:
        """
        Internal helper to emit events to in-memory event bus AND persist to database.

        Args:
            event_type: Type of event (TOOL_START, CHAIN_END, etc.)
            data: Event-specific data payload
        """
        try:
            # Import here to avoid circular dependencies
            from services.event_bus import get_event_bus

            # Get event bus
            event_bus = get_event_bus()

            # Map internal event types to SSE event types expected by frontend
            sse_event_type_map = {
                "CHAIN_START": "on_chain_start",
                "CHAIN_END": "on_chain_end",
                "CHAIN_ERROR": "error",
                "TOOL_START": "on_tool_start",
                "TOOL_END": "on_tool_end",
                "TOOL_ERROR": "error",
                "AGENT_ACTION": "on_agent_action",
                "AGENT_FINISH": "on_agent_finish",
                "LLM_END": "on_llm_end",
                "CHAT_MODEL_STREAM": "on_chat_model_stream",
                "SUBAGENT_START": "subagent_start",
                "SUBAGENT_END": "subagent_end",
                "SUBAGENT_ERROR": "subagent_error"
            }

            # Get SSE-compatible event type
            sse_event_type = sse_event_type_map.get(event_type, event_type.lower())

            # Build full event payload in SSE format
            event_payload = {
                "type": sse_event_type,
                "data": {
                    **data,
                    "project_id": self.project_id,
                    "task_id": self.task_id,
                    "user_id": self.user_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }

            # Publish to workflow-specific channel (matches SSE endpoint subscription)
            if self.workflow_id:
                channel = f"workflow:{self.workflow_id}"
            else:
                # Fallback to project channel if workflow_id not set
                channel = f"project:{self.project_id}:execution"
                logger.warning(
                    f"No workflow_id set, using fallback channel: {channel}"
                )

            await event_bus.publish(channel, event_payload)

            logger.debug(
                f"Emitted {sse_event_type} event to {channel}: "
                f"project={self.project_id}, task={self.task_id}"
            )

            # Persist event to database for historical replay (non-blocking)
            # Use create_task to avoid blocking the event loop
            import asyncio
            persist_task = asyncio.create_task(self._persist_event_to_database(
                event_type=sse_event_type,
                event_data=event_payload["data"],
                run_id=data.get("run_id"),
                parent_run_id=data.get("parent_run_id")
            ))

            # Track pending persist tasks for cleanup callback
            self._pending_persist_tasks.append(persist_task)

            def cleanup_task(t, event_type=sse_event_type):
                self._handle_persist_error(t, event_type)
                # Remove from pending list when done
                try:
                    self._pending_persist_tasks.remove(t)
                except ValueError:
                    pass

            persist_task.add_done_callback(cleanup_task)

        except Exception as e:
            # Don't let event emission failures break workflow execution
            logger.warning(
                f"Failed to emit {event_type} event: {e}",
                exc_info=False
            )

    # =========================================================================
    # DeepAgents-Specific Callback Methods
    # =========================================================================

    async def on_deepagent_todo_created(
        self,
        todo_id: str,
        todo_text: str,
        node_name: str = "DeepAgent",
        **kwargs
    ) -> None:
        """
        Called when a DeepAgent creates a new todo item.

        Args:
            todo_id: Unique identifier for the todo
            todo_text: The todo item text
            node_name: Name of the agent node
        """
        await self._emit_event(
            event_type="DEEPAGENT_TODO_CREATED",
            data={
                "todo_id": todo_id,
                "todo_text": todo_text,
                "node_name": node_name,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    async def on_deepagent_todo_completed(
        self,
        todo_id: str,
        todo_text: str,
        node_name: str = "DeepAgent",
        **kwargs
    ) -> None:
        """
        Called when a DeepAgent completes a todo item.

        Args:
            todo_id: Unique identifier for the todo
            todo_text: The todo item text
            node_name: Name of the agent node
        """
        await self._emit_event(
            event_type="DEEPAGENT_TODO_COMPLETED",
            data={
                "todo_id": todo_id,
                "todo_text": todo_text,
                "node_name": node_name,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    async def on_deepagent_subagent_spawned(
        self,
        subagent_name: str,
        subagent_task: str,
        parent_node: str = "DeepAgent",
        **kwargs
    ) -> None:
        """
        Called when a DeepAgent spawns a subagent.

        Args:
            subagent_name: Name of the spawned subagent
            subagent_task: Task assigned to the subagent
            parent_node: Name of the parent agent node
        """
        await self._emit_event(
            event_type="DEEPAGENT_SUBAGENT_SPAWNED",
            data={
                "subagent_name": subagent_name,
                "subagent_task": subagent_task,
                "parent_node": parent_node,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    async def on_deepagent_filesystem_operation(
        self,
        operation: str,
        file_path: str,
        node_name: str = "DeepAgent",
        **kwargs
    ) -> None:
        """
        Called when a DeepAgent performs a filesystem operation.

        Args:
            operation: Type of operation (read, write, edit, ls, etc.)
            file_path: Path of the file being operated on
            node_name: Name of the agent node
        """
        await self._emit_event(
            event_type="DEEPAGENT_FILESYSTEM_OP",
            data={
                "operation": operation,
                "file_path": file_path,
                "node_name": node_name,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    async def on_deepagent_context_offload(
        self,
        context_size: int,
        offload_path: str,
        node_name: str = "DeepAgent",
        **kwargs
    ) -> None:
        """
        Called when a DeepAgent offloads context to filesystem to manage memory.

        Args:
            context_size: Size of context being offloaded (tokens/bytes)
            offload_path: Path where context is saved
            node_name: Name of the agent node
        """
        await self._emit_event(
            event_type="DEEPAGENT_CONTEXT_OFFLOAD",
            data={
                "context_size": context_size,
                "offload_path": offload_path,
                "node_name": node_name,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    # =========================================================================
    # Data Sanitization Helpers
    # =========================================================================

    def _sanitize_arguments(self, data: Any) -> Any:
        """
        Sanitize sensitive data from arguments before emission.

        Redacts common sensitive patterns:
        - API keys (patterns like "sk-", "api_key", etc.)
        - Passwords
        - Tokens
        - Credentials

        Args:
            data: Data to sanitize (dict, list, str, or primitive)

        Returns:
            Sanitized data with sensitive values redacted
        """
        if isinstance(data, dict):
            return {
                key: self._sanitize_value(key, value)
                for key, value in data.items()
            }
        elif isinstance(data, (list, tuple)):
            return [self._sanitize_arguments(item) for item in data]
        elif isinstance(data, str):
            return self._sanitize_string(data)
        else:
            return data

    def _sanitize_value(self, key: str, value: Any) -> Any:
        """Sanitize a single key-value pair."""
        # Check if key contains sensitive terms
        sensitive_keys = [
            "api_key", "apikey", "password", "passwd", "secret", "token",
            "credential", "auth", "bearer", "private_key", "access_key"
        ]

        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            return "[REDACTED]"

        # Recursively sanitize nested structures
        return self._sanitize_arguments(value)

    def _sanitize_string(self, text: str) -> str:
        """Sanitize sensitive patterns in strings."""
        # Redact common API key patterns
        patterns = [
            (r"sk-[a-zA-Z0-9]{32,}", "[API_KEY_REDACTED]"),  # OpenAI style
            (r"Bearer\s+[a-zA-Z0-9_\-\.]+", "Bearer [REDACTED]"),  # Bearer tokens
            (r"api[_-]?key[\"']?\s*[:=]\s*[\"']?[a-zA-Z0-9_\-]+", "api_key=[REDACTED]"),  # Generic API keys
        ]

        sanitized = text
        for pattern, replacement in patterns:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

        return sanitized

    async def _persist_event_to_database(
        self,
        event_type: str,
        event_data: Dict[str, Any],
        run_id: Optional[str] = None,
        parent_run_id: Optional[str] = None
    ) -> None:
        """
        Persist event to database for historical replay and debugging.

        Events are stored in the execution_events table and linked to the task.
        This enables:
        - Historical workflow replay after completion
        - Debugging and troubleshooting past executions
        - Persistent event logs accessible via API

        Args:
            event_type: Type of event (on_chain_start, on_tool_end, etc.)
            event_data: Full event data payload
            run_id: LangChain run ID for tracking
            parent_run_id: Parent run ID for nested executions
        """
        # Skip if database persistence is disabled
        if not self.save_to_db:
            logger.debug(f"Skipping DB persist for {event_type}: save_to_db={self.save_to_db}")
            return

        try:
            logger.debug(f"Starting DB persist for {event_type} (task={self.task_id})")
            # Import models and database session here to avoid circular deps
            from models.execution_event import ExecutionEvent
            from db.database import get_async_session

            # Create database event record
            event_record = ExecutionEvent(
                task_id=self.task_id,
                workflow_id=self.workflow_id,
                event_type=event_type,
                event_data=event_data,
                run_id=run_id,
                parent_run_id=parent_run_id
            )


            # Save to database using async session
            # CRITICAL: Ensure we're using the CURRENT event loop, not one from a thread
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # No running loop - this shouldn't happen in async context but handle it
                logger.warning(f"No running event loop for {event_type} - cannot persist to DB")
                return

            async with get_async_session() as session:
                session.add(event_record)
                await session.commit()
                await session.refresh(event_record)

            # Use debug level for streaming events to reduce log noise
            if event_type == "on_chat_model_stream":
                logger.debug(
                    f"✅ Persisted {event_type} event to database "
                    f"(id={event_record.id}, task={self.task_id})"
                )
            else:
                logger.info(
                    f"✅ Persisted {event_type} event to database "
                    f"(id={event_record.id}, task={self.task_id})"
                )


        except RuntimeError as e:
            # Catch async event loop conflicts (common with tool execution creating new loops)
            error_msg = str(e)
            if "event loop" in error_msg.lower() or "different loop" in error_msg.lower():
                logger.warning(
                    f"⚠️ Event loop conflict during {event_type} persistence - skipping DB save. "
                    f"This is a known issue with certain tools. Execution continues normally."
                )
            else:
                # Re-raise if it's a different RuntimeError
                logger.error(f"❌ RuntimeError persisting {event_type}: {e}", exc_info=True)
        except Exception as e:
            # Log error but don't break execution
            logger.warning(
                f"Failed to persist event {event_type} to database: {e}"
            )

    def _handle_persist_error(self, task: 'asyncio.Task', event_type: str) -> None:
        """Handle exceptions from async persist tasks."""
        try:
            task.result()  # This will raise if the task had an exception
        except Exception as e:
            logger.error(
                f"❌ Async persist task failed for {event_type}: {e}",
                exc_info=True
            )

    async def flush_pending_persists(self, timeout: float = 5.0) -> None:
        """
        Wait for all pending database persist tasks to complete.

        Call this at the end of workflow execution to ensure all events
        are persisted to the database before the workflow handler exits.

        Args:
            timeout: Maximum time to wait for pending tasks (seconds)
        """
        if not self._pending_persist_tasks:
            return

        pending_count = len(self._pending_persist_tasks)
        logger.info(f"🔄 Flushing {pending_count} pending database persist tasks...")

        try:
            # Wait for all pending tasks with timeout
            done, pending = await asyncio.wait(
                self._pending_persist_tasks,
                timeout=timeout,
                return_when=asyncio.ALL_COMPLETED
            )

            if pending:
                logger.warning(
                    f"⚠️ {len(pending)} persist tasks timed out after {timeout}s - "
                    "some events may not be saved to database"
                )
                # Cancel timed out tasks
                for task in pending:
                    task.cancel()
            else:
                logger.info(f"✅ All {len(done)} persist tasks completed successfully")

        except Exception as e:
            logger.error(f"❌ Error flushing persist tasks: {e}")
        finally:
            self._pending_persist_tasks.clear()


# =============================================================================
# Factory Function for Easy Integration
# =============================================================================

def create_execution_callback_handler(
    project_id: int,
    task_id: int,
    workflow_id: Optional[int] = None,
    user_id: Optional[str] = None,
    enable_sanitization: bool = True,
    node_metadata: Optional[Dict[str, Dict[str, Any]]] = None
) -> ExecutionEventCallbackHandler:
    """
    Factory function to create an ExecutionEventCallbackHandler.

    Usage:
        callback = create_execution_callback_handler(
            project_id=123,
            task_id=456,
            workflow_id=789,  # Required for SSE streaming
            node_metadata={...}  # For proper event labeling
        )

        result = await agent_graph.ainvoke(
            input_data,
            config={"callbacks": [callback]}
        )

    Args:
        project_id: Project ID for event attribution
        task_id: Task ID for event attribution
        workflow_id: Workflow ID for channel routing (required for SSE streaming)
        user_id: Optional user ID for audit trails
        enable_sanitization: Whether to sanitize sensitive data

    Returns:
        Configured callback handler
    """
    return ExecutionEventCallbackHandler(
        project_id=project_id,
        task_id=task_id,
        workflow_id=workflow_id,
        user_id=user_id,
        enable_sanitization=enable_sanitization,
        node_metadata=node_metadata,
        save_to_db=True  # Enable DB persistence for historical execution logs
    )


# =============================================================================
# Usage Example (Documentation)
# =============================================================================

"""
USAGE EXAMPLE: Integrating with LangGraph Workflow

from core.workflows.events.emitter import create_execution_callback_handler
from core.agents.factory import AgentFactory

async def execute_agent_workflow(project_id: int, task_id: int, user_input: str):
    # 1. Create callback handler for observability
    callback = create_execution_callback_handler(
        project_id=project_id,
        task_id=task_id
    )

    # 2. Create agent using AgentFactory
    agent_config = {
        "model": "gpt-4o",
        "temperature": 0.7,
        "system_prompt": "You are a helpful assistant.",
        "mcp_tools": ["filesystem", "web_search"],
        "enable_memory": True
    }

    agent_graph, tools, callbacks = await AgentFactory.create_agent(
        agent_config=agent_config,
        project_id=project_id,
        task_id=task_id,
        context="Execute user request with available tools."
    )

    # 3. Combine callbacks (AgentFactory + Execution Events)
    all_callbacks = callbacks + [callback]

    # 4. Execute workflow with full observability
    result = await agent_graph.ainvoke(
        {"messages": [{"role": "user", "content": user_input}]},
        config={"callbacks": all_callbacks}
    )

    # 5. Access execution metrics
    print(f"Tool calls: {callback.tool_call_count}")
    print(f"Total tokens: {callback.total_tokens}")
    print(f"Errors: {callback.error_count}")

    return result

# Frontend clients receive real-time events via SSE (Server-Sent Events):
# - CHAIN_START/END: Node lifecycle
# - TOOL_START/END/ERROR: Tool invocations
# - AGENT_ACTION: Agent reasoning steps
# - LLM_END: Token usage tracking
#
# Connect to SSE stream:
# GET /api/orchestration/workflows/{workflow_id}/stream
# new EventSource('/api/orchestration/workflows/123/stream')
"""
