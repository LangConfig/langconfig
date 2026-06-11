"""Git Repository model for the read-only repository browser feature."""

import datetime
import enum

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from db.database import Base


class RepoSyncStatus(str, enum.Enum):
    PENDING = "pending"
    CLONING = "cloning"
    SYNCED = "synced"
    SYNCING = "syncing"
    INDEXING = "indexing"
    ERROR = "error"


class GitRepository(Base):
    __tablename__ = "git_repositories"
    __table_args__ = (
        UniqueConstraint("project_id", "clone_url", name="uq_project_clone_url"),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    clone_url = Column(String(500), nullable=False)
    repo_name = Column(String(255), nullable=False)
    local_path = Column(String(500), nullable=True)
    branch = Column(String(100), nullable=False, default="main")
    sync_status = Column(
        Enum(RepoSyncStatus, values_callable=lambda x: [e.value for e in x]),
        default=RepoSyncStatus.PENDING,
    )
    last_commit_hash = Column(String(40), nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    indexed_files_count = Column(Integer, nullable=False, default=0)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    project = relationship("Project", back_populates="git_repositories")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "clone_url": self.clone_url,
            "repo_name": self.repo_name,
            "local_path": self.local_path,
            "branch": self.branch,
            "sync_status": self.sync_status.value if self.sync_status else None,
            "last_commit_hash": self.last_commit_hash,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
            "last_error": self.last_error,
            "indexed_files_count": self.indexed_files_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
