# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Seed generic LangConfig development data.

This script intentionally creates open-source LangConfig demo data only. It must
not import private, consulting, client, or project-specific rows.

Seeded recipe workflows are marked as templates (is_template=True) with
category/icon/tags metadata so the UI can surface them as an out-of-box
template gallery.

Usage:
    python backend/db/seed_langconfig_dev.py
    python backend/db/seed_langconfig_dev.py --refresh-templates

--refresh-templates re-syncs the configuration/blueprint/metadata of existing
template rows (matched by name AND is_template=True) with the current recipe
definitions, and creates any missing templates. It NEVER touches user
workflows (rows with is_template=False are skipped).
"""

import argparse
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
            "default_model": "gpt-5.4",
            "theme": "langconfig",
            "seeded_by": "seed_langconfig_dev",
        },
    )
    db.add(project)
    db.flush()
    logger.info("Created project: %s", project.name)
    return project


def _recipe_configuration(recipe) -> dict:
    return {
        "nodes": recipe.nodes,
        "edges": recipe.edges,
        "recipe_id": recipe.recipe_id,
        "tags": recipe.tags,
    }


def _apply_template_metadata(workflow: WorkflowProfile, recipe) -> None:
    workflow.is_template = True
    workflow.template_category = recipe.category
    workflow.template_icon = recipe.icon
    workflow.template_tags = list(recipe.tags)


def _seed_recipe_workflows(db, project: Project, refresh_templates: bool = False) -> tuple:
    """Insert-if-missing template workflows; optionally refresh existing templates.

    Returns (created_count, updated_count).
    """
    created = 0
    updated = 0
    for recipe in get_all_recipes():
        workflow = db.query(WorkflowProfile).filter(
            WorkflowProfile.name == recipe.name
        ).first()

        configuration = _recipe_configuration(recipe)

        if workflow:
            if workflow.project_id is None:
                workflow.project_id = project.id

            # Backfill template metadata on rows created by older seeder
            # versions (provably seeded: configuration carries our recipe_id).
            seeded_by_us = (
                isinstance(workflow.configuration, dict)
                and workflow.configuration.get("recipe_id") == recipe.recipe_id
            )
            if not workflow.is_template and seeded_by_us:
                _apply_template_metadata(workflow, recipe)
                logger.info("Backfilled template metadata: %s", workflow.name)

            if refresh_templates:
                if not workflow.is_template:
                    logger.info(
                        "Skipping '%s': name matches a recipe but row is not a "
                        "template (user workflow is never modified)",
                        recipe.name,
                    )
                    continue
                workflow.description = recipe.description
                workflow.configuration = configuration
                workflow.blueprint = configuration
                _apply_template_metadata(workflow, recipe)
                updated += 1
                logger.info("Refreshed template workflow: %s", workflow.name)
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
            is_template=True,
            template_category=recipe.category,
            template_icon=recipe.icon,
            template_tags=list(recipe.tags),
        )
        db.add(workflow)
        db.flush()
        created += 1
        logger.info("Created template workflow: %s", workflow.name)

        if project.workflow_profile_id is None:
            project.workflow_profile_id = workflow.id

    return created, updated


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


def main(refresh_templates: bool = False) -> int:
    db = SessionLocal()
    try:
        existing_projects = db.query(Project).count()
        existing_workflows = db.query(WorkflowProfile).count()
        has_demo_project = db.query(Project).filter(Project.name == DEMO_PROJECT_NAME).first() is not None
        if (
            (existing_projects or existing_workflows)
            and not has_demo_project
            and not refresh_templates
        ):
            logger.info(
                "Existing LangConfig data detected (%s projects, %s workflows); skipping demo seed "
                "(use --refresh-templates to sync template workflows anyway)",
                existing_projects,
                existing_workflows,
            )
            return 0

        project = _get_or_create_demo_project(db)
        created, updated = _seed_recipe_workflows(db, project, refresh_templates=refresh_templates)
        pii_created = _seed_default_pii_profile(db)
        db.commit()

        logger.info("LangConfig dev seed complete")
        logger.info("  project: %s", project.name)
        logger.info("  template workflows created: %s", created)
        if refresh_templates:
            logger.info("  template workflows refreshed: %s", updated)
        logger.info("  default PII profile created: %s", pii_created)
        return 0
    except Exception:
        db.rollback()
        logger.exception("LangConfig dev seed failed")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed generic LangConfig development data.")
    parser.add_argument(
        "--refresh-templates",
        action="store_true",
        help="Update configuration/blueprint/metadata of existing template workflows "
             "(matched by name AND is_template=True) to the current recipe definitions. "
             "Never modifies user workflows.",
    )
    args = parser.parse_args()
    raise SystemExit(main(refresh_templates=args.refresh_templates))
