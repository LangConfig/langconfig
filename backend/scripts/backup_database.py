#!/usr/bin/env python3
# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Database Backup and Restore Utilities for LangConfig.

This script provides utilities for backing up and restoring the PostgreSQL database.

Usage:
    python backup_database.py backup                    # Create a backup
    python backup_database.py restore --file <path>     # Restore from backup
    python backup_database.py list                      # List available backups

Environment Variables:
    DATABASE_URL: PostgreSQL connection string
    BACKUP_DIR: Directory to store backups (default: ./backups)
"""

import subprocess
import datetime
import os
import logging
import argparse
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Backup configuration
BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "./backups"))
BACKUP_DIR.mkdir(exist_ok=True, parents=True)


def get_database_url():
    """Get database URL from environment."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError(
            "DATABASE_URL environment variable is not set. "
            "Please set it to your PostgreSQL connection string."
        )
    return db_url


def backup_database(output_file: str = None) -> str:
    """
    Create database backup using pg_dump.

    Args:
        output_file: Optional path to output file. If not provided, generates one.

    Returns:
        Path to backup file

    Raises:
        Exception: If backup fails
    """
    if output_file is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = BACKUP_DIR / f"langconfig_backup_{timestamp}.dump"
    else:
        output_file = Path(output_file)

    db_url = get_database_url()

    logger.info(f"Creating backup: {output_file}")
    logger.info(f"Backup directory: {output_file.parent.absolute()}")

    try:
        result = subprocess.run(
            [
                "pg_dump",
                "--dbname", db_url,
                "--file", str(output_file),
                "--format=custom",  # Compressed binary format
                "--verbose"
            ],
            capture_output=True,
            text=True,
            check=True
        )

        # Check file was created and has content
        if not output_file.exists():
            raise Exception("Backup file was not created")

        file_size = output_file.stat().st_size
        file_size_mb = file_size / (1024 * 1024)

        logger.info(f"✓ Backup created successfully")
        logger.info(f"  File: {output_file}")
        logger.info(f"  Size: {file_size_mb:.2f} MB")

        return str(output_file)

    except subprocess.CalledProcessError as e:
        logger.error(f"Backup failed with exit code {e.returncode}")
        logger.error(f"stdout: {e.stdout}")
        logger.error(f"stderr: {e.stderr}")
        raise Exception(f"Backup failed: {e.stderr}")
    except FileNotFoundError:
        raise Exception(
            "pg_dump command not found. Please ensure PostgreSQL client tools are installed "
            "and pg_dump is in your PATH."
        )


def restore_database(backup_file: str, drop_existing: bool = True):
    """
    Restore database from backup file.

    WARNING: This will overwrite the current database!

    Args:
        backup_file: Path to backup file
        drop_existing: If True, drops existing database objects before restore

    Raises:
        Exception: If restore fails
    """
    backup_path = Path(backup_file)

    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_file}")

    db_url = get_database_url()

    logger.warning("=" * 60)
    logger.warning("WARNING: DATABASE RESTORE OPERATION")
    logger.warning("=" * 60)
    logger.warning(f"Restoring from backup: {backup_file}")
    logger.warning("This will OVERWRITE the current database!")
    logger.warning("=" * 60)

    # Confirm before proceeding
    response = input("Type 'YES' to confirm database restore: ")
    if response != "YES":
        logger.info("Restore cancelled by user")
        return

    logger.info("Starting database restore...")

    try:
        # Build pg_restore command
        cmd = [
            "pg_restore",
            "--dbname", db_url,
            "--verbose"
        ]

        if drop_existing:
            cmd.extend(["--clean", "--if-exists"])

        cmd.append(str(backup_path))

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        logger.info("✓ Database restored successfully")
        logger.info(f"  From: {backup_file}")

    except subprocess.CalledProcessError as e:
        logger.error(f"Restore failed with exit code {e.returncode}")
        logger.error(f"stdout: {e.stdout}")
        logger.error(f"stderr: {e.stderr}")
        raise Exception(f"Restore failed: {e.stderr}")
    except FileNotFoundError:
        raise Exception(
            "pg_restore command not found. Please ensure PostgreSQL client tools are installed "
            "and pg_restore is in your PATH."
        )


def list_backups() -> list:
    """
    List all available backups.

    Returns:
        List of backup file paths (sorted by date, newest first)
    """
    backups = sorted(
        BACKUP_DIR.glob("langconfig_backup_*.dump"),
        reverse=True,
        key=lambda p: p.stat().st_mtime
    )
    return [str(b) for b in backups]


def print_backups():
    """Print list of available backups with details."""
    backups = list_backups()

    if not backups:
        logger.info("No backups found")
        logger.info(f"Backup directory: {BACKUP_DIR.absolute()}")
        return

    logger.info(f"Available backups ({len(backups)}) in {BACKUP_DIR.absolute()}:")
    logger.info("")

    for backup_path in backups:
        path = Path(backup_path)
        file_size_mb = path.stat().st_size / (1024 * 1024)
        modified_time = datetime.datetime.fromtimestamp(path.stat().st_mtime)

        logger.info(f"  • {path.name}")
        logger.info(f"    Size: {file_size_mb:.2f} MB")
        logger.info(f"    Date: {modified_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("")


def main():
    """Main entry point for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Database backup and restore utilities for LangConfig"
    )
    parser.add_argument(
        "command",
        choices=["backup", "restore", "list"],
        help="Command to execute"
    )
    parser.add_argument(
        "--file",
        help="Backup file path (for restore command)"
    )
    parser.add_argument(
        "--output",
        help="Output file path (for backup command)"
    )
    parser.add_argument(
        "--no-drop",
        action="store_true",
        help="Don't drop existing objects before restore (for restore command)"
    )

    args = parser.parse_args()

    try:
        if args.command == "backup":
            backup_file = backup_database(output_file=args.output)
            print(f"\n✓ Backup created: {backup_file}")

        elif args.command == "restore":
            if not args.file:
                parser.error("--file is required for restore command")
            restore_database(args.file, drop_existing=not args.no_drop)

        elif args.command == "list":
            print_backups()

    except Exception as e:
        logger.error(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
