# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Workspace Manager for Organized File Storage

Manages output folders for projects, workflows, and tasks.
Creates a clean directory structure: outputs/project_{id}/workflow_{id}/task_{id}/

This allows:
- Easy browsing of project outputs
- Automatic cleanup of old task outputs
- Better organization for multi-project setups
"""
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime
import mimetypes
import shutil

logger = logging.getLogger(__name__)


class WorkspaceManager:
    """Manages workspace directories for project/workflow/task outputs"""

    def __init__(self, base_dir: str = None):
        """
        Initialize workspace manager.

        Args:
            base_dir: Base directory for all outputs. If None, uses backend/outputs.
        """
        if base_dir is None:
            # Default to backend/outputs relative to this file's location
            backend_dir = Path(__file__).parent.parent  # services/ -> backend/
            self.base_dir = backend_dir / "outputs"
        else:
            self.base_dir = Path(base_dir).resolve()

        self.base_dir.mkdir(exist_ok=True)
        logger.info(f"Workspace manager initialized: {self.base_dir}")
    
    def get_task_workspace(
        self,
        project_id: Optional[int],
        workflow_id: int,
        task_id: int
    ) -> Path:
        """
        Get workspace directory for a specific task.
        
        Creates directory structure: outputs/project_{id}/workflow_{id}/task_{id}/
        If project_id is None, uses "standalone" as the project folder.
        
        Args:
            project_id: Project ID (can be None for standalone workflows)
            workflow_id: Workflow ID
            task_id: Task ID
            
        Returns:
            Path to task workspace directory
        """
        # Handle standalone workflows (no project)
        project_folder = f"project_{project_id}" if project_id else "standalone"
        
        # Build path: outputs/project_X/workflow_Y/task_Z/
        workspace = self.base_dir / project_folder / f"workflow_{workflow_id}" / f"task_{task_id}"
        
        # Create directory if it doesn't exist
        workspace.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Task workspace: {workspace}")
        return workspace
    
    def get_workflow_workspace(
        self,
        project_id: Optional[int],
        workflow_id: int
    ) -> Path:
        """
        Get workspace directory for all tasks in a workflow.
        
        Args:
            project_id: Project ID
            workflow_id: Workflow ID
            
        Returns:
            Path to workflow workspace directory
        """
        project_folder = f"project_{project_id}" if project_id else "standalone"
        workspace = self.base_dir / project_folder / f"workflow_{workflow_id}"
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace
    
    def get_project_workspace(self, project_id: int) -> Path:
        """
        Get workspace directory for all workflows in a project.
        
        Args:
            project_id: Project ID
            
        Returns:
            Path to project workspace directory
        """
        workspace = self.base_dir / f"project_{project_id}"
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace
    
    def list_task_files(self, project_id: Optional[int], workflow_id: int, task_id: int) -> list[dict]:
        """
        List all files in a task's workspace.
        
        Returns:
            List of file info dicts with name, size, modified_at, extension
        """
        workspace = self.get_task_workspace(project_id, workflow_id, task_id)
        
        files = []
        for file_path in workspace.iterdir():
            if file_path.is_file():
                stat = file_path.stat()
                files.append({
                    "filename": file_path.name,
                    "path": str(file_path.relative_to(self.base_dir)),
                    "size_bytes": stat.st_size,
                    "size_human": self._format_size(stat.st_size),
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "extension": file_path.suffix,
                })
        
        # Sort by modification time (newest first)
        files.sort(key=lambda x: x['modified_at'], reverse=True)
        return files
    
    def get_file_path(
        self,
        project_id: Optional[int],
        workflow_id: int,
        task_id: int,
        filename: str
    ) -> Optional[Path]:
        """
        Get full path to a file in task workspace.

        Returns None if file doesn't exist or is outside workspace (security).
        """
        workspace = self.get_task_workspace(project_id, workflow_id, task_id)
        file_path = (workspace / filename).resolve()

        # Security: Ensure file is within workspace
        if not str(file_path).startswith(str(workspace)):
            logger.warning(f"Path traversal attempt blocked: {filename}")
            return None

        if not file_path.exists() or not file_path.is_file():
            return None

        return file_path

    def get_default_file_path(self, filename: str) -> Optional[Path]:
        """
        Get full path to a file in the default workspace.

        Returns None if file doesn't exist or is outside workspace (security).
        """
        default_dir = self.base_dir / "default"
        file_path = (default_dir / filename).resolve()

        # Security: Ensure file is within default directory
        if not str(file_path).startswith(str(default_dir)):
            logger.warning(f"Path traversal attempt blocked: {filename}")
            return None

        if not file_path.exists() or not file_path.is_file():
            return None

        return file_path

    def list_default_files(self) -> list[dict]:
        """
        List all files in the default workspace.

        Returns:
            List of file info dicts
        """
        default_dir = self.base_dir / "default"

        if not default_dir.exists():
            return []

        files = []
        for file_path in default_dir.iterdir():
            if file_path.is_file():
                stat = file_path.stat()
                files.append({
                    "filename": file_path.name,
                    "path": str(file_path.relative_to(self.base_dir)),
                    "size_bytes": stat.st_size,
                    "size_human": self._format_size(stat.st_size),
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "extension": file_path.suffix,
                })

        files.sort(key=lambda x: x['modified_at'], reverse=True)
        return files

    def get_default_file_content(
        self,
        filename: str,
        max_size: int = 1024 * 1024
    ) -> Optional[dict]:
        """Get content of a file in the default workspace."""
        file_path = self.get_default_file_path(filename)

        if not file_path:
            return None

        # Determine mime type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type is None:
            mime_type = "text/plain"

        # Check if text-based
        text_types = [
            "text/", "application/json", "application/javascript",
            "application/xml", "application/yaml", "application/x-yaml"
        ]
        is_text = any(mime_type.startswith(t) for t in text_types)

        text_extensions = {
            '.md', '.txt', '.py', '.js', '.ts', '.tsx', '.jsx', '.json',
            '.yaml', '.yml', '.xml', '.html', '.css', '.scss', '.sql',
            '.sh', '.bash', '.env', '.gitignore', '.csv', '.toml', '.ini',
            '.cfg', '.conf', '.log', '.rst', '.tex'
        }
        if file_path.suffix.lower() in text_extensions:
            is_text = True

        if not is_text:
            return {
                "content": None,
                "mime_type": mime_type,
                "is_binary": True,
                "truncated": False,
                "size_bytes": file_path.stat().st_size
            }

        try:
            file_size = file_path.stat().st_size
            truncated = file_size > max_size

            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read(max_size)

            return {
                "content": content,
                "mime_type": mime_type,
                "is_binary": False,
                "truncated": truncated,
                "size_bytes": file_size
            }
        except Exception as e:
            logger.error(f"Error reading file content: {e}")
            return None

    def delete_default_file(self, filename: str) -> bool:
        """Delete a file from the default workspace."""
        file_path = self.get_default_file_path(filename)

        if not file_path:
            return False

        try:
            file_path.unlink()
            logger.info(f"Deleted default file: {filename}")
            return True
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False

    def rename_default_file(self, old_name: str, new_name: str) -> bool:
        """Rename a file in the default workspace."""
        default_dir = self.base_dir / "default"
        old_path = (default_dir / old_name).resolve()
        new_path = (default_dir / new_name).resolve()

        # Security checks
        if not str(old_path).startswith(str(default_dir)):
            return False
        if not str(new_path).startswith(str(default_dir)):
            return False

        if not old_path.exists():
            return False
        if new_path.exists():
            return False

        try:
            old_path.rename(new_path)
            logger.info(f"Renamed default file: {old_name} -> {new_name}")
            return True
        except Exception as e:
            logger.error(f"Error renaming file: {e}")
            return False
    
    def rename_file(
        self,
        project_id: Optional[int],
        workflow_id: int,
        task_id: int,
        old_name: str,
        new_name: str
    ) -> bool:
        """
        Rename a file in the task workspace.

        Args:
            project_id: Project ID
            workflow_id: Workflow ID
            task_id: Task ID
            old_name: Current filename
            new_name: New filename

        Returns:
            True if renamed successfully, False otherwise
        """
        workspace = self.get_task_workspace(project_id, workflow_id, task_id)
        old_path = (workspace / old_name).resolve()
        new_path = (workspace / new_name).resolve()

        # Security: Ensure both paths are within workspace
        if not str(old_path).startswith(str(workspace)):
            logger.warning(f"Path traversal attempt blocked (old): {old_name}")
            return False
        if not str(new_path).startswith(str(workspace)):
            logger.warning(f"Path traversal attempt blocked (new): {new_name}")
            return False

        if not old_path.exists():
            logger.warning(f"File not found: {old_path}")
            return False

        if new_path.exists():
            logger.warning(f"Target file already exists: {new_path}")
            return False

        try:
            old_path.rename(new_path)
            logger.info(f"Renamed file: {old_name} -> {new_name}")
            return True
        except Exception as e:
            logger.error(f"Error renaming file: {e}")
            return False

    def delete_file(
        self,
        project_id: Optional[int],
        workflow_id: int,
        task_id: int,
        filename: str
    ) -> bool:
        """
        Delete a file from the task workspace.

        Args:
            project_id: Project ID
            workflow_id: Workflow ID
            task_id: Task ID
            filename: Filename to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        file_path = self.get_file_path(project_id, workflow_id, task_id, filename)

        if not file_path:
            logger.warning(f"File not found or invalid path: {filename}")
            return False

        try:
            file_path.unlink()
            logger.info(f"Deleted file: {filename}")
            return True
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False

    def get_file_content(
        self,
        project_id: Optional[int],
        workflow_id: int,
        task_id: int,
        filename: str,
        max_size: int = 1024 * 1024  # 1MB default limit
    ) -> Optional[dict]:
        """
        Get the content of a file for preview.

        Args:
            project_id: Project ID
            workflow_id: Workflow ID
            task_id: Task ID
            filename: Filename to read
            max_size: Maximum file size to read (default 1MB)

        Returns:
            Dict with content, mime_type, truncated flag, or None if not found
        """
        file_path = self.get_file_path(project_id, workflow_id, task_id, filename)

        if not file_path:
            return None

        # Determine mime type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type is None:
            mime_type = "text/plain"

        # Check if it's a text-based file we can preview
        text_types = [
            "text/", "application/json", "application/javascript",
            "application/xml", "application/yaml", "application/x-yaml"
        ]
        is_text = any(mime_type.startswith(t) for t in text_types)

        # Check file extension for common text files
        text_extensions = {
            '.md', '.txt', '.py', '.js', '.ts', '.tsx', '.jsx', '.json',
            '.yaml', '.yml', '.xml', '.html', '.css', '.scss', '.sql',
            '.sh', '.bash', '.env', '.gitignore', '.csv', '.toml', '.ini',
            '.cfg', '.conf', '.log', '.rst', '.tex'
        }
        if file_path.suffix.lower() in text_extensions:
            is_text = True

        if not is_text:
            return {
                "content": None,
                "mime_type": mime_type,
                "is_binary": True,
                "truncated": False,
                "size_bytes": file_path.stat().st_size
            }

        try:
            file_size = file_path.stat().st_size
            truncated = file_size > max_size

            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read(max_size)

            return {
                "content": content,
                "mime_type": mime_type,
                "is_binary": False,
                "truncated": truncated,
                "size_bytes": file_size
            }
        except Exception as e:
            logger.error(f"Error reading file content: {e}")
            return None

    def list_all_files(
        self,
        project_id: Optional[int] = None,
        workflow_id: Optional[int] = None,
        search: Optional[str] = None,
        file_type: Optional[str] = None
    ) -> List[dict]:
        """
        List all files across projects/workflows.

        Args:
            project_id: Filter by project ID (optional)
            workflow_id: Filter by workflow ID (optional)
            search: Search term for filename (optional)
            file_type: Filter by file extension (optional)

        Returns:
            List of file info dicts with project/workflow/task context
        """
        all_files = []
        logger.info(f"Listing all files from base_dir: {self.base_dir}")

        def add_file(file_path: Path, proj_id: Optional[int], wf_id: Optional[int], t_id: Optional[int]):
            """Helper to add a file to the list with filters applied"""
            if not file_path.is_file():
                return

            # Apply filters
            if search and search.lower() not in file_path.name.lower():
                return

            if file_type and file_path.suffix.lower() != f".{file_type.lower()}":
                return

            try:
                stat = file_path.stat()
                all_files.append({
                    "filename": file_path.name,
                    "path": str(file_path.relative_to(self.base_dir)),
                    "full_path": str(file_path),
                    "project_id": proj_id,
                    "workflow_id": wf_id,
                    "task_id": t_id,
                    "size_bytes": stat.st_size,
                    "size_human": self._format_size(stat.st_size),
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "extension": file_path.suffix,
                })
            except Exception as e:
                logger.warning(f"Could not stat file {file_path}: {e}")

        # Check if base_dir exists
        if not self.base_dir.exists():
            logger.warning(f"Base directory does not exist: {self.base_dir}")
            return all_files

        # First, scan for files directly in outputs/ (root level)
        if not project_id and not workflow_id:
            for item in self.base_dir.iterdir():
                if item.is_file():
                    add_file(item, None, None, None)

        # Determine which directories to scan
        if project_id:
            scan_dirs = [self.base_dir / f"project_{project_id}"]
        else:
            # Scan all subdirectories
            scan_dirs = [d for d in self.base_dir.iterdir() if d.is_dir()]

        logger.info(f"list_all_files: Scanning directories: {[str(d) for d in scan_dirs]}")

        for project_dir in scan_dirs:
            if not project_dir.exists():
                continue

            # Extract project ID from folder name
            proj_name = project_dir.name
            proj_id = None

            if proj_name.startswith("project_"):
                try:
                    proj_id = int(proj_name.replace("project_", ""))
                except ValueError:
                    logger.warning(f"Skipping malformed project directory: {proj_name}")
                    continue
            elif proj_name in ("standalone", "default"):
                proj_id = None
            else:
                # Skip unknown directories at project level
                continue

            # For default folder, scan files directly (not in workflow/task structure)
            if proj_name == "default":
                for file_path in project_dir.iterdir():
                    add_file(file_path, None, None, None)
                continue

            # For project folders, scan workflow directories
            for workflow_dir in project_dir.iterdir():
                if not workflow_dir.is_dir():
                    # Could be a file directly in project folder
                    add_file(workflow_dir, proj_id, None, None)
                    continue

                if not workflow_dir.name.startswith("workflow_"):
                    continue

                # Extract workflow ID - handle "workflow_None" case
                wf_id_str = workflow_dir.name.replace("workflow_", "")
                if wf_id_str == "None" or wf_id_str == "":
                    wf_id = None
                else:
                    try:
                        wf_id = int(wf_id_str)
                    except ValueError:
                        logger.warning(f"Skipping malformed workflow directory: {workflow_dir.name}")
                        continue

                # Filter by workflow_id if specified
                if workflow_id and wf_id != workflow_id:
                    continue

                # Scan task directories
                for task_dir in workflow_dir.iterdir():
                    if not task_dir.is_dir():
                        # Could be a file directly in workflow folder
                        add_file(task_dir, proj_id, wf_id, None)
                        continue

                    if not task_dir.name.startswith("task_"):
                        continue

                    try:
                        t_id = int(task_dir.name.replace("task_", ""))
                    except ValueError:
                        logger.warning(f"Skipping malformed task directory: {task_dir.name}")
                        continue

                    # List files in this task
                    for file_path in task_dir.iterdir():
                        if file_path.is_file():
                            logger.debug(f"Found file: {file_path} (project={proj_id}, workflow={wf_id}, task={t_id})")
                            add_file(file_path, proj_id, wf_id, t_id)

        logger.info(f"list_all_files: Found {len(all_files)} files total")

        # Sort by modification time (newest first)
        all_files.sort(key=lambda x: x['modified_at'], reverse=True)
        return all_files

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format bytes as human-readable size"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"


# Global instance
_workspace_manager: Optional[WorkspaceManager] = None


def get_workspace_manager() -> WorkspaceManager:
    """Get or create global workspace manager instance"""
    global _workspace_manager
    if _workspace_manager is None:
        _workspace_manager = WorkspaceManager()
    return _workspace_manager
