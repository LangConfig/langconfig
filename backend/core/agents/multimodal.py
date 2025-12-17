# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Multimodal Input Utilities

Provides functionality for handling multimodal inputs (images, documents, videos, audio)
in LangChain agents. Converts various attachment formats to LangChain message content blocks.
"""

import base64
import httpx
import logging
from typing import List, Dict, Any, Optional, Union

from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


# Supported attachment types
SUPPORTED_ATTACHMENT_TYPES = ["image", "document", "video", "audio"]

# MIME type mappings for common extensions
MIME_TYPE_MAP = {
    # Images
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "svg": "image/svg+xml",
    # Documents
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
    "md": "text/markdown",
    # Videos
    "mp4": "video/mp4",
    "webm": "video/webm",
    "mov": "video/quicktime",
    # Audio
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "ogg": "audio/ogg",
}


def get_mime_type(url_or_path: str, explicit_type: Optional[str] = None) -> str:
    """
    Determine MIME type from URL/path extension or explicit type.

    Args:
        url_or_path: URL or file path
        explicit_type: Explicitly provided MIME type

    Returns:
        MIME type string
    """
    if explicit_type:
        return explicit_type

    # Extract extension from URL or path
    ext = url_or_path.rsplit(".", 1)[-1].lower() if "." in url_or_path else ""
    return MIME_TYPE_MAP.get(ext, "application/octet-stream")


async def fetch_url_as_base64(url: str, timeout: float = 30.0) -> Optional[str]:
    """
    Fetch content from URL and convert to base64.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds

    Returns:
        Base64-encoded content or None if failed
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            return base64.b64encode(response.content).decode("utf-8")
    except Exception as e:
        logger.warning(f"Failed to fetch URL {url}: {e}")
        return None


