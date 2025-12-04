# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Database Migration: Add Unique Constraint on Workflow Versions

Adds a unique constraint on (workflow_id, version_number) to prevent race conditions
that could create duplicate version numbers for the same workflow.

This is a SAFETY-CRITICAL migration that prevents data corruption from concurrent
version creation.

Usage:
    # Analyze impact (check for existing duplicates)
    python migrations/add_version_unique_constraint.py --analyze

    # Dry run (preview changes)
    python migrations/add_version_unique_constraint.py --dry-run

    # Execute migration
    python migrations/add_version_unique_constraint.py

    # Rollback (remove constraint)
    python migrations/add_version_unique_constraint.py --rollback
"""

import sys
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# Migration Functions
# =============================================================================

def analyze_duplicates(session) -> Dict[str, Any]:
    """
    Analyze the database for duplicate version numbers.

    Returns:
        Dictionary with analysis results including duplicate counts and details
    """
    logger.info("Analyzing workflow versions for duplicates...")

    # Query for duplicate version numbers
    query = text("""
        SELECT workflow_id, version_number, COUNT(*) as count
        FROM workflow_versions
        GROUP BY workflow_id, version_number
        HAVING COUNT(*) > 1
        ORDER BY workflow_id, version_number
    """)

    duplicates = session.execute(query).fetchall()

    analysis = {
        "total_versions": 0,
        "unique_versions": 0,
        "duplicate_groups": len(duplicates),
        "total_duplicate_records": 0,
        "duplicates": []
    }

    # Get total version count
    total_query = text("SELECT COUNT(*) FROM workflow_versions")
    analysis["total_versions"] = session.execute(total_query).scalar()

    # Calculate unique versions
    unique_query = text("""
        SELECT COUNT(*) FROM (
            SELECT DISTINCT workflow_id, version_number
            FROM workflow_versions
        ) as unique_versions
    """)
    analysis["unique_versions"] = session.execute(unique_query).scalar()

    # Get details for each duplicate group
    for workflow_id, version_number, count in duplicates:
        analysis["total_duplicate_records"] += count

        # Get details of duplicate records
        detail_query = text("""
            SELECT id, created_at, is_current, notes
            FROM workflow_versions
            WHERE workflow_id = :workflow_id AND version_number = :version_number
            ORDER BY created_at ASC
        """)

        records = session.execute(
            detail_query,
            {"workflow_id": workflow_id, "version_number": version_number}
        ).fetchall()

        analysis["duplicates"].append({
            "workflow_id": workflow_id,
            "version_number": version_number,
            "duplicate_count": count,
            "records": [
                {
                    "id": r[0],
                    "created_at": r[1].isoformat() if r[1] else None,
                    "is_current": r[2],
                    "notes": r[3]
                }
                for r in records
            ]
        })

    return analysis


def fix_duplicates(session, dry_run: bool = False) -> Dict[str, Any]:
    """
    Fix duplicate version numbers by renumbering the newer versions.

    Strategy:
    - Keep the oldest version with the original number
    - Renumber newer duplicates to the next available version number

    Args:
        session: Database session
        dry_run: If True, only simulate the fix

    Returns:
        Dictionary with fix results
    """
    logger.info(f"{'DRY RUN: ' if dry_run else ''}Fixing duplicate version numbers...")

    # Query for duplicates
    duplicates_query = text("""
        SELECT workflow_id, version_number, COUNT(*) as count
        FROM workflow_versions
        GROUP BY workflow_id, version_number
        HAVING COUNT(*) > 1
        ORDER BY workflow_id, version_number
    """)

    duplicates = session.execute(duplicates_query).fetchall()

    results = {
        "duplicate_groups_fixed": 0,
        "records_renumbered": 0,
        "changes": []
    }

    for workflow_id, version_number, count in duplicates:
        logger.info(f"Fixing workflow {workflow_id}, version {version_number} ({count} duplicates)")

        # Get all versions for this workflow/version combo, ordered by creation time
        versions_query = text("""
            SELECT id, version_number, created_at
            FROM workflow_versions
            WHERE workflow_id = :workflow_id AND version_number = :version_number
            ORDER BY created_at ASC
        """)

        versions = session.execute(
            versions_query,
            {"workflow_id": workflow_id, "version_number": version_number}
        ).fetchall()

        # Keep first (oldest), renumber the rest
        for idx, (version_id, old_version_num, created_at) in enumerate(versions[1:], start=1):
            # Find next available version number for this workflow
            max_version_query = text("""
                SELECT COALESCE(MAX(version_number), 0) + 1
                FROM workflow_versions
                WHERE workflow_id = :workflow_id
            """)

            new_version_num = session.execute(
                max_version_query,
                {"workflow_id": workflow_id}
            ).scalar()

            logger.info(f"  Renumbering version ID {version_id}: v{old_version_num} → v{new_version_num}")

            if not dry_run:
                # Update the version number
                update_query = text("""
                    UPDATE workflow_versions
                    SET version_number = :new_version
                    WHERE id = :version_id
                """)

                session.execute(
                    update_query,
                    {"new_version": new_version_num, "version_id": version_id}
                )

            results["records_renumbered"] += 1
            results["changes"].append({
                "workflow_id": workflow_id,
                "version_id": version_id,
                "old_version": old_version_num,
                "new_version": new_version_num,
                "created_at": created_at.isoformat() if created_at else None
            })

        results["duplicate_groups_fixed"] += 1

    if not dry_run and duplicates:
        session.commit()
        logger.info("✓ Duplicate fixes committed to database")
    elif duplicates:
        logger.info("✓ DRY RUN completed (no changes made)")
    else:
        logger.info("✓ No duplicates found - nothing to fix")

    return results


def add_unique_constraint(session, dry_run: bool = False) -> Dict[str, Any]:
    """
    Add the unique constraint on (workflow_id, version_number).

    Args:
        session: Database session
        dry_run: If True, only simulate adding the constraint

    Returns:
        Dictionary with operation results
    """
    logger.info(f"{'DRY RUN: ' if dry_run else ''}Adding unique constraint...")

    results = {
        "constraint_added": False,
        "error": None
    }

    # Check if constraint already exists
    check_query = text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'workflow_versions'
        AND constraint_name = 'uq_workflow_version_number'
    """)

    existing = session.execute(check_query).fetchone()

    if existing:
        logger.warning("Constraint 'uq_workflow_version_number' already exists")
        results["constraint_added"] = False
        results["error"] = "Constraint already exists"
        return results

    if not dry_run:
        try:
            # Add the unique constraint
            constraint_query = text("""
                ALTER TABLE workflow_versions
                ADD CONSTRAINT uq_workflow_version_number
                UNIQUE (workflow_id, version_number)
            """)

            session.execute(constraint_query)
            session.commit()

            logger.info("✓ Unique constraint added successfully")
            results["constraint_added"] = True

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to add constraint: {e}")
            results["error"] = str(e)
            raise
    else:
        logger.info("✓ DRY RUN: Would add constraint 'uq_workflow_version_number'")
        results["constraint_added"] = True

    return results


