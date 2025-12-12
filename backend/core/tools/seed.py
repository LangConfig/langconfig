# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Custom Tool Seeding - Pre-populate default custom tools for new users.

This module provides functions to seed the database with commonly-used
custom tool configurations so users don't have to create them from scratch.
"""

import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from models.custom_tool import CustomTool, ToolType, ToolTemplateType

logger = logging.getLogger(__name__)


# Default tools to seed for new installations
DEFAULT_CUSTOM_TOOLS: List[Dict[str, Any]] = [
    {
        "tool_id": "image_generation",
        "name": "Nano Banana Pro (Image Generator)",
        "description": "AI image generation using Gemini 3 Pro Image - Google's best model with 2K/4K output, text rendering, and character consistency. Ultra-fast generation (2-5 seconds) at ~$0.01-0.03 per image.",
        "tool_type": ToolType.IMAGE_VIDEO,
        "template_type": ToolTemplateType.IMAGE_GEMINI_NANO_BANANA,
        "implementation_config": {
            "provider": "google",
            "model": "gemini-3-pro-image-preview",
            "aspect_ratio": "1:1",
            "number_of_images": 1,
            "safety_filter_level": "block_some",
            "timeout": 45
        },
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Detailed image generation prompt describing the desired image"
                },
                "negative_prompt": {
                    "type": "string",
                    "description": "Elements to avoid in the image (optional)",
                    "default": ""
                },
                "aspect_ratio": {
                    "type": "string",
                    "description": "Image aspect ratio: 1:1, 16:9, 9:16, 4:3, or 3:4",
                    "default": "1:1"
                },
                "style": {
                    "type": "string",
                    "description": "Image style: photorealistic, artistic, anime, illustration, or default",
                    "default": "default"
                }
            },
            "required": ["prompt"]
        },
        "output_format": "json",
        "is_template_based": True,
        "is_advanced_mode": False,
        "is_public": True,
        "category": "image_video",
        "tags": ["image", "generation", "google", "gemini", "nano-banana", "fast", "featured", "workflow"]
    },
    # Add more default tools here as needed:
    # - slack_notification
    # - discord_notification
    # - etc.
]


def seed_custom_tools(db: Session) -> Dict[str, Any]:
    """
    Seed the database with pre-configured custom tools.

    This function is idempotent - it will skip tools that already exist
    based on their tool_id.

    Args:
        db: SQLAlchemy database session

    Returns:
        Dict with 'created', 'skipped', and 'errors' counts
    """
    results = {
        "created": 0,
        "skipped": 0,
        "errors": 0,
        "details": []
    }

    for tool_data in DEFAULT_CUSTOM_TOOLS:
        tool_id = tool_data["tool_id"]

        try:
            # Check if tool already exists
            existing = db.query(CustomTool).filter(
                CustomTool.tool_id == tool_id
            ).first()

            if existing:
                logger.info(f"Tool '{tool_id}' already exists, skipping")
                results["skipped"] += 1
                results["details"].append(f"Skipped: {tool_id} (already exists)")
                continue

            # Create new custom tool
            custom_tool = CustomTool(
                tool_id=tool_data["tool_id"],
                name=tool_data["name"],
                description=tool_data["description"],
                tool_type=tool_data["tool_type"],
                template_type=tool_data["template_type"],
                implementation_config=tool_data["implementation_config"],
                input_schema=tool_data["input_schema"],
                output_format=tool_data.get("output_format", "string"),
                is_template_based=tool_data.get("is_template_based", True),
                is_advanced_mode=tool_data.get("is_advanced_mode", False),
                is_public=tool_data.get("is_public", False),
                category=tool_data.get("category"),
                tags=tool_data.get("tags", []),
                version="1.0.0"
            )

            db.add(custom_tool)
            logger.info(f"Created custom tool: {tool_id}")
            results["created"] += 1
            results["details"].append(f"Created: {tool_id}")

        except Exception as e:
            logger.error(f"Failed to create tool '{tool_id}': {e}")
            results["errors"] += 1
            results["details"].append(f"Error: {tool_id} - {str(e)}")

    # Commit all changes
    try:
        db.commit()
        logger.info(f"Custom tool seeding complete: {results['created']} created, {results['skipped']} skipped, {results['errors']} errors")
    except Exception as e:
        logger.error(f"Failed to commit custom tools: {e}")
        db.rollback()
        results["errors"] += 1
        results["details"].append(f"Commit error: {str(e)}")

    return results


async def seed_custom_tools_async(db: Session) -> Dict[str, Any]:
    """
    Async wrapper for seed_custom_tools.

    For consistency with other async seed functions in the codebase.
    """
    return seed_custom_tools(db)