def attachment_to_content_block(attachment: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Convert an attachment dictionary to a LangChain content block.

    Attachment format:
    {
        "type": "image" | "document" | "video" | "audio",
        "url": "https://..." or "data:image/png;base64,...",
        "data": "<base64 string>" (alternative to url),
        "mime_type": "image/png" (optional),
        "name": "filename.png" (optional),
        "description": "Image description" (optional)
    }

    Returns:
        LangChain content block dict or None if invalid
    """
    import base64

    attachment_type = attachment.get("type", "image")
    url = attachment.get("url")
    data = attachment.get("data")
    mime_type = attachment.get("mime_type", "")
    name = attachment.get("name", "attachment")
    description = attachment.get("description", "")

    logger.info(f"Processing attachment: type={attachment_type}, name={name}, mime_type={mime_type}, has_url={bool(url)}, has_data={bool(data)}")

    # Get MIME type from name if not provided
    if not mime_type and url:
        mime_type = get_mime_type(url)
    elif not mime_type and name:
        mime_type = get_mime_type(name)
    elif not mime_type:
        mime_type = "application/octet-stream"

    # Determine if this is a text document that should be decoded and included as text
    text_mime_types = [
        "text/plain", "text/markdown", "text/html", "text/css", "text/csv",
        "application/json", "application/xml", "text/xml"
    ]
    is_text_document = (
        attachment_type == "document" or
        mime_type in text_mime_types or
        any(name.lower().endswith(ext) for ext in ['.md', '.txt', '.json', '.xml', '.csv', '.html', '.css', '.py', '.js', '.ts'])
    )

    # Determine if this is an image that can use image_url
    image_mime_types = ["image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml"]
    is_image = mime_type in image_mime_types or mime_type.startswith("image/")

    logger.info(f"Attachment {name}: is_text_document={is_text_document}, is_image={is_image}, mime_type={mime_type}")

    # Handle text documents - decode base64 and return as text content
    if is_text_document and data:
        try:
            # Decode base64 to get the text content
            clean_data = str(data).strip()
            # Remove potential quotes
            while clean_data.startswith("'") or clean_data.startswith('"'):
                clean_data = clean_data[1:]
            while clean_data.endswith("'") or clean_data.endswith('"'):
                clean_data = clean_data[:-1]

            decoded_text = base64.b64decode(clean_data).decode('utf-8')
            logger.info(f"Attachment {name}: Decoded text document ({len(decoded_text)} chars)")

            # Return as text content block with document context
            return {
                "type": "text",
                "text": f"--- Document: {name} ---\n{decoded_text}\n--- End of {name} ---"
            }
        except Exception as e:
            logger.warning(f"Attachment {name}: Failed to decode as text: {e}")
            # Fall through to try other handling

    # Handle URLs (for images)
    if url:
        if not is_image:
            logger.warning(f"Attachment {name}: URL provided for non-image type {mime_type}, skipping")
            return None

        if url.startswith("data:"):
            logger.debug(f"Attachment {name}: Using existing data URI")
            return {
                "type": "image_url",
                "image_url": {"url": url}
            }
        elif url.startswith("http://") or url.startswith("https://"):
            logger.debug(f"Attachment {name}: Using HTTP URL")
            return {
                "type": "image_url",
                "image_url": {"url": url}
            }
        else:
            logger.warning(f"Attachment {name}: Invalid URL format: {url[:50]}...")
            return None

    # Handle base64 data for images
    elif data and is_image:
        # Clean the data
        clean_data = str(data).strip()
        while clean_data.startswith("'") or clean_data.startswith('"'):
            clean_data = clean_data[1:]
        while clean_data.endswith("'") or clean_data.endswith('"'):
            clean_data = clean_data[:-1]
        clean_data = clean_data.strip()

        # Check if data is already a complete data URI
        if clean_data.startswith("data:"):
            logger.debug(f"Attachment {name}: Data already contains data: prefix")
            return {
                "type": "image_url",
                "image_url": {"url": clean_data}
            }

        # Build the data URI
        data_uri = f"data:{mime_type};base64,{clean_data}"
        logger.info(f"Attachment {name}: Created image data URI, data_length={len(clean_data)}")

        return {
            "type": "image_url",
            "image_url": {"url": data_uri}
        }

    logger.warning(f"Attachment {name}: Could not process (type={attachment_type}, mime={mime_type})")
    return None


def convert_attachments_to_content_blocks(
    attachments: List[Dict[str, Any]],
    filter_types: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Convert a list of attachments to LangChain content blocks.

    Args:
        attachments: List of attachment dictionaries
        filter_types: Optional list of types to include (e.g., ["image"])

    Returns:
        List of LangChain content block dictionaries
    """
    content_blocks = []

    for attachment in attachments:
        # Filter by type if specified
        if filter_types:
            att_type = attachment.get("type", "image")
            if att_type not in filter_types:
                logger.debug(f"Skipping attachment type {att_type} (not in filter)")
                continue

        block = attachment_to_content_block(attachment)
        if block:
            content_blocks.append(block)

    return content_blocks


def create_multimodal_message(
    text_content: str,
    attachments: Optional[List[Dict[str, Any]]] = None,
    filter_types: Optional[List[str]] = None
) -> HumanMessage:
    """
    Create a LangChain HumanMessage with multimodal content.

    For models that support multimodal input (GPT-4 Vision, Claude 3, Gemini, etc.),
    the content is structured as a list of content blocks:
    [
        {"type": "text", "text": "..."},
        {"type": "image_url", "image_url": {"url": "..."}},
        ...
    ]

    For models that don't support multimodal, falls back to text-only message.

    Args:
        text_content: The text content of the message
        attachments: Optional list of attachment dictionaries
        filter_types: Optional list of attachment types to include

    Returns:
        HumanMessage with multimodal content
    """
    if not attachments:
        # No attachments - simple text message
        return HumanMessage(content=text_content)

    # Build multimodal content
    content_blocks: List[Union[Dict[str, Any], str]] = []

    # Add text content first
    if text_content:
        content_blocks.append({"type": "text", "text": text_content})

    # Add attachment content blocks
    attachment_blocks = convert_attachments_to_content_blocks(attachments, filter_types)
    content_blocks.extend(attachment_blocks)

    if len(content_blocks) == 1 and isinstance(content_blocks[0], dict) and content_blocks[0].get("type") == "text":
        # Only text - use simple string content
        return HumanMessage(content=text_content)

    logger.info(f"Created multimodal message with {len(content_blocks)} content blocks ({len(attachment_blocks)} attachments)")
    return HumanMessage(content=content_blocks)


def check_model_multimodal_support(model_name: str) -> Dict[str, bool]:
    """
    Check what multimodal capabilities a model supports.

    Returns dict with capability flags:
    {
        "vision": True/False,
        "audio": True/False,
        "video": True/False,
        "documents": True/False
    }
    """
    model_lower = model_name.lower()

    # Default capabilities
    capabilities = {
        "vision": False,
        "audio": False,
        "video": False,
        "documents": False
    }

    # Claude models
    if "claude" in model_lower:
        if "3" in model_lower or "4" in model_lower:
            capabilities["vision"] = True
            capabilities["documents"] = True  # PDF support

    # GPT-4 Vision models
    if "gpt-4" in model_lower and ("vision" in model_lower or "turbo" in model_lower or "o" in model_lower):
        capabilities["vision"] = True

    # GPT-4o supports multiple modalities
    if "gpt-4o" in model_lower:
        capabilities["vision"] = True
        capabilities["audio"] = True

    # Gemini models
    if "gemini" in model_lower:
        capabilities["vision"] = True
        capabilities["documents"] = True
        if "pro" in model_lower or "ultra" in model_lower or "2" in model_lower:
            capabilities["video"] = True
            capabilities["audio"] = True

    return capabilities
