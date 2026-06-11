# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Git Repository Service — Clone, sync, and browse git repos.

Clones repos locally so their files can be browsed read-only in the UI
and selectively ingested into the project knowledge base. Uses the
GITHUB_TOKEN environment variable for private-repo auth when set,
falling back to the machine's existing git config otherwise.

Note on subprocess usage: main.py installs WindowsSelectorEventLoopPolicy
on Windows (required for psycopg), and asyncio.create_subprocess_exec
raises NotImplementedError under the selector event loop. All git
commands therefore run via blocking subprocess.run inside
asyncio.to_thread.
"""

import asyncio
import logging
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from db.database import SessionLocal
from models.git_repository import GitRepository, RepoSyncStatus

logger = logging.getLogger(__name__)

REPO_BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "repositories")

# Text-based file extensions worth browsing / ingesting
INDEXABLE_EXTENSIONS = {
    ".md", ".txt", ".py", ".js", ".ts", ".tsx", ".jsx",
    ".json", ".yaml", ".yml", ".csv", ".html", ".css",
    ".sql", ".sh", ".toml", ".cfg", ".rst", ".xml",
    ".env.example", ".ini", ".conf", ".r", ".rb",
    ".go", ".java", ".kt", ".swift", ".rs",
    ".ipynb", ".tex", ".bib",
}

# Directories to always skip
EXCLUDED_DIRS = {
    ".git", "node_modules", "__pycache__", "dist", "build",
    ".venv", "venv", ".env", ".tox", ".mypy_cache",
    ".pytest_cache", "coverage", ".next", ".nuxt",
    "target", "out", "bin", "obj",
}

# Skip files larger than 2MB — prevents OOM on large CSVs/JSONs
MAX_INDEXABLE_FILE_SIZE = 2 * 1024 * 1024

# Subprocess timeouts (seconds)
GIT_CLONE_TIMEOUT = 600
GIT_PULL_TIMEOUT = 300
GIT_COMMAND_TIMEOUT = 30


def validate_clone_url(url: str) -> None:
    """Reject URLs that aren't HTTPS or SSH git URLs.

    Prevents local path traversal, file:// protocol, and ext:: handler abuse.
    """
    url = url.strip()
    if url.startswith("https://"):
        return
    if url.startswith("git@") and ":" in url:
        return
    raise ValueError(
        "Unsupported clone URL. Use HTTPS (https://github.com/...) "
        "or SSH (git@github.com:...) URLs only."
    )


def extract_repo_name(clone_url: str) -> str:
    """Extract repository name from a clone URL.

    Handles:
      - https://github.com/org/repo.git
      - git@github.com:org/repo.git
      - https://github.com/org/repo
    """
    # SSH-style URL
    if clone_url.startswith("git@"):
        path = clone_url.split(":")[-1]
    else:
        parsed = urlparse(clone_url)
        path = parsed.path

    # Strip .git suffix and leading slashes
    name = path.rstrip("/").rsplit("/", 1)[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name or "unknown-repo"


def _get_repo_path(project_id: int, repo_name: str) -> Path:
    return Path(REPO_BASE_DIR) / f"project_{project_id}" / repo_name


def _inject_token_into_url(clone_url: str, token: str) -> str:
    """Inject a GitHub token into an HTTPS clone URL for auth.

    Converts https://github.com/org/repo.git
    into     https://x-access-token:{token}@github.com/org/repo.git
    """
    if not token or not clone_url.startswith("https://"):
        return clone_url

    parsed = urlparse(clone_url)
    authed = parsed._replace(netloc=f"x-access-token:{token}@{parsed.hostname}")
    return authed.geturl()


def _should_index_file(file_path: Path) -> bool:
    """Check if a file should be browsable/ingestable based on extension."""
    # Check multi-part extensions first (e.g. .env.example)
    name = file_path.name
    for ext in INDEXABLE_EXTENSIONS:
        if name.endswith(ext):
            return True
    return file_path.suffix.lower() in INDEXABLE_EXTENSIONS


def _get_github_token() -> Optional[str]:
    """Get GitHub token from the environment (GITHUB_TOKEN)."""
    return os.environ.get("GITHUB_TOKEN") or None


async def _run_git(
    cmd: list,
    timeout: int = GIT_COMMAND_TIMEOUT,
    env: Optional[dict] = None,
) -> subprocess.CompletedProcess:
    """Run a git command in a worker thread.

    asyncio.create_subprocess_exec raises NotImplementedError under the
    WindowsSelectorEventLoopPolicy that main.py installs, so blocking
    subprocess.run is used via asyncio.to_thread instead.

    Always disables interactive credential prompts so auth failures fail
    fast with a clear stderr message instead of hanging until the
    subprocess timeout (e.g. private repo with no GITHUB_TOKEN).
    """
    run_env = dict(env) if env is not None else os.environ.copy()
    run_env["GIT_TERMINAL_PROMPT"] = "0"
    run_env.setdefault("GCM_INTERACTIVE", "never")
    return await asyncio.to_thread(
        subprocess.run,
        cmd,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=run_env,
    )


def _iter_browsable_files(repo_path: Path):
    """Yield files in the repo that pass the extension/excluded-dir filters."""
    for file_path in repo_path.rglob("*"):
        if not file_path.is_file():
            continue
        rel_parts = file_path.relative_to(repo_path).parts
        if any(part in EXCLUDED_DIRS for part in rel_parts):
            continue
        if not _should_index_file(file_path):
            continue
        yield file_path


def _count_browsable_files(repo_path: Path) -> int:
    """Count browsable files in a cloned repo."""
    return sum(1 for _ in _iter_browsable_files(repo_path))


async def clone_repo(repo_id: int) -> dict:
    """Clone a git repository to local storage.

    Returns dict with clone results.
    """
    db: Session = SessionLocal()
    token: Optional[str] = None
    try:
        repo = db.query(GitRepository).filter(GitRepository.id == repo_id).first()
        if not repo:
            raise ValueError(f"Repository {repo_id} not found")

        # Update status
        repo.sync_status = RepoSyncStatus.CLONING
        repo.last_error = None
        db.commit()

        # Determine local path
        repo_path = _get_repo_path(repo.project_id, repo.repo_name)
        repo_path.parent.mkdir(parents=True, exist_ok=True)

        # If directory already exists, remove it for a clean clone
        if repo_path.exists():
            shutil.rmtree(repo_path)

        # Build clone URL with token if available
        clone_url = repo.clone_url
        token = _get_github_token()
        if token:
            clone_url = _inject_token_into_url(clone_url, token)

        # Run git clone
        cmd = [
            "git", "clone",
            "--branch", repo.branch,
            "--single-branch",
            "--depth", "1",
            clone_url,
            str(repo_path),
        ]

        result = await _run_git(cmd, timeout=GIT_CLONE_TIMEOUT)

        if result.returncode != 0:
            error_msg = (result.stderr or "").strip()
            # Scrub any token from the error message
            if token:
                error_msg = error_msg.replace(token, "***")
            repo.sync_status = RepoSyncStatus.ERROR
            repo.last_error = error_msg
            db.commit()
            raise RuntimeError(f"git clone failed: {error_msg}")

        # Strip the token from the on-disk remote URL — git clone persists the
        # authed URL in .git/config otherwise (mirrors pull_repo's cleanup).
        if token:
            try:
                clean_cmd = ["git", "-C", str(repo_path), "remote", "set-url", "origin", repo.clone_url]
                await _run_git(clean_cmd)
            except Exception:
                logger.warning("Failed to restore clean remote URL after clone")

        # Get HEAD commit hash
        commit_hash = await _get_head_commit(repo_path)

        # Update repo record
        repo.local_path = str(repo_path)
        repo.last_commit_hash = commit_hash
        repo.last_synced_at = datetime.now(timezone.utc)
        repo.sync_status = RepoSyncStatus.SYNCED
        repo.indexed_files_count = await asyncio.to_thread(_count_browsable_files, repo_path)
        db.commit()

        logger.info(f"Cloned {repo.repo_name} to {repo_path} (commit: {commit_hash[:7]})")
        return {
            "success": True,
            "repo_id": repo_id,
            "local_path": str(repo_path),
            "commit_hash": commit_hash,
            "files_count": repo.indexed_files_count,
        }

    except Exception as e:
        # Ensure error status is set
        try:
            repo = db.query(GitRepository).filter(GitRepository.id == repo_id).first()
            if repo and repo.sync_status != RepoSyncStatus.ERROR:
                error_msg = str(e)
                if token:
                    error_msg = error_msg.replace(token, "***")
                repo.sync_status = RepoSyncStatus.ERROR
                repo.last_error = error_msg
                db.commit()
        except Exception:
            pass
        raise
    finally:
        db.close()


async def pull_repo(repo_id: int) -> dict:
    """Pull latest changes for an already-cloned repository."""
    db: Session = SessionLocal()
    token: Optional[str] = None
    clone_url_clean: Optional[str] = None
    repo_path: Optional[Path] = None

    try:
        repo = db.query(GitRepository).filter(GitRepository.id == repo_id).first()
        if not repo:
            raise ValueError(f"Repository {repo_id} not found")

        if not repo.local_path or not Path(repo.local_path).exists():
            raise ValueError(f"Repository {repo.repo_name} is not cloned locally")

        repo.sync_status = RepoSyncStatus.SYNCING
        repo.last_error = None
        db.commit()

        repo_path = Path(repo.local_path)
        clone_url_clean = repo.clone_url

        # Inject token into remote URL if available
        token = _get_github_token()
        env = os.environ.copy()
        if token:
            env["GIT_TERMINAL_PROMPT"] = "0"
            authed_url = _inject_token_into_url(repo.clone_url, token)
            set_cmd = ["git", "-C", str(repo_path), "remote", "set-url", "origin", authed_url]
            await _run_git(set_cmd)

        # Run git pull
        cmd = ["git", "-C", str(repo_path), "pull", "--ff-only"]
        result = await _run_git(cmd, timeout=GIT_PULL_TIMEOUT, env=env)

        if result.returncode != 0:
            error_msg = (result.stderr or "").strip()
            if token:
                error_msg = error_msg.replace(token, "***")
            repo.sync_status = RepoSyncStatus.ERROR
            repo.last_error = error_msg
            db.commit()
            raise RuntimeError(f"git pull failed: {error_msg}")

        commit_hash = await _get_head_commit(repo_path)

        repo.last_commit_hash = commit_hash
        repo.last_synced_at = datetime.now(timezone.utc)
        repo.sync_status = RepoSyncStatus.SYNCED
        repo.indexed_files_count = await asyncio.to_thread(_count_browsable_files, repo_path)
        db.commit()

        logger.info(f"Pulled {repo.repo_name} (commit: {commit_hash[:7]})")
        return {
            "success": True,
            "repo_id": repo_id,
            "commit_hash": commit_hash,
            "files_count": repo.indexed_files_count,
        }

    except Exception as e:
        try:
            repo = db.query(GitRepository).filter(GitRepository.id == repo_id).first()
            if repo and repo.sync_status != RepoSyncStatus.ERROR:
                error_msg = str(e)
                if token:
                    error_msg = error_msg.replace(token, "***")
                repo.sync_status = RepoSyncStatus.ERROR
                repo.last_error = error_msg
                db.commit()
        except Exception:
            pass
        raise
    finally:
        # Always restore clean remote URL if we injected a token
        if token and repo_path and clone_url_clean:
            try:
                clean_cmd = ["git", "-C", str(repo_path), "remote", "set-url", "origin", clone_url_clean]
                await _run_git(clean_cmd)
            except Exception:
                logger.warning("Failed to restore clean remote URL after pull")
        db.close()


async def delete_repo(repo_id: int) -> bool:
    """Delete a repository: remove from disk and database."""
    db: Session = SessionLocal()
    try:
        repo = db.query(GitRepository).filter(GitRepository.id == repo_id).first()
        if not repo:
            return False

        # 1. Delete from disk
        if repo.local_path and Path(repo.local_path).exists():
            shutil.rmtree(repo.local_path, ignore_errors=True)

        # 2. Delete DB record
        db.delete(repo)
        db.commit()

        logger.info(f"Deleted repository {repo.repo_name} (id={repo_id})")
        return True

    finally:
        db.close()


def list_repo_files(repo_id: int) -> list:
    """List browsable files in a repository."""
    db: Session = SessionLocal()
    try:
        repo = db.query(GitRepository).filter(GitRepository.id == repo_id).first()
        if not repo or not repo.local_path:
            return []

        repo_path = Path(repo.local_path)
        if not repo_path.exists():
            return []

        files = []
        for file_path in _iter_browsable_files(repo_path):
            relative_path = str(file_path.relative_to(repo_path)).replace("\\", "/")
            files.append({
                "path": relative_path,
                "size": file_path.stat().st_size,
                "extension": file_path.suffix,
            })

        return sorted(files, key=lambda f: f["path"])

    finally:
        db.close()


async def _get_head_commit(repo_path: Path) -> str:
    """Get the HEAD commit hash for a local repo."""
    result = await _run_git(["git", "-C", str(repo_path), "rev-parse", "HEAD"])
    return (result.stdout or "").strip()
