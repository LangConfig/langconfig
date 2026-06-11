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
        "description": "Studio-quality AI image generation using Gemini 3 Pro Image — Google's highest-quality image model. Reasoning-driven generation for maximum factual accuracy, complex graphic design, and high-fidelity product mockups. Supports 512px-4K output, 14 aspect ratios, Google Search grounding, subject consistency via reference images, accurate text rendering, and conversational multi-turn editing. $0.134/image.",
        "tool_type": ToolType.IMAGE_VIDEO,
        "template_type": ToolTemplateType.IMAGE_GEMINI_NANO_BANANA,
        "implementation_config": {
            "provider": "google",
            "model": "gemini-3-pro-image-preview",
            "aspect_ratio": "1:1",
            "image_size": "1K",
            "number_of_images": 1,
            "safety_filter_level": "block_some",
            "timeout": 45
        },
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Detailed image generation prompt. Pro excels at complex graphic design, factual accuracy, and precise text rendering."
                },
                "negative_prompt": {
                    "type": "string",
                    "description": "Elements to avoid in the image (optional)",
                    "default": ""
                },
                "aspect_ratio": {
                    "type": "string",
                    "description": "Image aspect ratio: 1:1, 16:9, 9:16, 4:3, 3:4, 2:3, 3:2, 4:5, 5:4, 4:1, 1:4, 8:1, 1:8, or 21:9",
                    "default": "1:1"
                },
                "image_size": {
                    "type": "string",
                    "description": "Output resolution: 512px (fast/cheap), 1K (default), 2K (high quality), or 4K (production)",
                    "default": "1K"
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
        "tags": ["image", "generation", "google", "gemini", "nano-banana", "pro", "studio", "featured", "workflow"]
    },
    {
        "tool_id": "image_generation_nb2",
        "name": "Nano Banana 2 (Image Generator)",
        "description": "High-volume AI image generation using Gemini 3.1 Flash Image. Pro-level quality at Flash speed: vibrant lighting, rich textures, sharp details. 50% cheaper than Nano Banana Pro ($0.067/image). Supports 512px-4K output, 14 aspect ratios, Google Image Search grounding, subject consistency via reference images, accurate text rendering, and data visualizations.",
        "tool_type": ToolType.IMAGE_VIDEO,
        "template_type": ToolTemplateType.IMAGE_GEMINI_NANO_BANANA_2,
        "implementation_config": {
            "provider": "google",
            "model": "gemini-3.1-flash-image-preview",
            "aspect_ratio": "1:1",
            "image_size": "1K",
            "number_of_images": 1,
            "safety_filter_level": "block_some",
            "enable_image_search": False,
            "thinking_level": "minimal",
            "timeout": 45
        },
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Detailed image generation prompt. The model follows complex instructions precisely and can render accurate text, diagrams, and infographics."
                },
                "negative_prompt": {
                    "type": "string",
                    "description": "Elements to avoid in the image (optional)",
                    "default": ""
                },
                "aspect_ratio": {
                    "type": "string",
                    "description": "Image aspect ratio: 1:1, 16:9, 9:16, 4:3, 3:4, 2:3, 3:2, 4:5, 5:4, 4:1, 1:4, 8:1, 1:8, or 21:9",
                    "default": "1:1"
                },
                "image_size": {
                    "type": "string",
                    "description": "Output resolution: 512px (fast/cheap), 1K (default), 2K (high quality), or 4K (production)",
                    "default": "1K"
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
        "tags": ["image", "generation", "google", "gemini", "nano-banana-2", "flash", "4k", "fast", "featured", "workflow", "grounding", "batch"]
    },
    {
        "tool_id": "openai_image_generation",
        "name": "GPT Image 2 (Image Generator)",
        "description": "OpenAI GPT Image 2 generation with artifact delivery for chat and workflow runs. Supports flexible output sizing, quality controls, background handling, and PNG/JPEG/WebP outputs.",
        "tool_type": ToolType.IMAGE_VIDEO,
        "template_type": ToolTemplateType.IMAGE_OPENAI_GPT_IMAGE_2,
        "implementation_config": {
            "provider": "openai",
            "model": "gpt-image-2",
            "size": "auto",
            "quality": "auto",
            "background": "auto",
            "output_format": "png",
            "timeout": 120
        },
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Detailed image generation prompt."
                },
                "size": {
                    "type": "string",
                    "description": "Image size: auto, 1024x1024, 1536x1024, or 1024x1536",
                    "enum": ["auto", "1024x1024", "1536x1024", "1024x1536"],
                    "default": "auto"
                },
                "quality": {
                    "type": "string",
                    "description": "Image quality: auto, low, medium, or high",
                    "enum": ["auto", "low", "medium", "high"],
                    "default": "auto"
                },
                "background": {
                    "type": "string",
                    "description": "Background: auto, transparent, or opaque",
                    "enum": ["auto", "transparent", "opaque"],
                    "default": "auto"
                },
                "output_format": {
                    "type": "string",
                    "description": "Output image format: png, jpeg, or webp",
                    "enum": ["png", "jpeg", "webp"],
                    "default": "png"
                }
            },
            "required": ["prompt"]
        },
        "output_format": "json",
        "is_template_based": True,
        "is_advanced_mode": False,
        "is_public": True,
        "category": "image_video",
        "tags": ["image", "generation", "openai", "gpt-image-2", "artifact", "featured", "workflow"]
    },
    {
        "tool_id": "video_generation",
        "name": "Veo 3.1 Fast (Video Generator)",
        "description": "AI video generation using Google's Veo 3.1 Fast model. Supports text-to-video, image-to-video animation, and video continuation/extension. Generate up to 8 seconds per clip with audio.",
        "tool_type": ToolType.IMAGE_VIDEO,
        "template_type": ToolTemplateType.VIDEO_GEMINI_VEO31,
        "implementation_config": {
            "provider": "google",
            "model": "veo-3.1-fast-generate-preview",
            "duration": 8,
            "resolution": "720p",
            "fps": 24,
            "aspect_ratio": "16:9",
            "generate_audio": True,
            "timeout": 180
        },
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Text description of the video to generate, including desired actions, scenes, and style"
                },
                "image_url": {
                    "type": "string",
                    "description": "Optional: URL or base64 data URI of an image to animate (image-to-video mode)",
                    "default": ""
                },
                "video_url": {
                    "type": "string",
                    "description": "Optional: URL of a previously generated Veo video to extend/continue",
                    "default": ""
                },
                "duration": {
                    "type": "integer",
                    "description": "Video duration in seconds: 4, 6, or 8",
                    "default": 8
                },
                "aspect_ratio": {
                    "type": "string",
                    "description": "Video aspect ratio: 16:9 (landscape) or 9:16 (portrait)",
                    "default": "16:9"
                },
                "negative_prompt": {
                    "type": "string",
                    "description": "Optional: Elements or styles to avoid in the video",
                    "default": ""
                }
            },
            "required": ["prompt"]
        },
        "output_format": "json",
        "is_template_based": True,
        "is_advanced_mode": False,
        "is_public": True,
        "category": "image_video",
        "tags": ["video", "generation", "google", "veo", "fast", "image-to-video", "video-extension", "featured", "workflow"]
    },
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
