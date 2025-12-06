# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Simple Workflow Executor for User-Created Workflows

This module executes workflows that users create in the frontend.
No blueprints, no strategies - just execute the workflow definition stored in the database.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, List, Annotated, TypedDict
from datetime import datetime
import operator

from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

from models.workflow import WorkflowProfile
from core.workflows.events.emitter import create_execution_callback_handler
from core.workflows.checkpointing.manager import get_store

logger = logging.getLogger(__name__)


# Simple state for user-created workflows
class SimpleWorkflowState(TypedDict):
    """
    State for user-created workflows from the frontend.

    This state supports all core workflow features including:
    - Multi-agent collaboration via message passing
    - RAG/vector store integration
    - MCP tool access
    - Execution history and timing metrics
    """
    # Core identifiers
    workflow_id: int
    task_id: Optional[int]
    project_id: Optional[int]

    # LangChain messages (with reducer for automatic accumulation)
    messages: Annotated[List[BaseMessage], operator.add]

    # User input
    query: str

    # Execution context (for RAG)
    context_documents: Optional[List[int]]

    # Node tracking
    current_node: Optional[str]
    last_agent_type: Optional[str]

    # Execution history (with reducer)
    step_history: Annotated[List[Dict[str, Any]], operator.add]

    # Results
    result: Optional[Dict[str, Any]]
    error_message: Optional[str]

    # Timing metrics
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    execution_duration_seconds: Optional[float]

    # Control flow state
    conditional_route: Optional[str]  # For CONDITIONAL_NODE routing
    loop_route: Optional[str]  # For LOOP_NODE routing
    loop_iterations: Optional[Dict[str, int]]  # Track iterations per loop node
    loop_iteration: Optional[int]  # Current iteration of active loop
    loop_should_exit: Optional[bool]  # Whether loop should exit
    loop_exit_reason: Optional[str]  # Reason for loop exit


