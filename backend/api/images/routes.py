# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Image API Endpoints

Serves AI-generated images and provides export functionality.
"""

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse, StreamingResponse
from pathlib import Path
from typing import List
import zipfile
import io
import logging

from services.image_storage import ImageStorageService, create_image_bundle, STORAGE_DIR

router = APIRouter(prefix="/api/images", tags=["images"])
logger = logging.getLogger(__name__)


@router.get("/{image_id}")
async def get_image(image_id: str):
    """
    Serve a generated image by ID.

    Args:
        image_id: Unique image identifier

    Returns:
        Image file
    """
    try:
        image_path = ImageStorageService.get_image_path(image_id)

        if not image_path or not image_path.exists():
            raise HTTPException(status_code=404, detail="Image not found")

        # Determine media type from extension
        extension = image_path.suffix.lower()
        media_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif"
        }
        media_type = media_types.get(extension, "image/png")

        return FileResponse(
            image_path,
            media_type=media_type,
            filename=image_path.name
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to serve image {image_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflow/{workflow_id}/task/{task_id}")
async def get_workflow_images(workflow_id: int, task_id: int):
    """
    Get all images for a specific workflow task.

    Returns:
        List of image metadata
    """
    try:
        images = ImageStorageService.get_workflow_images(workflow_id, task_id)
        return {
            "workflow_id": workflow_id,
            "task_id": task_id,
            "image_count": len(images),
            "images": images
        }
    except Exception as e:
        logger.error(f"Failed to get workflow images: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflow/{workflow_id}/task/{task_id}/export")
async def export_workflow_with_images(
    workflow_id: int,
    task_id: int,
    markdown_content: str
):
    """
    Export workflow results as ZIP with images bundled.

    Args:
        workflow_id: Workflow ID
        task_id: Task ID
        markdown_content: Markdown content with image references

    Returns:
        ZIP file containing markdown + images
    """
    try:
        # Get all images
        images = ImageStorageService.get_workflow_images(workflow_id, task_id)

        if not images:
            # No images, just return markdown
            return Response(
                content=markdown_content,
                media_type="text/markdown",
                headers={
                    "Content-Disposition": f"attachment; filename=workflow-{workflow_id}-task-{task_id}.md"
                }
            )

        # Create ZIP in memory
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Update markdown to use relative paths
            updated_markdown = markdown_content

            # Add images to ZIP
            for img_metadata in images:
                img_id = img_metadata["image_id"]
                filename = img_metadata["filename"]
                local_path = Path(img_metadata["local_path"])

                if local_path.exists():
                    # Add image to ZIP
                    zip_file.write(local_path, f"images/{filename}")

                    # Update markdown references
                    original_url = img_metadata["original_url"]
                    public_url = f"/api/images/{img_id}"
                    relative_path = f"./images/{filename}"

                    updated_markdown = updated_markdown.replace(original_url, relative_path)
                    updated_markdown = updated_markdown.replace(public_url, relative_path)

            # Add markdown to ZIP
            zip_file.writestr("report.md", updated_markdown)

            # Add README
            readme_content = f"""# Workflow Export

**Workflow ID:** {workflow_id}
**Task ID:** {task_id}
**Images:** {len(images)}

## Contents

- `report.md` - Main workflow output with embedded images
- `images/` - Generated images referenced in the report

## Viewing

Open `report.md` in any markdown viewer that supports images.
Images are referenced using relative paths (`./images/filename.png`).

## Image Details

"""
            for img in images:
                readme_content += f"\n### {img['filename']}\n"
                readme_content += f"- **Prompt:** {img.get('prompt', 'N/A')}\n"
                readme_content += f"- **Created:** {img.get('created_at', 'N/A')}\n"

            zip_file.writestr("README.md", readme_content)

        # Return ZIP
        zip_buffer.seek(0)

        return StreamingResponse(
            io.BytesIO(zip_buffer.getvalue()),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=workflow-{workflow_id}-task-{task_id}-with-images.zip"
            }
        )

    except Exception as e:
        logger.error(f"Failed to export workflow with images: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{image_id}")
async def delete_image(image_id: str):
    """Delete a generated image."""
    try:
        image_path = ImageStorageService.get_image_path(image_id)

        if not image_path or not image_path.exists():
            raise HTTPException(status_code=404, detail="Image not found")

        image_path.unlink()

        return {"message": "Image deleted successfully", "image_id": image_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete image {image_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup")
async def cleanup_old_images(days: int = 30):
    """
    Clean up images older than specified days.

    Args:
        days: Number of days to keep images (default: 30)

    Returns:
        Number of images deleted
    """
    try:
        deleted_count = ImageStorageService.cleanup_old_images(days)
        return {
            "message": f"Cleanup completed",
            "deleted_count": deleted_count,
            "days_threshold": days
        }
    except Exception as e:
        logger.error(f"Failed to cleanup images: {e}")
        raise HTTPException(status_code=500, detail=str(e))