def remove_unique_constraint(session) -> Dict[str, Any]:
    """
    Remove the unique constraint (rollback operation).

    Args:
        session: Database session

    Returns:
        Dictionary with operation results
    """
    logger.info("Removing unique constraint...")

    results = {
        "constraint_removed": False,
        "error": None
    }

    # Check if constraint exists
    check_query = text("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'workflow_versions'
        AND constraint_name = 'uq_workflow_version_number'
    """)

    existing = session.execute(check_query).fetchone()

    if not existing:
        logger.warning("Constraint 'uq_workflow_version_number' does not exist")
        results["error"] = "Constraint does not exist"
        return results

    try:
        # Remove the constraint
        drop_query = text("""
            ALTER TABLE workflow_versions
            DROP CONSTRAINT IF EXISTS uq_workflow_version_number
        """)

        session.execute(drop_query)
        session.commit()

        logger.info("✓ Unique constraint removed successfully")
        results["constraint_removed"] = True

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to remove constraint: {e}")
        results["error"] = str(e)
        raise

    return results


# =============================================================================
# Main CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Add unique constraint on workflow version numbers"
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Analyze for duplicate versions only (no changes)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without executing"
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Remove the unique constraint"
    )
    parser.add_argument(
        "--fix-only",
        action="store_true",
        help="Only fix duplicates without adding constraint"
    )

    args = parser.parse_args()

    # Get database URL from environment
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://langconfig:langconfig_dev@localhost:5433/langconfig"
    )

    # Create database session
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        # Rollback mode - remove constraint
        if args.rollback:
            results = remove_unique_constraint(session)
            logger.info("\n=== Rollback Results ===")
            if results["constraint_removed"]:
                logger.info("✓ Constraint removed successfully")
            else:
                logger.warning(f"Constraint not removed: {results.get('error', 'Unknown error')}")
            return 0 if results["constraint_removed"] else 1

        # Analysis mode - just check for duplicates
        if args.analyze:
            analysis = analyze_duplicates(session)
            logger.info("\n=== Duplicate Analysis ===")
            logger.info(f"Total versions: {analysis['total_versions']}")
            logger.info(f"Unique versions: {analysis['unique_versions']}")
            logger.info(f"Duplicate groups: {analysis['duplicate_groups']}")
            logger.info(f"Total duplicate records: {analysis['total_duplicate_records']}")

            if analysis['duplicates']:
                logger.info("\nDuplicate details:")
                for dup in analysis['duplicates']:
                    logger.info(f"\n  Workflow {dup['workflow_id']}, Version {dup['version_number']}:")
                    logger.info(f"    {dup['duplicate_count']} duplicate records")
                    for record in dup['records']:
                        logger.info(f"      ID {record['id']}: "
                                  f"created {record['created_at']}, "
                                  f"is_current={record['is_current']}")
            else:
                logger.info("\n✓ No duplicates found - safe to add constraint")

            return 0

        # Migration mode - fix duplicates and add constraint
        logger.info("=== Starting Migration ===\n")

        # Step 1: Analyze duplicates
        logger.info("Step 1: Analyzing for duplicates...")
        analysis = analyze_duplicates(session)

        if analysis['duplicate_groups'] > 0:
            logger.warning(f"Found {analysis['duplicate_groups']} duplicate groups "
                         f"({analysis['total_duplicate_records']} total records)")

            # Step 2: Fix duplicates
            logger.info("\nStep 2: Fixing duplicates...")
            fix_results = fix_duplicates(session, dry_run=args.dry_run)

            logger.info(f"  Groups fixed: {fix_results['duplicate_groups_fixed']}")
            logger.info(f"  Records renumbered: {fix_results['records_renumbered']}")

            if fix_results['changes']:
                logger.info("\n  Changes made:")
                for change in fix_results['changes'][:10]:  # Show first 10
                    logger.info(f"    Workflow {change['workflow_id']}, "
                              f"Version ID {change['version_id']}: "
                              f"v{change['old_version']} → v{change['new_version']}")
                if len(fix_results['changes']) > 10:
                    logger.info(f"    ... and {len(fix_results['changes']) - 10} more changes")
        else:
            logger.info("Step 1: No duplicates found - skipping fix step")

        # Step 3: Add constraint (unless --fix-only)
        if not args.fix_only:
            logger.info("\nStep 3: Adding unique constraint...")
            constraint_results = add_unique_constraint(session, dry_run=args.dry_run)

            if constraint_results['constraint_added']:
                logger.info("✓ Constraint added successfully")
            elif constraint_results['error']:
                logger.error(f"✗ Failed to add constraint: {constraint_results['error']}")
                return 1
        else:
            logger.info("\nStep 3: Skipped (--fix-only specified)")

        # Summary
        logger.info("\n=== Migration Summary ===")
        if args.dry_run:
            logger.info("✓ DRY RUN completed successfully")
            logger.info("Run without --dry-run to execute migration")
        else:
            logger.info("✓ Migration completed successfully")
            logger.info("\nThe unique constraint will now prevent duplicate version numbers")
            logger.info("Concurrent version creation attempts will receive a 409 Conflict error")

        return 0

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        return 1

    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
