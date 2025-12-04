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
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class WorkspaceManager:
    """Manages workspace directories for project/workflow/task outputs"""
    
    def __init__(self, base_dir: str = "outputs"):
        """
        Initialize workspace manager.
        
        Args:
            base_dir: Base directory for all outputs (default: "outputs")
        """
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
