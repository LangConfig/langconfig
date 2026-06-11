# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Seed generic LangConfig development data.

This script intentionally creates open-source LangConfig demo data only. It must
not import private, consulting, client, or project-specific rows.

Usage:
    python backend/db/seed_langconfig_dev.py
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import SessionLocal
from models.core import IndexingStatus, Project, ProjectStatus
from models.pii_profile import PIIProfile
from models.workflow import WorkflowProfile, WorkflowStrategy
from core.templates.workflow_recipes import get_all_recipes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


DEMO_PROJECT_NAME = "LangConfig Demo"
DEFAULT_PII_PROFILE_NAME = "Default PII Redaction"


def _get_or_create_demo_project(db) -> Project:
    project = db.query(Project).filter(Project.name == DEMO_PROJECT_NAME).first()
    if project:
        return project

    project = Project(
        name=DEMO_PROJECT_NAME,
        description="Generic OSS workspace for trying LangConfig workflows.",
        status=ProjectStatus.IDLE,
        indexing_status=IndexingStatus.NOT_INDEXED,
        configuration={
            "default_model": "gpt-4o",
            "theme": "langconfig",
            "seeded_by": "seed_langconfig_dev",
        },
    )
    db.add(project)
    db.flush()
    logger.info("Created project: %s", project.name)
    return project


def _seed_recipe_workflows(db, project: Project) -> int:
    created = 0
    for recipe in get_all_recipes():
        workflow = db.query(WorkflowProfile).filter(
            WorkflowProfile.name == recipe.name
        ).first()

        configuration = {
            "nodes": recipe.nodes,
            "edges": recipe.edges,
            "recipe_id": recipe.recipe_id,
            "tags": recipe.tags,
        }

        if workflow:
            if workflow.project_id is None:
                workflow.project_id = project.id
            continue

        workflow = WorkflowProfile(
            name=recipe.name,
            description=recipe.description,
            project_id=project.id,
            strategy_type=WorkflowStrategy.DEFAULT_SEQUENTIAL,
            configuration=configuration,
            blueprint=configuration,
            schema_output_config=None,
            output_schema=None,
        )
        db.add(workflow)
        db.flush()
        created += 1
        logger.info("Created workflow: %s", workflow.name)

        if project.workflow_profile_id is None:
            project.workflow_profile_id = workflow.id

    return created


def _seed_default_pii_profile(db) -> bool:
    profile = db.query(PIIProfile).filter(
        PIIProfile.project_id.is_(None),
        PIIProfile.name == DEFAULT_PII_PROFILE_NAME,
    ).first()
    if profile:
        return False

    db.add(PIIProfile(
        project_id=None,
        name=DEFAULT_PII_PROFILE_NAME,
        description="Generic profile that enables the built-in PII detectors.",
        blocklist=[],
        allowlist=[],
        custom_types=[],
        enabled_builtin_types=[],
    ))
    logger.info("Created global PII profile: %s", DEFAULT_PII_PROFILE_NAME)
    return True


def main() -> int:
    db = SessionLocal()
    try:
        existing_projects = db.query(Project).count()
        existing_workflows = db.query(WorkflowProfile).count()
        has_demo_project = db.query(Project).filter(Project.name == DEMO_PROJECT_NAME).first() is not None
        if (existing_projects or existing_workflows) and not has_demo_project:
            logger.info(
                "Existing LangConfig data detected (%s projects, %s workflows); skipping demo seed",
                existing_projects,
                existing_workflows,
            )
            return 0

        project = _get_or_create_demo_project(db)
        workflow_count = _seed_recipe_workflows(db, project)
        pii_created = _seed_default_pii_profile(db)
        db.commit()

        logger.info("LangConfig dev seed complete")
        logger.info("  project: %s", project.name)
        logger.info("  workflows created: %s", workflow_count)
        logger.info("  default PII profile created: %s", pii_created)
        return 0
    except Exception:
        db.rollback()
        logger.exception("LangConfig dev seed failed")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
