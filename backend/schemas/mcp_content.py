# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
MCP Multimodal Content Schemas

Defines Pydantic models for MCP (Model Context Protocol) multimodal content blocks.
MCP tools can return content in various formats: text, images, audio, and embedded resources.

Based on LangChain MCP adapters standard content block format:
https://docs.langchain.com/oss/python/langchain/mcp#multimodal-tool-content
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Union, Literal, Any, Dict


class MCPTextContent(BaseModel):
    """Text content block from MCP tool result."""
    type: Literal["text"] = "text"
    text: str = Field(..., description="The text content")


class MCPImageContent(BaseModel):
    """Image content block from MCP tool result (e.g., screenshots, generated images)."""
    type: Literal["image"] = "image"
    data: str = Field(..., description="Base64-encoded image data")
    mimeType: str = Field(default="image/png", description="MIME type (image/png, image/jpeg, etc.)")
    alt_text: Optional[str] = Field(None, description="Alternative text description")


class MCPAudioContent(BaseModel):
    """Audio content block from MCP tool result."""
    type: Literal["audio"] = "audio"
    data: str = Field(..., description="Base64-encoded audio data")
    mimeType: str = Field(default="audio/wav", description="MIME type (audio/wav, audio/mp3, etc.)")
    duration_seconds: Optional[float] = Field(None, description="Audio duration in seconds")


class MCPResourceContent(BaseModel):
    """Embedded resource content block from MCP tool result."""
    type: Literal["resource"] = "resource"
    uri: str = Field(..., description="Resource URI")
    mimeType: Optional[str] = Field(None, description="MIME type of the resource")
    blob: Optional[str] = Field(None, description="Base64-encoded binary content")
    text: Optional[str] = Field(None, description="Text content if applicable")


# Union type for all MCP content block types
MCPContentBlock = Union[MCPTextContent, MCPImageContent, MCPAudioContent, MCPResourceContent]


class MCPMultimodalResult(BaseModel):
    """
    Parsed multimodal result from MCP tool invocation.

    Separates content (for LLM context) from artifacts (for UI display only).
    This follows LangChain's outputHandling pattern where artifacts are not
    sent to the LLM but are available for the UI to display.
    """
    content: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Content blocks sent to LLM context"
    )
    artifacts: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Content blocks for UI display only (not sent to LLM)"
    )
    has_multimodal: bool = Field(
        default=False,
        description="Whether the result contains non-text content (images, audio, etc.)"
    )
    is_error: bool = Field(
        default=False,
        description="Whether the result represents an error"
    )


def is_multimodal_type(content_type: str) -> bool:
    """Check if a content type is multimodal (non-text)."""
    return content_type in ("image", "audio", "resource", "file")


def get_text_from_content_blocks(blocks: List[Dict[str, Any]]) -> str:
    """Extract all text content from a list of content blocks."""
    text_parts = []
    for block in blocks:
        if block.get("type") == "text":
            text_parts.append(block.get("text", ""))
    return "\n".join(text_parts)


def get_images_from_content_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract all image blocks from a list of content blocks."""
    return [block for block in blocks if block.get("type") == "image"]


def content_block_to_data_uri(block: Dict[str, Any]) -> Optional[str]:
    """
    Convert an image or audio content block to a data URI.

    Returns:
        Data URI string (e.g., "data:image/png;base64,iVBORw0...") or None
    """
    block_type = block.get("type")
    if block_type not in ("image", "audio"):
        return None

    data = block.get("data")
    mime_type = block.get("mimeType", "application/octet-stream")

    if not data:
        return None

    return f"data:{mime_type};base64,{data}"
