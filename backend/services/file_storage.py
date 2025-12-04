# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
File Storage Service

Handles persistence of uploaded documents to disk.
"""
import logging
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class FileStorage:
    """Manages file storage for uploaded documents."""
    
    def __init__(self, base_dir: str = "./data/documents"):
        """
        Initialize file storage.
        
        Args:
            base_dir: Base directory for document storage
        """
        self._default_base_dir = base_dir
        self._base_dir = None
        self._init_storage()
    
    def _init_storage(self):
        """Initialize storage directory from settings."""
        try:
            from api.system.settings import _settings
            base_dir = _settings.get("storage_path", self._default_base_dir)
        except:
            base_dir = self._default_base_dir
        
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"File storage initialized at {self._base_dir.absolute()}")
    
    @property
    def base_dir(self) -> Path:
        """Get current base directory, refreshing from settings if needed."""
        try:
            from api.system.settings import _settings
            current_path = _settings.get("storage_path", self._default_base_dir)
            if str(self._base_dir) != current_path:
                self._base_dir = Path(current_path)
                self._base_dir.mkdir(parents=True, exist_ok=True)
        except:
            pass
        return self._base_dir
    
    def save_file(self, project_id: int, filename: str, content: bytes) -> str:
        """
        Save uploaded file to disk.
        
        Args:
            project_id: Project identifier
            filename: Original filename
            content: File content bytes
            
        Returns:
            Absolute path to saved file
        """
        project_dir = self.base_dir / f"project_{project_id}"
        project_dir.mkdir(exist_ok=True)
        
        # Generate unique filename to avoid collisions
        file_id = uuid.uuid4().hex[:8]
        safe_filename = f"{file_id}_{filename}"
        file_path = project_dir / safe_filename
        
        # Write file
        file_path.write_bytes(content)
        logger.info(f"Saved file {filename} to {file_path}")
        
        return str(file_path.absolute())
    
    def delete_file(self, file_path: str) -> bool:
        """
        Delete file from disk.
        
        Args:
            file_path: Path to file
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                logger.info(f"Deleted file {file_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            return False
    
    def get_project_storage_size(self, project_id: int) -> int:
        """
        Calculate total storage used by project.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Total bytes used
        """
        project_dir = self.base_dir / f"project_{project_id}"
        if not project_dir.exists():
            return 0
        
        total_size = sum(f.stat().st_size for f in project_dir.rglob('*') if f.is_file())
        return total_size


# Global instance
file_storage = FileStorage()
