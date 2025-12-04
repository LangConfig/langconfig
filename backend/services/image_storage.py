# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Image Storage Service

Handles downloading, storing, and serving AI-generated images from workflows.
Ensures images persist beyond API URL expiration and can be bundled with exports.
"""

import os
import hashlib
import httpx
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)

# Storage configuration
STORAGE_DIR = Path("storage/generated_images")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Image metadata tracking
_image_registry: Dict[str, Dict[str, Any]] = {}


class ImageStorageService:
    """
    Service for managing AI-generated images from workflows.

    Features:
    - Downloads images from temporary URLs (DALL-E, Nano Banana)
    - Stores images persistently with unique IDs
    - Tracks image metadata (workflow, task, prompt, etc.)
    - Provides URLs for serving images
    - Enables bundled exports
    """

    @staticmethod
    async def download_and_store_image(
        image_url: str,
        workflow_id: Optional[int] = None,
        task_id: Optional[int] = None,
        prompt: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """
        Download image from temporary URL and store persistently.

        Args:
            image_url: Temporary URL from image generation API
            workflow_id: Associated workflow ID
            task_id: Associated task ID
            prompt: Generation prompt (for reference)
            metadata: Additional metadata

        Returns:
            Dictionary with:
            - image_id: Unique identifier
            - local_path: File path
            - public_url: URL for frontend access
            - original_url: Original temporary URL
        """
        try:
            # Generate unique image ID from URL
            image_id = hashlib.md5(f"{image_url}{datetime.utcnow()}".encode()).hexdigest()[:16]

            # Download image
            logger.info(f"Downloading image from: {image_url}")
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(image_url)
                response.raise_for_status()

                # Detect format from content-type or URL
                content_type = response.headers.get("content-type", "")
                if "png" in content_type or image_url.endswith(".png"):
                    extension = "png"
                elif "jpeg" in content_type or "jpg" in content_type:
                    extension = "jpg"
                elif "webp" in content_type:
                    extension = "webp"
                else:
                    extension = "png"  # Default

                # Save to disk
                filename = f"{image_id}.{extension}"
                file_path = STORAGE_DIR / filename

                with open(file_path, "wb") as f:
                    f.write(response.content)

                logger.info(f"Image saved to: {file_path}")

                # Store metadata
                _image_registry[image_id] = {
                    "image_id": image_id,
                    "filename": filename,
                    "local_path": str(file_path),
                    "workflow_id": workflow_id,
                    "task_id": task_id,
                    "prompt": prompt,
                    "original_url": image_url,
                    "created_at": datetime.utcnow().isoformat(),
                    "file_size": len(response.content),
                    "format": extension,
                    **(metadata or {})
                }

                # Return info
                return {
                    "image_id": image_id,
                    "local_path": str(file_path),
                    "public_url": f"/api/images/{image_id}",  # Frontend-accessible URL
                    "original_url": image_url,
                    "format": extension
                }

        except Exception as e:
            logger.error(f"Failed to download and store image: {e}")
            # Return original URL as fallback
            return {
                "image_id": None,
                "local_path": None,
                "public_url": image_url,  # Use original if download fails
                "original_url": image_url,
                "error": str(e)
            }

    @staticmethod
    def get_image_path(image_id: str) -> Optional[Path]:
        """Get local file path for an image by ID."""
        if image_id in _image_registry:
            return Path(_image_registry[image_id]["local_path"])

        # Try to find file directly
        for file in STORAGE_DIR.glob(f"{image_id}.*"):
            return file

        return None

    @staticmethod
    def get_image_metadata(image_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for an image."""
        return _image_registry.get(image_id)

    @staticmethod
    def get_workflow_images(workflow_id: int, task_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all images for a workflow/task."""
        results = []
        for img_id, metadata in _image_registry.items():
            if metadata.get("workflow_id") == workflow_id:
                if task_id is None or metadata.get("task_id") == task_id:
                    results.append(metadata)
        return results

    @staticmethod
    def cleanup_old_images(days: int = 30) -> int:
        """
        Clean up images older than specified days.

        Args:
            days: Number of days to keep images

        Returns:
            Number of images deleted
        """
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        deleted = 0

        for img_id, metadata in list(_image_registry.items()):
            created_at = datetime.fromisoformat(metadata["created_at"])
            if created_at < cutoff:
                # Delete file
                try:
                    file_path = Path(metadata["local_path"])
                    if file_path.exists():
                        file_path.unlink()
                    del _image_registry[img_id]
                    deleted += 1
                except Exception as e:
                    logger.error(f"Failed to delete image {img_id}: {e}")

        logger.info(f"Cleaned up {deleted} old images")
        return deleted


# Export function for creating bundled packages
async def create_image_bundle(
    workflow_id: int,
    task_id: int,
    markdown_content: str,
    output_dir: Path
) -> Dict[str, Any]:
    """
    Create a bundled export with markdown and all images.

    Args:
        workflow_id: Workflow ID
        task_id: Task ID
        markdown_content: Markdown content with image references
        output_dir: Directory to create bundle in

    Returns:
        Dictionary with bundle info and file paths
    """
    try:
        # Get all images for this task
        images = ImageStorageService.get_workflow_images(workflow_id, task_id)

        if not images:
            logger.info("No images to bundle")
            return {
                "image_count": 0,
                "images": [],
                "markdown_content": markdown_content
            }

        # Create images subdirectory
        images_dir = output_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        # Copy images and update markdown references
        updated_markdown = markdown_content
        bundled_images = []

        for img_metadata in images:
            img_id = img_metadata["image_id"]
            filename = img_metadata["filename"]
            local_path = Path(img_metadata["local_path"])

            if local_path.exists():
                # Copy to bundle
                dest_path = images_dir / filename
                import shutil
                shutil.copy2(local_path, dest_path)

                # Update markdown references
                original_url = img_metadata["original_url"]
                public_url = f"/api/images/{img_id}"
                relative_path = f"./images/{filename}"

                # Replace URLs in markdown
                updated_markdown = updated_markdown.replace(original_url, relative_path)
                updated_markdown = updated_markdown.replace(public_url, relative_path)

                bundled_images.append({
                    "image_id": img_id,
                    "filename": filename,
                    "relative_path": relative_path,
                    "prompt": img_metadata.get("prompt")
                })

        logger.info(f"Bundled {len(bundled_images)} images")

        return {
            "image_count": len(bundled_images),
            "images": bundled_images,
            "markdown_content": updated_markdown,
            "images_dir": str(images_dir)
        }

    except Exception as e:
        logger.error(f"Failed to create image bundle: {e}")
        return {
            "image_count": 0,
            "images": [],
            "markdown_content": markdown_content,
            "error": str(e)
        }
