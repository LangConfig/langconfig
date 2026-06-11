"""Normalized stream adapter helpers.

LangConfig keeps LangGraph/Deep Agents streaming as the source of truth. This
module provides a small AG-UI-like boundary so API routes can normalize v2/v3
events without committing the public SSE contract to AG-UI yet.
"""

from typing import Any, Dict, Optional


def normalize_stream_event(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Map LangChain/LangGraph stream events into a small internal shape."""
    event_type = event.get("event")
    method = event.get("method")
    data = event.get("data") or event.get("params", {}).get("data") or {}
    params = event.get("params") or {}
    namespace = params.get("namespace") or []

    if event_type in ("on_chat_model_stream", "on_llm_stream"):
        chunk = data.get("chunk")
        content = getattr(chunk, "content", None) or data.get("content") or data.get("token") or ""

        # Anthropic (and other providers) stream content as block lists.
        # Partition blocks: text -> text_delta, thinking -> thinking_delta,
        # server_tool_use / *_tool_result -> synthesized tool events so
        # server-side tools render with the existing tool chips.
        if isinstance(content, list):
            text_parts = []
            thinking_parts = []
            server_tool_event = None
            for block in content:
                if not isinstance(block, dict):
                    if block:
                        text_parts.append(str(block))
                    continue
                block_type = block.get("type")
                if block_type == "thinking":
                    thinking_text = block.get("thinking") or ""
                    if thinking_text:
                        thinking_parts.append(thinking_text)
                elif block_type == "server_tool_use":
                    server_tool_event = {
                        "type": "tool_started",
                        "tool_name": f"{block.get('name') or 'server_tool'} (anthropic)",
                        "input": block.get("input") or block.get("partial_json"),
                        "namespace": namespace,
                    }
                elif block_type in ("web_search_tool_result", "web_fetch_tool_result"):
                    tool_name = "web_search" if block_type == "web_search_tool_result" else "web_fetch"
                    server_tool_event = {
                        "type": "tool_completed",
                        "tool_name": f"{tool_name} (anthropic)",
                        "output": None,  # server tool results can be large; omit payload
                        "namespace": namespace,
                    }
                else:
                    # text / text_delta blocks (ignore signatures, tool_use deltas)
                    block_text = block.get("text") or ""
                    if block_text:
                        text_parts.append(block_text)

            if text_parts:
                return {"type": "text_delta", "text": "".join(text_parts), "namespace": namespace}
            if thinking_parts:
                return {"type": "thinking_delta", "text": "".join(thinking_parts), "namespace": namespace}
            if server_tool_event:
                return server_tool_event
            return None

        return {"type": "text_delta", "text": content, "namespace": namespace}

    if method == "messages" and data.get("event") == "content-block-delta":
        delta = data.get("delta") or {}
        if delta.get("type") in ("text", "text-delta"):
            return {"type": "text_delta", "text": delta.get("text", ""), "namespace": namespace}

    if event_type in ("on_tool_start", "tool_start"):
        return {
            "type": "tool_started",
            "tool_name": data.get("name") or event.get("name") or data.get("tool_name"),
            "input": data.get("input") or data.get("inputs"),
            "namespace": namespace,
        }

    if method == "tools" and data.get("event") == "tool-started":
        return {
            "type": "tool_started",
            "tool_name": data.get("tool_name"),
            "input": data.get("input"),
            "namespace": namespace,
        }

    if event_type == "on_tool_end":
        return {
            "type": "tool_completed",
            "tool_name": data.get("name") or event.get("name") or data.get("tool_name"),
            "output": data.get("output"),
            "namespace": namespace,
        }

    if method == "tools" and data.get("event") in ("tool-finished", "tool-error"):
        return {
            "type": "tool_completed" if data.get("event") == "tool-finished" else "tool_error",
            "tool_name": data.get("tool_name"),
            "output": data.get("output"),
            "error": data.get("error"),
            "namespace": namespace,
        }

    if method == "lifecycle":
        return {
            "type": f"lifecycle_{data.get('event', 'unknown')}",
            "namespace": namespace,
            "graph_name": data.get("graph_name"),
            "error": data.get("error"),
        }

    return None