class SimpleWorkflowExecutor:
    """
    Executes user-created workflows from the database.

    Takes a WorkflowProfile (which contains nodes/edges from React Flow)
    and executes it using LangGraph.
    """

    def __init__(self):
        self.node_metadata = {}  # Will be populated during graph building

    async def execute_workflow(
        self,
        workflow: WorkflowProfile,
        input_data: Dict[str, Any],
        project_id: int,
        task_id: int
    ) -> Dict[str, Any]:
        """
        Execute a user-created workflow.

        Args:
            workflow: WorkflowProfile from database with nodes/edges
            input_data: Input data from user (e.g., {"query": "..."})
            project_id: Project ID
            task_id: Task ID for tracking

        Returns:
            Final state with results
        """
        logger.info(f"Executing workflow '{workflow.name}' (id={workflow.id}) for task {task_id}")

        # Get event bus for real-time monitoring
        from services.event_bus import get_event_bus
        event_bus = get_event_bus()
        channel = f"workflow:{workflow.id}"

        try:
            # Publish workflow start event
            await event_bus.publish(channel, {
                "type": "status",
                "data": {
                    "status": "starting",
                    "workflow_name": workflow.name,
                    "workflow_id": workflow.id,
                    "task_id": task_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            })

            # 0. Validate and pre-initialize tools BEFORE workflow execution
            logger.info("Validating workflow tools and pre-initializing async tools...")
            await event_bus.publish(channel, {
                "type": "status",
                "data": {
                    "status": "validating_tools",
                    "message": "Validating and initializing workflow tools...",
                    "timestamp": datetime.utcnow().isoformat()
                }
            })

            try:
                await self._validate_and_init_tools(workflow, channel, event_bus)
            except Exception as tool_error:
                error_msg = f"Tool validation failed: {str(tool_error)}"
                logger.error(error_msg)
                await event_bus.publish(channel, {
                    "type": "error",
                    "data": {
                        "error": error_msg,
                        "error_type": "ToolValidationError",
                        "workflow_id": workflow.id,
                        "task_id": task_id,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                })
                # Emit complete event so UI stops spinner
                await event_bus.publish(channel, {
                    "type": "complete",
                    "data": {
                        "status": "error",
                        "error": error_msg,
                        "error_type": "ToolValidationError",
                        "workflow_id": workflow.id,
                        "task_id": task_id,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                })
                raise ValueError(error_msg)

            # 1. Build LangGraph from workflow definition
            logger.info(f"Building graph from workflow configuration")
            await event_bus.publish(channel, {
                "type": "on_chain_start",
                "data": {
                    "name": "build_graph",
                    "message": f"Building workflow graph with {len(workflow.configuration.get('nodes', []))} nodes"
                }
            })

            graph = await self._build_graph_from_workflow(workflow)

            # 2. Get checkpointer for state persistence
            # Only use checkpointer if explicitly enabled in input_data
            checkpointer_enabled = input_data.get("checkpointer_enabled", False)
            from core.workflows.checkpointing.manager import get_checkpointer
            checkpointer = get_checkpointer() if checkpointer_enabled else None

            # 3. Compile the graph with checkpointer
            if checkpointer:
                logger.info(f"Compiling workflow '{workflow.name}' with checkpointing enabled")
                compiled_graph = graph.compile(
                    checkpointer=checkpointer,
                    interrupt_before=[]  # Can add APPROVAL_NODE here for HITL
                )
            else:
                logger.warning(
                    f"Compiling workflow '{workflow.name}' WITHOUT checkpointing - "
                    f"state will not be persisted"
                )
                compiled_graph = graph.compile()

            # 4. Create initial state with user's query
            query = input_data.get("query", "")
            now = datetime.utcnow()
            initial_state: SimpleWorkflowState = {
                "workflow_id": workflow.id,
                "task_id": task_id,
                "project_id": project_id,
                "messages": [],
                "query": query,
                "context_documents": input_data.get("context_documents"),
                "current_node": None,
                "last_agent_type": None,
                "step_history": [],
                "result": None,
                "error_message": None,
                "started_at": now,
                "completed_at": None,
                "execution_duration_seconds": None
            }

            # 5. Create callback handler for detailed agent logging
            callback_handler = create_execution_callback_handler(
                project_id=project_id if project_id else 0,
                task_id=task_id,
                workflow_id=workflow.id,  # Required for SSE channel routing
                enable_sanitization=True,
                node_metadata=self.node_metadata  # Pass node metadata for proper event labeling
            )
            logger.info(f"Created execution callback handler for detailed event tracking (workflow:{workflow.id})")

            # 6. Configure workflow execution with thread_id for checkpointing and callbacks
            # Add Store for long-term memory if available
            store = get_store()
            config = {
                "configurable": {
                    "thread_id": f"workflow_{workflow.id}_task_{task_id}"
                },
                "callbacks": [callback_handler],
                "recursion_limit": input_data.get("recursion_limit", 100)  # Use user-defined limit or default to 100
            }

            # Add Store to config if initialized (enables runtime.store API for long-term memory)
            if store is not None:
                config["configurable"]["store"] = store
                logger.info("Long-term memory (Store) enabled for workflow execution")

            # 7. Execute the workflow with checkpointing config and callbacks
            logger.info(f"Starting execution of workflow '{workflow.name}'")
            await event_bus.publish(channel, {
                "type": "status",
                "data": {
                    "status": "executing",
                    "message": "Executing workflow nodes...",
                    "timestamp": datetime.utcnow().isoformat()
                }
            })

            # ========================================================================
            # CRITICAL: WORKFLOW EXECUTION LOOP - DO NOT MODIFY WITHOUT TESTING
            # ========================================================================
            # This loop processes LangGraph events and MUST properly exit or workflows
            # will run forever. Changes to completion detection logic (line ~402) can
            # cause infinite loops. Always test workflow completion after modifications.
            # ========================================================================

            # Use astream_events() to enable LLM token streaming
            # Unlike astream() which only streams node outputs, astream_events() streams ALL events
            # including LLM tokens - but we must manually publish them to SSE!
            final_state = None
            token_buffer = {}  # Buffer tokens per node to batch them and reduce spam
            last_publish_time = {}  # Track last publish time per node for throttling

            # Tool call JSON buffering to aggregate partial_json chunks and extract reasoning
            tool_call_buffer = {}  # {tool_call_id: {"name": str, "json_parts": [], "agent_label": str}}

            # Get cancellation registry for checking cancellation during execution
            from core.workflows.checkpointing.cancellation import get_cancellation_registry
            registry = get_cancellation_registry()

            # SAFETY: Prevent infinite loops with max events and timeout
            MAX_EVENTS = 10000  # Hard limit on events
            TIMEOUT_SECONDS = 600  # 10 minute timeout
            event_count = 0
            execution_start_time = datetime.utcnow()

            # RECURSION TRACKING: Track agent actions to detect loops
            agent_action_history = []  # List of (agent_label, tool_name, timestamp) tuples
            MAX_HISTORY_SIZE = 200  # Keep last 200 actions for analysis

            async for event in compiled_graph.astream_events(initial_state, config=config, version="v2"):
                event_count += 1

                # Check event count limit
                if event_count > MAX_EVENTS:
                    error_msg = f"Workflow exceeded maximum event limit ({MAX_EVENTS}). Possible infinite loop detected."
                    logger.error(error_msg)
                    await event_bus.publish(channel, {
                        "type": "error",
                        "data": {
                            "error": error_msg,
                            "error_type": "MaxEventsExceeded",
                            "workflow_id": workflow.id,
                            "task_id": task_id,
                            "event_count": event_count,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    })
                    raise RuntimeError(error_msg)

                # Check timeout
                elapsed = (datetime.utcnow() - execution_start_time).total_seconds()
                if elapsed > TIMEOUT_SECONDS:
                    error_msg = f"Workflow execution timeout ({TIMEOUT_SECONDS}s). Stopping execution."
                    logger.error(error_msg)
                    await event_bus.publish(channel, {
                        "type": "error",
                        "data": {
                            "error": error_msg,
                            "error_type": "ExecutionTimeout",
                            "workflow_id": workflow.id,
                            "task_id": task_id,
                            "elapsed_seconds": elapsed,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    })
                    raise TimeoutError(error_msg)
                # Check for cancellation at every event
                if await registry.is_cancelled(task_id):
                    logger.info(f"Task {task_id} cancelled - stopping workflow execution")
                    await event_bus.publish(channel, {
                        "type": "error",
                        "data": {
                            "error": "Workflow cancelled by user",
                            "error_type": "TaskCancelled",
                            "workflow_id": workflow.id,
                            "task_id": task_id,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    })
                    raise asyncio.CancelledError("Task cancelled by user")
                # astream_events yields ALL events including LLM tokens and state updates
                kind = event.get("event")

                # Handle LLM token streaming - batch and throttle to reduce spam
                if kind == "on_chat_model_stream":
                    # Extract token from event
                    data = event.get("data", {})
                    chunk = data.get("chunk")
                    token_text = None

                    # Get node_id early to determine model provider
                    tags = event.get("tags", [])
                    metadata = event.get("metadata", {})
                    node_id = metadata.get("node_id") or (tags[0] if tags and tags[0].startswith("node-") else None)

                    # Determine model provider from node config
                    model_provider = None
                    if node_id and node_id in self.node_metadata:
                        model_config = self.node_metadata[node_id].get("config", {})
                        model_name = model_config.get("model", "").lower()

                        # Detect provider from model name
                        if "claude" in model_name or "anthropic" in model_name:
                            model_provider = "anthropic"
                        elif "gpt" in model_name or "o1" in model_name or "openai" in model_name:
                            model_provider = "openai"
                        elif "gemini" in model_name or "google" in model_name:
                            model_provider = "google"
                        else:
                            model_provider = "unknown"

                    logger.debug(f"[DEBUG] Provider: {model_provider}, Chunk type: {type(chunk)}, Value preview: {str(chunk)[:100]}")

                    # Provider-specific token extraction
                    if chunk and hasattr(chunk, 'content'):
                        content = chunk.content

                        if model_provider == "anthropic":
                            # Claude/Anthropic: content = [{'text': 'token', 'type': 'text', 'index': 0}]
                            if isinstance(content, list) and len(content) > 0:
                                text_parts = []
                                for item in content:
                                    if isinstance(item, dict) and 'text' in item:
                                        text_parts.append(item['text'])
                                    elif isinstance(item, str):
                                        text_parts.append(item)
                                token_text = ''.join(text_parts) if text_parts else None
                            elif isinstance(content, str):
                                token_text = content

                        elif model_provider in ("openai", "google"):
                            # OpenAI/Gemini: content = "token string"
                            if isinstance(content, str):
                                token_text = content
                            elif content:
                                token_text = str(content)

                        else:
                            # Unknown provider - try both approaches as fallback
                            if isinstance(content, str):
                                token_text = content
                            elif isinstance(content, list) and len(content) > 0:
                                text_parts = []
                                for item in content:
                                    if isinstance(item, dict) and 'text' in item:
                                        text_parts.append(item['text'])
                                    elif isinstance(item, str):
                                        text_parts.append(item)
                                token_text = ''.join(text_parts) if text_parts else None
                            elif content:
                                token_text = str(content)

                    # Also check for tool call streaming (partial_json chunks)
                    if chunk and hasattr(chunk, 'content') and isinstance(chunk.content, list):
                        for item in chunk.content:
                            if isinstance(item, dict):
                                # Check for tool call with partial_json
                                if item.get('type') == 'input_json_delta' and 'partial_json' in item:
                                    partial_json = item['partial_json']
                                    tool_call_index = item.get('index', 0)

                                    # Get tool call ID from chunk metadata
                                    tool_call_id = f"{node_id}_{tool_call_index}"

                                    # Initialize buffer for this tool call
                                    if tool_call_id not in tool_call_buffer:
                                        tool_call_buffer[tool_call_id] = {
                                            "name": None,
                                            "json_parts": [],
                                            "agent_label": None,
                                            "notified": False  # Track if we've sent notification
                                        }

                                    # Accumulate JSON parts
                                    tool_call_buffer[tool_call_id]["json_parts"].append(partial_json)

                                    # Store agent label if we have node_id
                                    if node_id and node_id in self.node_metadata:
                                        tool_call_buffer[tool_call_id]["agent_label"] = self.node_metadata[node_id]["label"]

                                    # Try to extract filename early for file_write tool
                                    tool_name = tool_call_buffer[tool_call_id].get("name")
                                    if tool_name == "file_write" and not tool_call_buffer[tool_call_id].get("notified"):
                                        # Reconstruct JSON so far to check if we have file_path
                                        json_so_far = ''.join(tool_call_buffer[tool_call_id]["json_parts"])

                                        # Try to extract file_path using regex (faster than JSON parse)
                                        import re
                                        match = re.search(r'"file_path"\s*:\s*"([^"]+)"', json_so_far)

                                        if match:
                                            filename = match.group(1)
                                            agent_label = tool_call_buffer[tool_call_id].get("agent_label")

                                            if agent_label and filename:
                                                # Check if file exists to determine message
                                                import os
                                                file_exists = os.path.exists(filename)
                                                action = "Working on" if file_exists else "Creating"

                                                # Extract just the filename from path
                                                display_name = os.path.basename(filename)

                                                await event_bus.publish(channel, {
                                                    "type": "tool_start",
                                                    "data": {
                                                        "tool_name": tool_name,
                                                        "agent_label": agent_label,
                                                        "file_action": action,
                                                        "filename": display_name,
                                                        "full_path": filename,
                                                        "run_id": str(event.get("run_id", "")),
                                                        "timestamp": datetime.utcnow().isoformat()
                                                    }
                                                })
                                                logger.info(f"[TOOL START] {agent_label}: {action} {display_name}")
                                                tool_call_buffer[tool_call_id]["notified"] = True

                                # Check for tool_use start (contains tool name)
                                elif item.get('type') == 'tool_use' and 'name' in item:
                                    tool_name = item['name']
                                    tool_call_index = item.get('index', 0)
                                    tool_call_id = f"{node_id}_{tool_call_index}"

                                    if tool_call_id in tool_call_buffer:
                                        tool_call_buffer[tool_call_id]["name"] = tool_name
                                        tool_call_buffer[tool_call_id]["tool_use_id"] = item.get('id')  # Store for later filename extraction

                    # DEBUG: Log what we extracted (debug level to avoid spam)
                    logger.debug(f"[EXTRACTED TOKEN] Provider: {model_provider}, Type: {type(token_text)}, Value: {repr(token_text)[:200]}")

                    if token_text and isinstance(token_text, str):
                        # Try to extract agent_label from event tags/metadata
                        tags = event.get("tags", [])
                        metadata = event.get("metadata", {})
                        agent_label = None

                        # Look for node_id in tags or metadata to find agent_label
                        node_id = metadata.get("node_id") or (tags[0] if tags and tags[0].startswith("node-") else None)
                        if node_id and node_id in self.node_metadata:
                            agent_label = self.node_metadata[node_id]["label"]

                        # Skip if we don't have a node_id (can't buffer properly)
                        if not node_id:
                            continue

                        # Buffer tokens per node (use node_id as key to keep agents separate)
                        if node_id not in token_buffer:
                            token_buffer[node_id] = ""
                            last_publish_time[node_id] = 0

                        token_buffer[node_id] += token_text

                        # Throttle: only publish every 50ms OR when buffer reaches 20 chars
                        current_time = datetime.utcnow().timestamp()
                        time_since_last = current_time - last_publish_time[node_id]
                        buffer_size = len(token_buffer[node_id])

                        if time_since_last > 0.1 or buffer_size > 40:  # 100ms throttle or 40 char buffer
                            stream_data = {
                                "token": token_buffer[node_id],
                                "content": token_buffer[node_id],  # Also include as 'content' for consistency
                                "agent_label": agent_label,
                                "node_id": node_id,  # Include node_id for proper grouping in frontend
                                "run_id": str(event.get("run_id", "")),
                                "parent_run_id": str(event.get("parent_run_id", "")) if event.get("parent_run_id") else None,
                                "timestamp": datetime.utcnow().isoformat()
                            }

                            # _emit_event handles BOTH:
                            # 1. Publishing to event bus (for live SSE streaming)
                            # 2. Persisting to database (for historical replay)
                            # Do NOT also call event_bus.publish() - that causes duplicate tokens!
                            await callback_handler._emit_event(
                                event_type="CHAT_MODEL_STREAM",
                                data=stream_data
                            )

                            logger.debug(f"[STREAMING] {agent_label or node_id}: {token_buffer[node_id][:50]}...")
                            token_buffer[node_id] = ""  # Clear buffer
                            last_publish_time[node_id] = current_time

                # ========================================================================
                # LLM END EVENT CAPTURE (for token tracking)
                # ========================================================================
                # Capture token usage from LLM completion events and save to database
                # This enables per-agent cost tracking in the workflow library
                elif kind == "on_llm_end" or kind == "on_chat_model_end":
                    logger.info(f"[TOKEN CAPTURE] Received {kind} event")
                    try:
                        # Extract token usage from event
                        data = event.get("data", {})
                        output = data.get("output", {})

                        # Get token usage - try multiple paths for different LangChain versions
                        tokens_used = 0
                        prompt_tokens = 0
                        completion_tokens = 0

                        # Path 1: llm_output.token_usage (older LangChain)
                        llm_output = output.get("llm_output", {})
                        token_usage = llm_output.get("token_usage", {})
                        if token_usage:
                            tokens_used = token_usage.get("total_tokens", 0)
                            prompt_tokens = token_usage.get("prompt_tokens", 0)
                            completion_tokens = token_usage.get("completion_tokens", 0)

                        # Path 2: usage_metadata (newer LangChain)
                        if tokens_used == 0:
                            usage_metadata = output.get("usage_metadata") or data.get("usage_metadata")
                            if usage_metadata:
                                if isinstance(usage_metadata, dict):
                                    tokens_used = usage_metadata.get("total_tokens", 0)
                                    prompt_tokens = usage_metadata.get("input_tokens", 0)
                                    completion_tokens = usage_metadata.get("output_tokens", 0)
                                else:
                                    tokens_used = getattr(usage_metadata, 'total_tokens', 0)
                                    prompt_tokens = getattr(usage_metadata, 'input_tokens', 0)
                                    completion_tokens = getattr(usage_metadata, 'output_tokens', 0)

                        if tokens_used == 0:
                            logger.warning(f"[TOKEN CAPTURE] No tokens found. Event structure: data keys={list(data.keys())}, output keys={list(output.keys()) if output else None}")

                        logger.info(f"[TOKEN CAPTURE] Extracted tokens: {tokens_used} (prompt: {prompt_tokens}, completion: {completion_tokens})")

                        if tokens_used > 0:
                            # Get node context for agent_label
                            tags = event.get("tags", [])
                            metadata = event.get("metadata", {})
                            node_id = metadata.get("node_id") or next((tag for tag in tags if tag.startswith("node-")), None)

                            agent_label = "Unknown"
                            model_name = "unknown"

                            if node_id and node_id in self.node_metadata:
                                agent_label = self.node_metadata[node_id].get("label", "Unknown")
                                model_config = self.node_metadata[node_id].get("config", {})
                                model_name = model_config.get("model", "unknown")

                            # Also try to get model from llm_output
                            if model_name == "unknown":
                                model_name = llm_output.get("model_name", llm_output.get("model", "unknown"))

                            # Save LLM_END event to database via callback handler
                            run_id = event.get("run_id", "")
                            await callback_handler._emit_event(
                                event_type="LLM_END",
                                data={
                                    "run_id": str(run_id),
                                    "agent_label": agent_label,
                                    "model": model_name,
                                    "tokens_used": tokens_used,
                                    "prompt_tokens": prompt_tokens,
                                    "completion_tokens": completion_tokens,
                                    "cumulative_tokens": 0  # Will be calculated in aggregation
                                }
                            )

                            logger.info(f"[LLM END] Captured token usage: agent={agent_label}, model={model_name}, tokens={tokens_used}")
                    except Exception as e:
                        logger.warning(f"Failed to capture LLM_END event: {e}")

                # ========================================================================
                # CRITICAL: STATE CAPTURE FROM GRAPH EVENTS
                # ========================================================================
                # Capture state from chain_end events as the graph progresses.
                # The loop will exit naturally when astream_events completes.
                # ========================================================================

                # Capture state from chain completion events
                elif kind == "on_chain_end":
                    event_name = event.get("name", "")
                    event_data = event.get("data", {})

                    # RECURSION TRACKING: Record node executions
                    tags = event.get("tags", [])
                    node_id = next((tag for tag in tags if tag.startswith("node-")), None)
                    if node_id and node_id in self.node_metadata:
                        agent_label = self.node_metadata[node_id]["label"]
                        agent_action_history.append((agent_label, "node_end", datetime.utcnow()))

                        # Keep history size bounded
                        if len(agent_action_history) > MAX_HISTORY_SIZE:
                            agent_action_history.pop(0)

                        # Check for simple loop patterns (same node 5+ times in a row)
                        # DISABLED: These warnings were too noisy and disrupted streaming
                        # if len(agent_action_history) >= 5:
                        #     recent = agent_action_history[-5:]
                        #     if all(action[0] == agent_label for action in recent):
                        #         logger.warning(f"⚠️  RECURSION WARNING: {agent_label} executed 5 times in a row")
                        #         logger.warning(f"Recent actions: {[(a[0], a[1]) for a in agent_action_history[-20:]]}")

                        # EARLY WARNING: If we're getting close to the limit, log it
                        # DISABLED: Too noisy for long-running workflows
                        # if len(agent_action_history) >= 20:
                        #     logger.warning(f"🚨 HIGH ITERATION COUNT: {len(agent_action_history)} actions so far")
                        #     logger.warning(f"⚠️  If this continues, check:")
                        #     logger.warning(f"   1. Agent system prompt has completion criteria")
                        #     logger.warning(f"   2. Agent isn't stuck in tool loop")
                        #     logger.warning(f"   3. Workflow graph doesn't have cycles")

                    # Capture any valid output state we encounter
                    # This ensures we have the latest state when loop exits naturally
                    potential_state = event_data.get("output")
                    if potential_state and isinstance(potential_state, dict):
                        final_state = potential_state
                        logger.debug(f"[STATE] Captured state from {event_name} event")

                        # ========================================================================
                        # HITL (Human-in-the-Loop) Detection
                        # ========================================================================
                        # Check if agent requested an interrupt (e.g., asking a question)
                        if potential_state.get("interrupt_requested"):
                            interrupt_reason = potential_state.get("interrupt_reason", "unknown")
                            pending_question = potential_state.get("pending_question", "")

                            logger.warning(f"🛑 HITL interrupt requested: {interrupt_reason}")
                            logger.info(f"Question: {pending_question[:200]}...")

                            # Publish HITL event to frontend
                            await event_bus.publish(channel, {
                                "type": "hitl_required",
                                "data": {
                                    "workflow_id": workflow.id,
                                    "task_id": task_id,
                                    "reason": interrupt_reason,
                                    "question": pending_question,
                                    "timestamp": datetime.utcnow().isoformat()
                                }
                            })

                            # For now, continue execution (Question Detection is informational)
                            # TODO: Implement proper pause/resume with LangGraph checkpointing
                            # This would require:
                            # 1. Break from astream_events loop
                            # 2. Save checkpoint state
                            # 3. Wait for user approval via HITL API
                            # 4. Resume from checkpoint when approved
                            logger.info("⚠️  HITL detection active but not pausing (informational mode)")
                            # In future: break  # Exit loop and wait for approval

            # Loop has exited naturally - LangGraph is done
            logger.info(f"[COMPLETION] Graph execution completed after {event_count} events")

            # Flush any remaining buffered tokens
            for node_id, buffered_text in token_buffer.items():
                if buffered_text:
                    # Get agent_label from node_metadata
                    agent_label = self.node_metadata.get(node_id, {}).get("label")
                    await event_bus.publish(channel, {
                        "type": "on_chat_model_stream",
                        "data": {
                            "token": buffered_text,
                            "agent_label": agent_label,
                            "node_id": node_id,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    })

            # Process completed tool calls to extract reasoning
            for tool_call_id, tool_data in tool_call_buffer.items():
                tool_name = tool_data.get("name")
                json_parts = tool_data.get("json_parts", [])
                agent_label = tool_data.get("agent_label")

                # Only process reasoning_chain tool calls with content
                if tool_name == "reasoning_chain" and json_parts and agent_label:
                    try:
                        # Reconstruct full JSON from partial chunks
                        full_json_str = ''.join(json_parts)
                        tool_input = json.loads(full_json_str)

                        # Extract reasoning text from tool input
                        reasoning_text = tool_input.get("task", "") or tool_input.get("query", "") or tool_input.get("reasoning", "")

                        if reasoning_text:
                            logger.info(f"[TOOL REASONING] {agent_label}: {reasoning_text[:100]}...")

                            # Stream the reasoning as if it were thinking text
                            await event_bus.publish(channel, {
                                "type": "on_chat_model_stream",
                                "data": {
                                    "token": f"\n🧠 Reasoning: {reasoning_text}",
                                    "agent_label": agent_label,
                                    "timestamp": datetime.utcnow().isoformat()
                                }
                            })
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse tool call JSON for {tool_call_id}: {e}")
                    except Exception as e:
                        logger.error(f"Error processing tool call reasoning: {e}")

            # If no state captured (shouldn't happen but defensive), fall back to initial state
            if final_state is None:
                logger.warning("No final state from astream_events - using initial state")
                final_state = initial_state

            logger.info(f"Workflow '{workflow.name}' completed successfully")
            await event_bus.publish(channel, {
                "type": "on_chain_end",
                "data": {
                    "name": "workflow_execution",
                    "message": "Workflow execution completed",
                    "timestamp": datetime.utcnow().isoformat()
                }
            })

            # 7. Aggregate workflow execution summary (tool calls, token usage by agent)
            from models.execution_event import ExecutionEvent
            from db.database import get_db, SessionLocal

            workflow_summary = {
                "tool_calls_by_agent": {},
                "tokens_by_agent": {},
                "total_tool_calls": 0,
                "total_tokens": 0,
                "total_cost_usd": 0.0
            }

            # Query all execution events for this task
            db = SessionLocal()
            try:
                tool_events = db.query(ExecutionEvent).filter(
                    ExecutionEvent.task_id == task_id,
                    ExecutionEvent.event_type == "on_tool_start"
                ).all()

                token_events = db.query(ExecutionEvent).filter(
                    ExecutionEvent.task_id == task_id,
                    ExecutionEvent.event_type == "LLM_END"
                ).all()

                # Aggregate tool calls by agent
                for event in tool_events:
                    agent_name = event.event_data.get("agent_label", "Unknown")
                    tool_name = event.event_data.get("tool_name", "unknown")

                    if agent_name not in workflow_summary["tool_calls_by_agent"]:
                        workflow_summary["tool_calls_by_agent"][agent_name] = []

                    workflow_summary["tool_calls_by_agent"][agent_name].append({
                        "tool": tool_name,
                        "timestamp": event.timestamp.isoformat() if event.timestamp else None
                    })
                    workflow_summary["total_tool_calls"] += 1

                # Aggregate tokens by agent
                for event in token_events:
                    agent_name = event.event_data.get("agent_label", "Unknown")
                    tokens = event.event_data.get("tokens_used", 0)
                    model = event.event_data.get("model", "unknown")

                    if agent_name not in workflow_summary["tokens_by_agent"]:
                        workflow_summary["tokens_by_agent"][agent_name] = {
                            "tokens": 0,
                            "model": model,
                            "calls": 0
                        }

                    workflow_summary["tokens_by_agent"][agent_name]["tokens"] += tokens
                    workflow_summary["tokens_by_agent"][agent_name]["calls"] += 1
                    workflow_summary["total_tokens"] += tokens

                # Cost estimation based on current model pricing (Updated December 2025)
                cost_per_1m_tokens = {
                    # OpenAI Reasoning Models
                    "o3": 20.00,
                    "o3-mini": 4.00,
                    "o4-mini": 3.00,
                    # OpenAI GPT-4o Series
                    "gpt-4o": 2.50,
                    "gpt-4o-mini": 0.15,
                    # Anthropic Claude 4.5
                    "claude-opus-4-5": 15.00,
                    "claude-sonnet-4-5": 3.00,
                    "claude-sonnet-4-5-20250929": 3.00,
                    "claude-haiku-4-5": 1.00,
                    # Google Gemini 3
                    "gemini-3-pro-preview": 2.00,
                    # Google Gemini 2.5
                    "gemini-2.5-flash": 0.075,
                    # Google Gemini 2.0
                    "gemini-2.0-flash": 0.075,
                    "default": 1.00
                }

                for agent_name, data in workflow_summary["tokens_by_agent"].items():
                    model = data["model"].lower()
                    rate = next((v for k, v in cost_per_1m_tokens.items() if k in model), cost_per_1m_tokens["default"])
                    agent_cost = (data["tokens"] / 1_000_000) * rate
                    data["estimated_cost_usd"] = round(agent_cost, 4)
                    workflow_summary["total_cost_usd"] += agent_cost

                workflow_summary["total_cost_usd"] = round(workflow_summary["total_cost_usd"], 4)

                logger.info(f"Workflow summary: {workflow_summary['total_tool_calls']} tool calls, {workflow_summary['total_tokens']} tokens, ${workflow_summary['total_cost_usd']}")

            except Exception as e:
                logger.error(f"Failed to aggregate workflow summary: {e}")
            finally:
                db.close()

            # 8. Format output for frontend display
            from services.output_formatter import format_workflow_output

            await event_bus.publish(channel, {
                "type": "status",
                "data": {
                    "status": "formatting",
                    "message": "Formatting output...",
                    "timestamp": datetime.utcnow().isoformat()
                }
            })

            formatted_output = format_workflow_output(
                raw_output=final_state,
                workflow_name=workflow.name,
                task_id=task_id
            )

            # Publish completion event with clean formatted output AND workflow summary
            await event_bus.publish(channel, {
                "type": "complete",
                "data": {
                    "status": "completed",
                    "workflow_id": workflow.id,
                    "task_id": task_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "formatted_output": formatted_output,
                    "workflow_summary": workflow_summary  # NEW: Comprehensive execution summary
                }
            })

            # Return formatted output, messages, AND workflow summary for task result
            return {
                "formatted_output": formatted_output,
                "messages": final_state.get("messages", []),
                "workflow_summary": workflow_summary
            }

        except asyncio.CancelledError as e:
            logger.info(f"Workflow execution cancelled for task {task_id}")

            # Publish cancellation event
            await event_bus.publish(channel, {
                "type": "error",
                "data": {
                    "error": "Workflow cancelled by user",
                    "error_type": "TaskCancelled",
                    "workflow_id": workflow.id,
                    "task_id": task_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            })

            return {
                "error": "Workflow cancelled by user",
                "workflow_status": "CANCELLED",
                "task_id": task_id
            }

        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)

            logger.error(f"Workflow execution failed: {e}", exc_info=True)

            # Enhanced diagnostics for recursion errors
            if "recursion" in error_msg.lower() or error_type == "GraphRecursionError":
                logger.error("=" * 80)
                logger.error("RECURSION LIMIT EXCEEDED - DIAGNOSTIC INFO")
                logger.error("=" * 80)
                logger.error(f"Workflow: {workflow.name} (ID: {workflow.id})")
                logger.error(f"Task: {task_id}")
                logger.error(f"Error: {error_msg}")
                logger.error("")

                # Analyze action history to find patterns
                if 'agent_action_history' in locals() and agent_action_history:
                    logger.error("EXECUTION PATTERN ANALYSIS:")
                    logger.error(f"Total actions before failure: {len(agent_action_history)}")

                    # Count actions per agent
                    from collections import Counter
                    agent_counts = Counter(action[0] for action in agent_action_history)
                    logger.error("Actions per agent:")
                    for agent, count in agent_counts.most_common():
                        logger.error(f"  - {agent}: {count} times")

                    # Show last 30 actions to reveal the loop pattern
                    logger.error("")
                    logger.error("Last 30 actions before error:")
                    for i, (agent, action_type, timestamp) in enumerate(agent_action_history[-30:], 1):
                        logger.error(f"  {i}. {agent} ({action_type})")

                    # Detect simple cycle patterns
                    if len(agent_action_history) >= 10:
                        last_10 = [action[0] for action in agent_action_history[-10:]]
                        if len(set(last_10)) <= 3:
                            logger.error("")
                            logger.error(f"🔍 LOOP DETECTED: Only {len(set(last_10))} unique agents in last 10 actions")
                            logger.error(f"   Pattern: {' → '.join(last_10)}")
                logger.error("")
                logger.error("POSSIBLE CAUSES:")
                logger.error("1. Agent system prompt lacks completion criteria")
                logger.error("2. Agent stuck in tool loop (calling same tool repeatedly)")
                logger.error("3. Workflow graph has a cycle without exit condition")
                logger.error("")
                logger.error("SOLUTIONS:")
                logger.error("1. ADD COMPLETION RULES TO SYSTEM PROMPT:")
                logger.error("   - 'Stop after 10-15 tool calls'")
                logger.error("   - 'Finish when you have sufficient information'")
                logger.error("   - 'Do not continue researching indefinitely'")
                logger.error("2. Check workflow graph for cycles - ensure conditional edges have proper exit")
                logger.error("3. Review browser console for repeated agent actions")
                logger.error("4. If task legitimately needs >40 steps, break it into smaller sub-tasks")
                logger.error("=" * 80)

                # Add helpful context to error message
                pattern_info = ""
                if 'agent_action_history' in locals() and agent_action_history:
                    last_agents = [action[0] for action in agent_action_history[-10:]]
                    pattern_info = f"\n5. Last 10 agents executed: {' → '.join(last_agents)}"

                error_msg = (
                    f"{error_msg}\n\n"
                    "💡 DIAGNOSIS HELP:\n"
                    "1. Check browser console for repeated agent actions (🤔 AGENT ACTION logs)\n"
                    "2. Verify workflow graph doesn't have infinite loops\n"
                    "3. Ensure conditional edges have proper exit conditions\n"
                    "4. Review agent system prompt for task completion logic"
                    f"{pattern_info}"
                )

                # Perform comprehensive diagnostics
                from core.utils.recursion_diagnostics import RecursionDiagnostics

                diagnostic_data = RecursionDiagnostics.analyze_recursion_error(
                    workflow=workflow,
                    task_id=task_id,
                    agent_action_history=agent_action_history if 'agent_action_history' in locals() else [],
                    workflow_state=workflow_state if 'workflow_state' in locals() else {},
                    error_msg=error_msg
                )

                # Update error message with detected issues
                if diagnostic_data.get("detected_issues"):
                    error_msg = (
                        f"{error_msg}\n\n"
                        "💡 DETECTED ISSUES:\n" +
                        "\n".join(f"  • {issue}" for issue in diagnostic_data["detected_issues"])
                    )

                # Emit special recursion_limit_hit event for HITL intervention with full diagnostics
                # DO NOT emit error event - let the workflow complete and show output
                await event_bus.publish(channel, {
                    "type": "recursion_limit_hit",
                    "data": {
                        "workflow_id": workflow.id,
                        "task_id": task_id,
                        "agent_name": agent_action_history[-1][0] if 'agent_action_history' in locals() and agent_action_history else "Unknown",
                        "iteration_count": len(agent_action_history) if 'agent_action_history' in locals() else 0,
                        "current_limit": 100,  # Match the actual workflow recursion_limit
                        "current_output": diagnostic_data.get("agent_output_preview", error_msg[:500]),
                        "diagnostics": diagnostic_data,  # Full diagnostic report
                        "timestamp": datetime.utcnow().isoformat()
                    }
                })
                logger.info(f"📢 Emitted recursion_limit_hit event - stream will continue")

            # Publish error event for ALL errors EXCEPT RecursionError
            # RecursionError should NOT stop the stream - user wants to see the output
            if "recursion" not in error_msg.lower() and error_type != "GraphRecursionError":
                await event_bus.publish(channel, {
                    "type": "error",
                    "data": {
                        "error": error_msg,
                        "error_type": error_type,
                        "workflow_id": workflow.id,
                        "task_id": task_id,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                })

            # ALWAYS emit complete event so UI knows workflow has finished
            # This ensures the spinner stops even on errors
            await event_bus.publish(channel, {
                "type": "complete",
                "data": {
                    "status": "error",
                    "error": error_msg,
                    "error_type": error_type,
                    "workflow_id": workflow.id,
                    "task_id": task_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            })

            return {
                "error": error_msg,
                "workflow_status": "FAILED",
                "task_id": task_id
            }

    async def _build_graph_from_workflow(
        self,
        workflow: WorkflowProfile
    ) -> StateGraph:
        """
        Build a LangGraph StateGraph from a WorkflowProfile.

        The WorkflowProfile.configuration contains the workflow data:
        {
            "nodes": [{"id": "node-1", "type": "agent", "config": {...}}],
            "edges": [{"id": "e1-2", "source": "node-1", "target": "node-2"}]
        }
        """
        logger.info(f"Building graph from workflow configuration with {len(workflow.configuration.get('nodes', []))} nodes")

        # Create StateGraph with SimpleWorkflowState
        graph = StateGraph(SimpleWorkflowState)

        # Get nodes and edges from configuration
        nodes = workflow.configuration.get("nodes", [])
        edges = workflow.configuration.get("edges", [])

        # DEBUG: Log what we're loading from database
        logger.info(f"[LOAD] ========== WORKFLOW CONFIGURATION DEBUG ==========")
        logger.info(f"[LOAD] Workflow configuration has {len(nodes)} nodes")
        logger.info(f"[LOAD] Raw nodes data: {nodes}")
        for node in nodes:
            logger.info(f"[LOAD] Processing node: {node}")
            node_id = node.get("id", "unknown")
            # Database stores config at TOP LEVEL: node["config"]
            # NOT nested in node["data"]["config"] (that's ReactFlow UI structure)
            node_config = node.get("config", {})
            logger.info(f"[LOAD] Node {node_id} - node_config keys: {list(node_config.keys())}")
            mcp_tools = node_config.get("mcp_tools", [])
            cli_tools = node_config.get("cli_tools", [])
            custom_tools = node_config.get("custom_tools", [])
            logger.info(f"[LOAD] Node {node_id} - Loaded from DB - mcp_tools: {mcp_tools}, cli_tools: {cli_tools}, custom_tools: {custom_tools}")

            # WARNING: If mcp_tools is empty but we expect tools, alert!
            if not mcp_tools and node_config.get("enable_memory") or node_config.get("enable_rag"):
                logger.warning(f"[LOAD] Node {node_id} - No MCP tools but memory/RAG enabled! Check frontend save logic.")
        logger.info(f"[LOAD] ==================================================")

        if not nodes:
            raise ValueError(f"Workflow '{workflow.name}' has no nodes defined")

        # Track special control nodes
        entry_point_override = None  # Track if user specified START_NODE
        terminal_nodes = []  # Track END_NODEs for special handling

        # Build node metadata map for callback handler (for proper event labeling)
        node_metadata = {}

        for node in nodes:
            node_id = node["id"]
            # Database stores config at top level: node["config"]
            node_type = node.get("type", "default")

            # CRITICAL: Also check node.data.agentType as fallback (same as main loop below)
            node_data = node.get("data", {})
            data_agent_type = node_data.get("agentType", "")
            agent_type = node_type if node_type != "default" else (data_agent_type or "default")

            # Get the actual display label:
            # 1. Try node data label (saved by frontend when user creates node)
            # 2. Fallback to type with underscores replaced by spaces and title cased
            agent_label = node_data.get("label") or agent_type.replace('_', ' ').title()

            # Skip non-executable control nodes (START and END are handled specially)
            if agent_type not in ['START_NODE', 'END_NODE']:
                # Normalize config to ensure backward compatibility with V1/V2 schemas
                raw_config = node.get("config", {})
                # Store config as-is (AgentFactory will normalize when needed)
                node_metadata[node_id] = {
                    "label": agent_label,
                    "agent_type": agent_type,
                    "config": raw_config
                }

        # Store in executor instance for callback access
        self.node_metadata = node_metadata
        logger.debug(f"Built node metadata for {len(node_metadata)} nodes")

        # DEBUG: Log extracted labels to verify they match canvas
        for node_id, metadata in node_metadata.items():
            logger.info(f"[NODE LABEL DEBUG] Node {node_id}: label='{metadata.get('label')}', type='{metadata.get('agent_type')}'")

        # Add nodes to graph
        for node in nodes:
            node_id = node["id"]
            # Database stores config at top level: node["config"]
            # NOT nested in node["data"]["config"]
            node_type = node.get("type", "default")

            # CRITICAL FIX: Also check node.data.agentType as fallback
            # Frontend saves agentType in node.data.agentType, and type at top level
            # But some edge cases may only have one or the other
            node_data = node.get("data", {})
            data_agent_type = node_data.get("agentType", "")

            # Use the first valid: node.type (if not default), then node.data.agentType
            agent_type = node_type if node_type != "default" else (data_agent_type or "default")

            # DEBUG: Log ALL node type info to diagnose END_NODE detection
            data_label = node_data.get("label", "NO_LABEL")
            logger.info(f"[NODE TYPE DEBUG] {node_id}: type={node_type}, data.agentType={data_agent_type}, resolved_type={agent_type}, label={data_label}")

            # Handle special START_NODE - don't add as node, use as entry point
            if agent_type == 'START_NODE':
                logger.info(f"Detected START_NODE: {node_id} - will determine entry point from connections")
                # Find the actual first node (what START_NODE points to)
                next_nodes = [e["target"] for e in edges if e["source"] == node_id]
                if next_nodes:
                    entry_point_override = next_nodes[0]
                    logger.debug(f"Entry point resolved from START_NODE to: {entry_point_override}")
                continue  # Skip adding START_NODE as actual node

            # Handle special END_NODE - don't add as node, LangGraph END is sufficient
            if agent_type == 'END_NODE':
                terminal_nodes.append(node_id)
                logger.info(f"✓ Detected END_NODE: {node_id} - will redirect connections to LangGraph END")
                continue  # Skip adding END_NODE as actual node

            # Create node executor function for all other node types
            node_executor = self._create_node_executor(node_id, agent_type, node)
            graph.add_node(node_id, node_executor)

            logger.info(f"Added node to graph: {node_id} (type: {agent_type})")

        # Set entry point (use START_NODE if specified, otherwise find node with no incoming edges)
        if nodes:
            if entry_point_override:
                first_node_id = entry_point_override
                logger.info(f"Using user-specified entry point: {first_node_id}")
            else:
                # Find the node with no incoming edges (the actual start of the workflow)
                regular_nodes = [n for n in nodes
                                if n.get("data", {}).get("label", "default")
                                not in ['START_NODE', 'END_NODE']]

                if not regular_nodes:
                    raise ValueError("Workflow must have at least one regular (non-control) node")

                # Get all target nodes (nodes that have incoming edges)
                target_node_ids = {e["target"] for e in edges if e["source"] != 'START_NODE'}

                # Find nodes with NO incoming edges - these are potential entry points
                entry_candidates = [n["id"] for n in regular_nodes if n["id"] not in target_node_ids]

                if entry_candidates:
                    # Use the first node with no incoming edges
                    first_node_id = entry_candidates[0]
                    logger.info(f"✓ Auto-detected entry point (no incoming edges): {first_node_id}")

                    if len(entry_candidates) > 1:
                        logger.warning(f"⚠️  Multiple entry points detected: {entry_candidates}")
                        logger.warning(f"   Using {first_node_id}. Consider adding a START_NODE for clarity.")
                else:
                    # Fallback: If all nodes have incoming edges (cycle), use first node
                    first_node_id = regular_nodes[0]["id"]
                    logger.warning(f"⚠️  All nodes have incoming edges (possible cycle)")
                    logger.warning(f"   Using first node as fallback: {first_node_id}")

            graph.add_edge(START, first_node_id)
            logger.info(f"✓ Workflow entry point: START -> {first_node_id}")

        # Group edges by source node to build routing maps for control nodes
        edges_by_source = {}
        for edge in edges:
            source = edge["source"]
            if source not in edges_by_source:
                edges_by_source[source] = []
            edges_by_source[source].append(edge)

        # Add edges to graph
        for source_id, source_edges in edges_by_source.items():
            # Get source node data
            source_node_data = next((n for n in nodes if n["id"] == source_id), {})
            source_type = source_node_data.get("type", source_node_data.get("data", {}).get("label", "default"))

            # Skip edges FROM START_NODE (already handled in entry point)
            if source_type == 'START_NODE':
                logger.debug(f"Skipping edges from START_NODE: {source_id}")
                continue

            # Check if source is a CONDITIONAL_NODE or LOOP_NODE
            if source_type == 'CONDITIONAL_NODE':
                # Build routing map for conditional edges
                routing_map = {}
                for edge in source_edges:
                    target = edge["target"]
                    # Get edge label/condition from edge data
                    edge_data = edge.get("data", {})
                    edge_label = edge_data.get("label", "default")

                    # Handle END_NODE targets
                    target_node_data = next((n for n in nodes if n["id"] == target), {})
                    target_type = target_node_data.get("type", target_node_data.get("data", {}).get("label", "default"))

                    if target_type == 'END_NODE' or target == "__END__":
                        routing_map[edge_label] = END
                    else:
                        routing_map[edge_label] = target

                    logger.debug(f"CONDITIONAL_NODE {source_id}: route '{edge_label}' -> {target}")

                # Create routing function for this conditional node
                def create_conditional_router(node_id_capture, route_map):
                    def route_conditional(state: SimpleWorkflowState) -> str:
                        # Get the route from state (set by CONDITIONAL_NODE executor)
                        route_key = state.get("conditional_route", "default")
                        target = route_map.get(route_key, route_map.get("default", END))
                        logger.debug(f"[Router] CONDITIONAL_NODE {node_id_capture} routing '{route_key}' to {target}")
                        return target
                    return route_conditional

                # Add conditional edges
                router_func = create_conditional_router(source_id, routing_map)
                graph.add_conditional_edges(source_id, router_func)
                logger.info(f"Added conditional edges for {source_id} with {len(routing_map)} routes")

            elif source_type == 'LOOP_NODE':
                # Build routing map for loop edges
                routing_map = {}
                for edge in source_edges:
                    target = edge["target"]
                    edge_data = edge.get("data", {})
                    edge_label = edge_data.get("label", "continue")

                    # Handle END_NODE targets
                    target_node_data = next((n for n in nodes if n["id"] == target), {})
                    target_type = target_node_data.get("type", target_node_data.get("data", {}).get("label", "default"))

                    if target_type == 'END_NODE' or target == "__END__":
                        routing_map[edge_label] = END
                    else:
                        routing_map[edge_label] = target

                    logger.debug(f"LOOP_NODE {source_id}: route '{edge_label}' -> {target}")

                # Create routing function for loop node
                def create_loop_router(node_id_capture, route_map):
                    def route_loop(state: SimpleWorkflowState) -> str:
                        # Get the route from state (set by LOOP_NODE executor)
                        route_key = state.get("loop_route", "continue")
                        target = route_map.get(route_key, route_map.get("continue", END))
                        logger.debug(f"[Router] LOOP_NODE {node_id_capture} routing '{route_key}' to {target}")
                        return target
                    return route_loop

                # Add conditional edges
                router_func = create_loop_router(source_id, routing_map)
                graph.add_conditional_edges(source_id, router_func)
                logger.info(f"Added loop edges for {source_id} with {len(routing_map)} routes")

            else:
                # Regular nodes: add direct edges
                for edge in source_edges:
                    target = edge["target"]

                    # Handle edges TO END_NODE
                    target_node_data = next((n for n in nodes if n["id"] == target), {})

                    # Check both node.type and node.data.agentType for END_NODE
                    target_node_type = target_node_data.get("type", "default")
                    target_data_agent_type = target_node_data.get("data", {}).get("agentType", "")
                    target_type = target_node_type if target_node_type != "default" else (target_data_agent_type or "default")

                    # DEBUG: Log target resolution for END_NODE detection
                    logger.info(f"[EDGE DEBUG] source={source_id}, target={target}, target_type={target_type}, node.type={target_node_type}, data.agentType={target_data_agent_type}")

                    if target_type == 'END_NODE' or target == "__END__":
                        target_node = END
                        logger.info(f"✓ Edge redirected to LangGraph END: {source_id} -> END")
                    else:
                        target_node = target

                    graph.add_edge(source_id, target_node)
                    logger.info(f"Added edge: {source_id} -> {target_node}")

        # Validate workflow structure - check for nodes with no outgoing edges
        # This is CRITICAL for catching workflow configuration issues
        if edges:
            # REMOVED AUTO-CONNECT LOGIC - IT WAS BREAKING WORKFLOWS
            # The graph already has all edges added correctly above.
            # Auto-connecting was creating duplicate/conflicting paths to END.
            # If a workflow needs an END_NODE, the user should add it explicitly.

            # Just log for diagnostics
            logger.debug(f"📊 EDGE VALIDATION: {len(edges)} edges processed")
        else:
            # No edges defined - this is also an error for multi-node workflows
            if len(regular_nodes) > 1:
                logger.error("❌ WORKFLOW ERROR: Multiple nodes but no edges defined!")
                logger.error("   Workflows need edges connecting nodes.")
                logger.error("   Please connect your nodes in the workflow canvas.")
                raise ValueError(
                    f"Workflow has {len(regular_nodes)} nodes but no edges. "
                    f"Please connect your nodes in the canvas."
                )
            elif len(regular_nodes) == 1:
                # Single node workflow - auto-connect to END is acceptable
                single_node_id = regular_nodes[0]["id"]
                graph.add_edge(single_node_id, END)
                logger.info(f"✓ Single-node workflow: {single_node_id} → END")

        return graph

    def _create_node_executor(
        self,
        node_id: str,
        agent_type: str,
        node_data: Dict[str, Any]
    ):
        """
        Create an executor function for a node.

        This function will be called by LangGraph when executing the node.
        """
        # Handle control nodes (START_NODE and END_NODE are filtered out in _build_graph_from_workflow)
        if agent_type in ['CHECKPOINT_NODE', 'OUTPUT_NODE', 'CONDITIONAL_NODE', 'APPROVAL_NODE', 'LOOP_NODE']:
            return self._create_control_node_executor(node_id, agent_type, node_data)

        # Handle TOOL_NODE (direct tool execution)
        if agent_type == 'TOOL_NODE':
            return self._create_tool_node_executor(node_id, node_data)

        async def node_executor(state: SimpleWorkflowState, config: dict = None) -> Dict[str, Any]:
            """Execute a single node in the workflow."""
            # Convert agent_type to human-readable name (e.g., "battlefield_6_expert" -> "Battlefield 6 Expert")
            display_name = agent_type.replace('_', ' ').title()
            logger.info(f"[{display_name}] Executing agent (node: {node_id})")

            try:
                # Get agent configuration from node data
                agent_config = node_data.get("config", {})
                model = agent_config.get("model", "gpt-4o-mini")
                temperature = agent_config.get("temperature", 0.7)
                system_prompt = agent_config.get("system_prompt", f"You are a {agent_type} agent.")

                # Get current messages from state
                messages = state.get("messages", [])

                # Get the user's query
                query = state.get("query", "")

                logger.info(f"[{display_name}] Received {len(messages)} messages from previous nodes")
                logger.info(f"[{display_name}] Query: {query[:100] if query else 'None'}...")

                # If no messages yet, create initial message from user's query
                if not messages and query:
                    messages = [HumanMessage(content=query)]
                    logger.info(f"[{display_name}] Created initial HumanMessage from query")

                # Create agent for this node using AgentFactory
                # Build agent_config dict matching AgentFactory.create_agent() API
                mcp_tools_list = agent_config.get("mcp_tools", [])
                cli_tools_list = agent_config.get("cli_tools", [])
                custom_tools_list = agent_config.get("custom_tools", [])

                logger.info(f"[{display_name}] Agent config - MCP tools: {mcp_tools_list}, CLI tools: {cli_tools_list}, Custom tools: {custom_tools_list}")

                # DIAGNOSTIC: Log if web_search appears unexpectedly
                if "web_search" in mcp_tools_list or "web" in mcp_tools_list:
                    logger.warning(f"⚠️  [{display_name}] HAS WEB_SEARCH TOOL - This may be unexpected!")
                    logger.warning(f"   Full agent_config keys: {list(agent_config.keys())}")
                    logger.warning(f"   mcp_tools from config: {agent_config.get('mcp_tools', [])}")

                full_agent_config = {
                    "model": model,
                    "temperature": temperature,
                    "system_prompt": system_prompt,
                    # Source of truth for built-in tools
                    "native_tools": agent_config.get("native_tools", []),
                    # Legacy/auxiliary tool groups
                    "mcp_tools": mcp_tools_list,
                    "cli_tools": cli_tools_list,
                    "custom_tools": custom_tools_list,
                    "enable_memory": agent_config.get("enable_memory", False),
                    "enable_rag": agent_config.get("enable_rag", False),
                    "max_tokens": agent_config.get("max_tokens"),
                    # Add middleware configuration if present (LangChain 1.0)
                    "middleware": agent_config.get("middleware", []),
                }

                # Shared setup: MCP manager and vector store
                from services.mcp_manager import get_mcp_manager
                from services.llama_config import get_vector_store

                mcp_manager = await get_mcp_manager()

                # Get vector store for RAG or Memory (if project_id available and either enabled)
                vector_store = None
                project_id_val = state.get("project_id")
                enable_rag = agent_config.get("enable_rag", False)
                enable_memory = agent_config.get("enable_memory", False)

                if project_id_val and (enable_rag or enable_memory):
                    try:
                        vector_store = get_vector_store(project_id_val)
                        logger.info(f"[Node: {node_id}] ✓ Vector store initialized (enable_rag={enable_rag}, enable_memory={enable_memory})")
                    except Exception as e:
                        logger.warning(f"[Node: {node_id}] Could not load vector store: {e}")

                # Check if this should be a DeepAgent (based on config flag)
                use_deepagents = agent_config.get("use_deepagents", False)

                if use_deepagents:
                    logger.info(f"[{display_name}] Creating DeepAgent with harness")

                    # Import DeepAgentFactory and models
                    from services.deepagent_factory import DeepAgentFactory
                    from models.deep_agent import DeepAgentConfig, MiddlewareConfig, SubAgentConfig

                    # Build DeepAgentConfig from agent_config
                    deep_agent_config = DeepAgentConfig(
                        model=model,
                        temperature=temperature,
                        max_tokens=agent_config.get("max_tokens"),
                        system_prompt=system_prompt,
                        tools=[],
                        mcp_tools=mcp_tools_list,
                        cli_tools=cli_tools_list,
                        custom_tools=custom_tools_list,
                        use_deepagents=True,
                        # Middleware: Enable filesystem and todo_list by default for DeepAgents
                        middleware=[
                            MiddlewareConfig(
                                type="filesystem",
                                enabled=True,
                                config={}
                            ),
                            MiddlewareConfig(
                                type="todo_list",
                                enabled=True,
                                config={}
                            )
                        ],
                        # Subagents can be added from agent_config if specified
                        subagents=agent_config.get("subagents", []),
                    )

                    # Build context with completion criteria
                    context_with_criteria = ""
                    if query:
                        context_with_criteria = f"""Task: {query}

CRITICAL - STOP CONDITIONS:
You MUST stop executing once you have completed the task and provided your output.
Do NOT continue iterating after your final response.
Do NOT loop or repeat actions unnecessarily.
When your work is complete, deliver the final result and END."""

                    # Create DeepAgent
                    agent_graph, tools, callbacks = await DeepAgentFactory.create_deep_agent(
                        config=deep_agent_config,
                        project_id=state.get("project_id", 0),
                        task_id=state.get("task_id", 0),
                        context=context_with_criteria,
                        mcp_manager=mcp_manager,
                        vector_store=vector_store
                    )

                    logger.info(f"[{display_name}] ✓ DeepAgent created with middleware and harness")

                else:
                    logger.info(f"[{display_name}] Creating regular agent")

                    # Build context with completion criteria
                    context_with_criteria = ""
                    if query:
                        context_with_criteria = f"""Task: {query}

CRITICAL - STOP CONDITIONS:
You MUST stop executing once you have completed the task and provided your output.
Do NOT continue iterating after your final response.
Do NOT loop or repeat actions unnecessarily.
When your work is complete, deliver the final result and END."""

                    # Create regular agent using AgentFactory
                    from core.agents.factory import AgentFactory

                    agent_graph, tools, callbacks = await AgentFactory.create_agent(
                        agent_config=full_agent_config,
                        project_id=state.get("project_id", 0),
                        task_id=state.get("task_id", 0),
                        context=context_with_criteria,
                        mcp_manager=mcp_manager,
                        vector_store=vector_store
                    )

                # Execute the agent graph with messages
                if messages:
                    # Get the parent config to inherit callbacks
                    parent_config = config if config else {}

                    # Build agent config with callbacks from parent AND agent
                    agent_config_dict = {
                        "configurable": {"thread_id": f"node_{node_id}_task_{state.get('task_id', 0)}"},
                        # Pass node_id in metadata so callback handler can look up agent_label
                        "metadata": {"node_id": node_id},
                        # Also add as tag for fallback lookup
                        "tags": [node_id],
                        # RECURSION LIMIT: Configurable per-node in frontend
                        # Get from agent config or use defaults
                        "recursion_limit": agent_config.get("recursion_limit", 75 if use_deepagents else 50)
                    }

                    # Combine callbacks from parent workflow AND agent factory
                    all_callbacks = []
                    if "callbacks" in parent_config:
                        parent_callbacks = parent_config["callbacks"]
                        if isinstance(parent_callbacks, list):
                            all_callbacks.extend(parent_callbacks)
                        else:
                            all_callbacks.append(parent_callbacks)

                    # Add agent's own callback handlers (for streaming events)
                    if callbacks:
                        if isinstance(callbacks, list):
                            all_callbacks.extend(callbacks)
                        else:
                            all_callbacks.append(callbacks)

                    if all_callbacks:
                        agent_config_dict["callbacks"] = all_callbacks
                        logger.debug(f"[{display_name}] Attached {len(all_callbacks)} callback handlers")

                    # RETRY LOOP for handling UNEXPECTED_TOOL_CALL (Gemini quirk)
                    # Gemini sometimes stops with "UNEXPECTED_TOOL_CALL" but doesn't execute the tool
                    # We catch this and force a retry with an explicit instruction
                    max_retries = 2
                    current_messages = messages

                    for attempt in range(max_retries + 1):
                        if attempt > 0:
                            logger.warning(f"[{display_name}] Retry attempt {attempt}/{max_retries} due to UNEXPECTED_TOOL_CALL")

                        # Try astream_events() first for streaming, fall back to ainvoke() if streaming unsupported
                        response = None
                        try:
                            # Use astream_events() to enable LLM token streaming callbacks
                            # This allows on_chat_model_stream events to fire for real-time thinking
                            async for event in agent_graph.astream_events(
                                {"messages": current_messages},
                                config=agent_config_dict,
                                version="v2"
                            ):
                                # astream_events yields ALL events including LLM tokens and state updates
                                # We only care about the final state for the agent response
                                kind = event.get("event")
                                if kind == "on_chain_end" and event.get("name") == "LangGraph":
                                    # Extract final state from the agent completion event
                                    response = event.get("data", {}).get("output")
                                # All other events (on_chat_model_stream, on_chain_start, etc.)
                                # are handled by the callback handler automatically
                        except Exception as stream_error:
                            # Streaming failed (e.g., OpenAI doesn't support streaming)
                            # Fall back to non-streaming execution
                            error_msg = str(stream_error)
                            if "stream" in error_msg.lower() or "unsupported" in error_msg.lower():
                                logger.warning(f"[{display_name}] Streaming not supported, falling back to non-streaming: {error_msg}")
                                # Use ainvoke() instead - no streaming but still works
                                response = await agent_graph.ainvoke(
                                    {"messages": current_messages},
                                    config=agent_config_dict
                                )
                            else:
                                # Different error - re-raise
                                raise

                        # Extract ONLY NEW AI messages from response
                        # The agent returns ALL messages (input + output), but LangGraph reducer
                        # appends them, so we only want the NEW messages not already in state
                        new_messages = []
                        all_response_messages = []

                        if isinstance(response, dict) and "messages" in response:
                            all_response_messages = response["messages"]
                            # Find messages that weren't in the input
                            input_message_count = len(current_messages)
                            new_messages = all_response_messages[input_message_count:]  # Only new messages

                        if not new_messages:
                            # Fallback: if no new messages detected, take last AI message
                            for msg in reversed(all_response_messages):
                                if hasattr(msg, '__class__') and 'AI' in msg.__class__.__name__:
                                    new_messages = [msg]
                                    break

                        # CHECK FOR UNEXPECTED_TOOL_CALL FAILURE
                        # If the last message has finish_reason='UNEXPECTED_TOOL_CALL' but NO tool calls were executed
                        # (meaning the agent stopped prematurely), we force a retry.
                        should_retry = False
                        if new_messages:
                            last_msg = new_messages[-1]
                            # Check response metadata for Gemini's specific error code
                            meta = getattr(last_msg, 'response_metadata', {})
                            finish_reason = meta.get('finish_reason')

                            # If Gemini says "UNEXPECTED_TOOL_CALL" but we didn't see a tool execution in the graph
                            # (Note: If tool WAS executed, the last message would be a ToolMessage or an AI message AFTER the tool)
                            if finish_reason == 'UNEXPECTED_TOOL_CALL':
                                logger.warning(f"[{display_name}] Detected UNEXPECTED_TOOL_CALL finish reason")

                                # Check if we actually have tool calls in the message
                                tool_calls = getattr(last_msg, 'tool_calls', [])
                                if not tool_calls:
                                    logger.warning(f"[{display_name}] Agent stopped with UNEXPECTED_TOOL_CALL but no tool_calls found. Retrying...")
                                    should_retry = True

                        # CHECK FOR FAKE IMAGE GENERATION (Hallucination)
                        # If the agent claims to have generated images but didn't call the tool
                        if not should_retry and new_messages:
                            last_msg = new_messages[-1]
                            last_content = str(last_msg.content) if hasattr(last_msg, 'content') else ""

                            # If the agent claims to have generated images but didn't call the tool
                            # We check for the specific marker [GENERATED IMAGES] which is in the system prompt
                            if "[GENERATED IMAGES]" in last_content and "image_generation" in str(agent_config.get("custom_tools", [])):
                                # Check if a tool was actually called in this turn
                                # We need to scan 'new_messages' for any ToolMessage or AIMessage with tool_calls
                                has_tool_calls = False
                                for msg in new_messages:
                                    if getattr(msg, 'tool_calls', []):
                                        has_tool_calls = True
                                        break
                                    if msg.__class__.__name__ == 'ToolMessage':
                                        has_tool_calls = True
                                        break

                                if not has_tool_calls:
                                    logger.warning(f"[{display_name}] Detected FAKE image generation (hallucination). Retrying...")
                                    should_retry = True
                                    retry_instruction = HumanMessage(content=
                                        "SYSTEM ERROR: You claimed to generate images but you did NOT call the 'image_generation' tool. "
                                        "You simply wrote a description. This is a failure. "
                                        "You MUST call the 'image_generation' tool to get a real URL. "
                                        "Try again and actually invoke the tool."
                                    )
                                    current_messages = list(all_response_messages) + [retry_instruction]
                                    continue

                        if should_retry and attempt < max_retries:
                            # Add a system/human message instructing the agent to fix its format
                            if not 'retry_instruction' in locals():
                                retry_instruction = HumanMessage(content=
                                    "SYSTEM ERROR: Your last response stopped with 'UNEXPECTED_TOOL_CALL'. "
                                    "You attempted to call a tool but the format was incorrect or not recognized. "
                                    "Please TRY AGAIN. Ensure you are using the correct tool calling format for 'image_generation'. "
                                    "Do not just describe the image - actually CALL the tool."
                                )
                            current_messages = list(all_response_messages) + [retry_instruction]
                            continue

                        # If we get here, we're done (success or max retries reached)
                        break

                else:
                    # Fallback: wrap response as AIMessage
                    new_messages = [AIMessage(content=str(response))]

                # Check for suspiciously short output (potential early termination)
                if new_messages:
                    last_content = ""
                    if hasattr(new_messages[-1], 'content'):
                        last_content = str(new_messages[-1].content)

                    # Warning conditions:
                    # 1. Output is very short (< 200 chars)
                    # 2. This is a downstream node (has previous messages)
                    # 3. Output contains meta-commentary keywords
                    is_short = len(last_content) < 200
                    is_downstream = len([m for m in messages if hasattr(m, '__class__') and 'AI' in m.__class__.__name__]) > 0
                    has_meta_commentary = any(keyword in last_content.lower() for keyword in [
                        '# executing', '# analysis', '# planning', 'based on the context provided',
                        'i will', 'i need to', 'let me'
                    ])

                    if is_short and is_downstream and has_meta_commentary:
                        warning_msg = (
                            f"⚠️ WARNING: {display_name} produced very short output ({len(last_content)} chars) "
                            f"that appears to be meta-commentary instead of actual content. "
                            f"This often indicates the agent's system prompt causes it to describe its task "
                            f"rather than execute it. Consider revising the system prompt to be more direct."
                        )
                        logger.warning(warning_msg)

                        # Emit warning event to frontend
                        from services.event_bus import get_event_bus
                        event_bus = get_event_bus()
                        channel = f"workflow:{state.get('workflow_id')}"
                        await event_bus.publish(channel, {
                            "type": "warning",
                            "data": {
                                "node": node_id,
                                "agent_label": display_name,
                                "warning_type": "short_output",
                                "message": f"{display_name} output may be incomplete (only {len(last_content)} characters)",
                                "suggestion": "Check the agent's system prompt - it may need to be more direct",
                                "timestamp": datetime.utcnow().isoformat()
                            }
                        })

                    logger.info(f"[{display_name}] Returning {len(new_messages)} new messages")

                    # Return new messages (reducer will append them)
                    return {
                        "messages": new_messages,
                        "current_node": node_id,
                        "last_agent_type": agent_type
                    }
                else:
                    logger.warning(f"[Node: {node_id}] No messages to process")
                    return {
                        "current_node": node_id,
                        "last_agent_type": agent_type
                    }

            except Exception as e:
                logger.error(f"[Node: {node_id}] Execution failed: {e}", exc_info=True)
                return {
                    "error_message": str(e),
                    "current_node": node_id
                }

        return node_executor

    def _create_control_node_executor(
        self,
        node_id: str,
        control_type: str,
        node_data: Dict[str, Any]
    ):
        """
        Create an executor function for control nodes.

        Control nodes handle workflow coordination, state management, and output formatting.
        """
        async def control_node_executor(state: SimpleWorkflowState) -> Dict[str, Any]:
            """Execute a control node."""
            logger.info(f"[Control Node: {node_id}] Executing {control_type}")

            try:
                if control_type == 'CHECKPOINT_NODE':
                    # Explicit checkpoint - state is automatically persisted by LangGraph
                    # Note: Only works if checkpointer is configured during compilation
                    checkpoint_data = {
                        "step": node_id,
                        "timestamp": datetime.utcnow().isoformat(),
                        "message_count": len(state.get("messages", []))
                    }
                    logger.info(f"[CHECKPOINT_NODE] Checkpoint marker set: {checkpoint_data}")
                    logger.debug(f"[CHECKPOINT_NODE] Note: Actual persistence depends on checkpointer configuration")

                    # Emit checkpoint event for frontend visualization
                    from execution_events import emit_checkpoint_event
                    await emit_checkpoint_event(
                        project_id=workflow.project_id,
                        task_id=task_id,
                        node_id=node_id,
                        checkpoint_data=checkpoint_data
                    )

                    return {
                        "current_step": node_id,
                        "workflow_status": "CHECKPOINTED",
                        "checkpoint_metadata": checkpoint_data
                    }

                elif control_type == 'OUTPUT_NODE':
                    # Format and return output
                    messages = state.get("messages", [])
                    message_count = len(messages)

                    output = {
                        "formatted_output": {
                            "messages": [msg.content if hasattr(msg, 'content') else str(msg) for msg in messages],
                            "workflow_status": state.get("workflow_status", "COMPLETED"),
                            "steps_completed": state.get("current_step", "unknown")
                        }
                    }

                    logger.info(f"[OUTPUT_NODE] Output formatted successfully ({message_count} messages)")
                    if message_count == 0:
                        logger.warning(f"[OUTPUT_NODE] No messages in output")

                    return {
                        "current_step": node_id,
                        **output
                    }

                elif control_type == 'CONDITIONAL_NODE':
                    # Conditional routing based on state evaluation
                    config = node_data.get("config", {})
                    condition_expr = config.get("condition", "").strip()
                    routing_map = config.get("routing_map", {})

                    logger.info(f"[CONDITIONAL_NODE] Evaluating condition: '{condition_expr}'")

                    # Default route if no condition specified
                    if not condition_expr:
                        logger.warning(f"[CONDITIONAL_NODE] No condition expression provided - using default route")
                        condition_result = routing_map.get("default", "default")
                        return {
                            "current_step": node_id,
                            "conditional_route": condition_result
                        }

                    # Evaluate condition expression safely
                    try:
                        # Build safe evaluation context with state values
                        eval_context = {
                            "state": state,
                            # Common helper functions
                            "len": len,
                            "str": str,
                            "int": int,
                            "float": float,
                            "bool": bool,
                            "list": list,
                            "dict": dict,
                            # Math operations
                            "abs": abs,
                            "min": min,
                            "max": max,
                            "sum": sum,
                        }

                        # Evaluate the condition expression
                        # Supports expressions like: state.get("retry_count", 0) < 3
                        #                           state.get("validation_passed") == True
                        #                           len(state.get("messages", [])) > 0
                        result = eval(condition_expr, {"__builtins__": {}}, eval_context)

                        # Convert to boolean
                        condition_met = bool(result)

                        logger.info(f"[CONDITIONAL_NODE] Condition '{condition_expr}' evaluated to: {condition_met}")

                        # Determine route based on condition result
                        # routing_map should have "true" and "false" keys mapping to node IDs
                        if condition_met:
                            route_key = "true"
                        else:
                            route_key = "false"

                        # Get target node from routing map, fallback to default
                        target_route = routing_map.get(route_key, routing_map.get("default", "default"))

                        logger.debug(f"[CONDITIONAL_NODE] Routing to: {target_route} (condition: {condition_met})")

                        return {
                            "current_step": node_id,
                            "conditional_route": target_route,
                            "condition_result": condition_met
                        }

                    except Exception as e:
                        logger.error(f"[CONDITIONAL_NODE] Failed to evaluate condition '{condition_expr}': {e}")
                        # Fallback to default route on error
                        fallback_route = routing_map.get("default", "default")
                        logger.warning(f"[CONDITIONAL_NODE] Using fallback route: {fallback_route}")
                        return {
                            "current_step": node_id,
                            "conditional_route": fallback_route,
                            "condition_error": str(e)
                        }

                elif control_type == 'LOOP_NODE':
                    # Loop control with iteration tracking
                    config = node_data.get("config", {})
                    max_iterations = config.get("max_iterations", 10)
                    exit_condition = config.get("exit_condition", "").strip()
                    loop_target = config.get("loop_target")  # Node to loop back to

                    # Initialize loop state if not present
                    loop_iterations = state.get("loop_iterations", {})
                    current_iteration = loop_iterations.get(node_id, 0)

                    logger.info(f"[LOOP_NODE] Iteration {current_iteration + 1}/{max_iterations}")

                    # Increment iteration count
                    current_iteration += 1
                    loop_iterations[node_id] = current_iteration

                    # Check exit conditions
                    should_exit = False
                    exit_reason = None

                    # 1. Check max iterations
                    if current_iteration >= max_iterations:
                        should_exit = True
                        exit_reason = f"max_iterations ({max_iterations}) reached"
                        logger.info(f"[LOOP_NODE] Exiting loop: {exit_reason}")

                    # 2. Check exit condition expression (if provided)
                    elif exit_condition:
                        try:
                            # Build safe evaluation context
                            eval_context = {
                                "state": state,
                                "iteration": current_iteration,
                                "max_iterations": max_iterations,
                                # Helper functions
                                "len": len,
                                "str": str,
                                "int": int,
                                "float": float,
                                "bool": bool,
                                "abs": abs,
                                "min": min,
                                "max": max,
                                "sum": sum,
                            }

                            # Evaluate exit condition
                            result = eval(exit_condition, {"__builtins__": {}}, eval_context)
                            should_exit = bool(result)

                            if should_exit:
                                exit_reason = f"exit_condition '{exit_condition}' evaluated to True"
                                logger.info(f"[LOOP_NODE] Exiting loop: {exit_reason}")

                        except Exception as e:
                            logger.error(f"[LOOP_NODE] Failed to evaluate exit condition '{exit_condition}': {e}")
                            # Don't exit on error, continue looping (safer than infinite loop)
                            should_exit = False

                    # Determine routing
                    if should_exit:
                        loop_route = "exit"
                        logger.debug(f"[LOOP_NODE] Routing to exit (reason: {exit_reason})")
                    else:
                        loop_route = "continue"
                        logger.debug(f"[LOOP_NODE] Routing to continue (iteration {current_iteration})")

                    return {
                        "current_step": node_id,
                        "loop_iterations": loop_iterations,
                        "loop_route": loop_route,
                        "loop_iteration": current_iteration,
                        "loop_should_exit": should_exit,
                        "loop_exit_reason": exit_reason
                    }

                elif control_type == 'APPROVAL_NODE':
                    # Human-in-the-loop approval gate
                    approval_context = {
                        "node_id": node_id,
                        "current_step": state.get("current_step"),
                        "message_count": len(state.get("messages", []))
                    }
                    logger.info(f"[APPROVAL_NODE] Workflow paused for human approval: {approval_context}")
                    logger.debug(f"[APPROVAL_NODE] This node requires 'interrupt_before' compilation config")
                    return {
                        "current_step": node_id,
                        "workflow_status": "AWAITING_APPROVAL",
                        "requires_human_approval": True,
                        "approval_context": approval_context
                    }

                else:
                    valid_types = ['CHECKPOINT_NODE', 'OUTPUT_NODE', 'CONDITIONAL_NODE', 'APPROVAL_NODE', 'LOOP_NODE']
                    logger.error(
                        f"[Control Node: {node_id}] Unknown control type: '{control_type}'. "
                        f"Valid types: {valid_types}"
                    )
                    return {
                        "current_step": node_id,
                        "error_message": f"Unknown control node type: {control_type}"
                    }

            except Exception as e:
                logger.error(f"[Control Node: {node_id}] Execution failed: {e}", exc_info=True)
                return {
                    "error_message": str(e),
                    "current_step": node_id,
                    "workflow_status": "FAILED"
                }

        return control_node_executor

    def _create_tool_node_executor(
        self,
        node_id: str,
        node_data: Dict[str, Any]
    ):
        """
        Create an executor for TOOL_NODE that directly executes a tool.

        Args:
            node_id: Unique node identifier
            node_data: Node configuration including tool_type, tool_id, and tool_params

        Returns:
            Async function that executes the tool
        """
        async def tool_node_executor(state: SimpleWorkflowState, config: dict = None) -> Dict[str, Any]:
            """Execute a tool node."""
            from core.workflows.nodes import execute_tool_node

            # Get tool configuration from node_data
            node_config = node_data.get("config", {})

            logger.info(f"[TOOL_NODE {node_id}] Executing with config: {node_config}")

            # Call the tool execution function
            result = await execute_tool_node(
                state=state,
                config=config,
                node_tool_config=node_config
            )

            return {
                "current_step": node_id,
                **result
            }

        return tool_node_executor

    async def _validate_and_init_tools(
        self,
        workflow: WorkflowProfile,
        channel: str,
        event_bus
    ) -> None:
        """
        Validate and pre-initialize tools before workflow execution.

        This ensures all tools (especially async ones like Playwright browser) are
        ready before the workflow starts, preventing mid-execution failures.

        Args:
            workflow: The workflow profile to validate
            channel: SSE channel for event publishing
            event_bus: Event bus for publishing progress

        Raises:
            ValueError: If any tools are missing or fail to initialize
        """
        logger.info("Starting tool validation and pre-initialization...")

        # Extract all tools from workflow nodes
        nodes = workflow.configuration.get("nodes", [])
        all_tools = set()
        browser_needed = False

        for node in nodes:
            # Skip control nodes
            node_type = node.get("type", "default")
            if node_type in ['START_NODE', 'END_NODE', 'CHECKPOINT_NODE', 'OUTPUT_NODE',
                            'CONDITIONAL_NODE', 'APPROVAL_NODE']:
                continue

            # Get tools from node config
            node_config = node.get("config", {})
            native_tools = node_config.get("native_tools", [])
            mcp_tools = node_config.get("mcp_tools", [])
            cli_tools = node_config.get("cli_tools", [])
            custom_tools = node_config.get("custom_tools", [])

            # SAFETY: Filter out enable_memory and enable_rag - they're config flags, not tools
            # This handles old workflows saved before the frontend fix
            native_tools = [t for t in native_tools if t not in ['enable_memory', 'enable_rag']]
            mcp_tools = [t for t in mcp_tools if t not in ['enable_memory', 'enable_rag']]
            cli_tools = [t for t in cli_tools if t not in ['enable_memory', 'enable_rag']]
            custom_tools = [t for t in custom_tools if t not in ['enable_memory', 'enable_rag']]

            # Collect all tools
            for tool in native_tools + mcp_tools + cli_tools + custom_tools:
                all_tools.add(tool)
                if tool == "browser":
                    browser_needed = True

        if not all_tools:
            logger.info("No tools required for this workflow")
            return

        logger.info(f"Workflow requires tools: {list(all_tools)}")

        # Publish validation progress
        await event_bus.publish(channel, {
            "type": "status",
            "data": {
                "status": "validating_tools",
                "message": f"Validating {len(all_tools)} tool(s)...",
                "tools": list(all_tools),
                "timestamp": datetime.utcnow().isoformat()
            }
        })

        # Get available tool names from native_tools
        from tools.native_tools import get_available_tool_names, TOOL_NAME_MAP
        available_tools = get_available_tool_names()

        # Apply legacy tool name mapping for backward compatibility
        # This allows old workflows/agents with names like "sequential_thinking" to work
        mapped_tools = set()
        for tool in all_tools:
            # Map old name to new name if it exists in the legacy map
            mapped_tool = TOOL_NAME_MAP.get(tool, tool)
            mapped_tools.add(mapped_tool)
            if tool != mapped_tool:
                logger.info(f"Mapped legacy tool name '{tool}' -> '{mapped_tool}'")

        # Check if all requested tools (after mapping) are available
        missing_tools = []
        for tool in mapped_tools:
            if tool not in available_tools:
                missing_tools.append(tool)

        if missing_tools:
            error_msg = f"Missing tools: {missing_tools}. Available tools: {available_tools}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info("✓ All requested tools are available in registry")

        # Pre-initialize Playwright browser if needed
        if browser_needed:
            logger.info("Browser tools requested - pre-initializing Playwright...")

            await event_bus.publish(channel, {
                "type": "status",
                "data": {
                    "status": "initializing_browser",
                    "message": "Initializing Playwright browser (this may take a few seconds)...",
                    "timestamp": datetime.utcnow().isoformat()
                }
            })

            try:
                from tools.native_tools import load_playwright_tools

                # This will initialize the browser and return the toolkit
                browser_tools = await load_playwright_tools()

                if not browser_tools:
                    raise ValueError("Playwright browser initialization returned no tools")

                logger.info(f"✓ Playwright browser initialized successfully ({len(browser_tools)} tools)")

                await event_bus.publish(channel, {
                    "type": "status",
                    "data": {
                        "status": "browser_ready",
                        "message": f"Playwright browser ready ({len(browser_tools)} tools available)",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                })

            except Exception as e:
                error_msg = f"Failed to initialize Playwright browser: {str(e)}"
                logger.error(error_msg)
                logger.error("Make sure Playwright is installed: playwright install chromium")
                raise ValueError(error_msg)

        # All tools validated and ready
        logger.info("✓ Tool validation complete - all tools ready")
        await event_bus.publish(channel, {
            "type": "status",
            "data": {
                "status": "tools_validated",
                "message": "All tools validated and ready",
                "timestamp": datetime.utcnow().isoformat()
            }
        })


# Global executor instance
_executor: Optional[SimpleWorkflowExecutor] = None


def get_executor() -> SimpleWorkflowExecutor:
    """Get or create the global executor instance."""
    global _executor
    if _executor is None:
        _executor = SimpleWorkflowExecutor()
    return _executor
