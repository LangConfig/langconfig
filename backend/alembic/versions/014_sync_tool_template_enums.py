# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""sync all tool enum values to PostgreSQL

Ensures all ToolType and ToolTemplateType Python enum values exist in the
corresponding PostgreSQL enum types. Prevents INSERT failures when new
enum values are added in code but not synced to the database.

Revision ID: 014_sync_tool_enums
Revises: 013_workflow_triggers
Create Date: 2026-02-26 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '014_sync_tool_enums'
down_revision = '013_workflow_triggers'
branch_labels = None
depends_on = None

# All values that must exist, sourced from the Python enums in models/custom_tool.py
TOOLTYPE_VALUES = [
    "api",
    "notification",
    "image_video",
    "database",
    "data_transform",
]

TOOLTEMPLATETYPE_VALUES = [
    "notification_slack",
    "notification_discord",
    "api_webhook",
    "image_openai_dalle3",
    "image_openai_sora",
    "image_openai_gpt_image_1_5",
    "image_gemini_imagen3",
    "image_gemini_nano_banana",
    "image_gemini_nano_banana_2",
    "video_gemini_veo3",
    "video_gemini_veo31",
    "database_postgres",
    "database_mysql",
    "database_mongodb",
    "data_transform_json",
    "custom",
]


def _get_existing_enum_values(conn, enum_name: str) -> set:
    """Query pg_enum for all current values of a PostgreSQL enum type."""
    result = conn.execute(sa.text(
        "SELECT enumlabel FROM pg_enum "
        "WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = :name)"
    ), {"name": enum_name})
    return {row[0] for row in result}


def _sync_enum(conn, enum_name: str, expected_values: list[str]) -> None:
    """Add any missing values to a PostgreSQL enum type."""
    existing = _get_existing_enum_values(conn, enum_name)
    missing = [v for v in expected_values if v not in existing]

    if not missing:
        print(f"  {enum_name}: all {len(expected_values)} values present")
        return

    for value in missing:
        conn.execute(sa.text(
            f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS :val"
        ), {"val": value})
        print(f"  {enum_name}: added '{value}'")

    print(f"  {enum_name}: synced {len(missing)} missing value(s)")


def upgrade() -> None:
    """Sync all Python enum values into PostgreSQL enum types."""
    conn = op.get_bind()

    print("Syncing tool enum types...")
    _sync_enum(conn, "tooltype", TOOLTYPE_VALUES)
    _sync_enum(conn, "tooltemplatetype", TOOLTEMPLATETYPE_VALUES)


def downgrade() -> None:
    """Cannot easily remove enum values in PostgreSQL."""
    print("Note: Cannot remove enum values - PostgreSQL does not support DROP VALUE")
