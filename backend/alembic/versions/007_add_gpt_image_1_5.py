# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""add gpt-image-1.5 tool template type

Revision ID: 007_add_gpt_image_1_5
Revises: 006_skills_system
Create Date: 2025-12-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '007_add_gpt_image_1_5'
down_revision = '006_skills_system'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add image_openai_gpt_image_1_5 to tooltemplatetype enum."""
    conn = op.get_bind()

    # Check if the enum value already exists
    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM pg_enum
            WHERE enumlabel = 'image_openai_gpt_image_1_5'
            AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'tooltemplatetype')
        )
    """))
    enum_exists = result.scalar()

    if not enum_exists:
        # Add the new enum value
        conn.execute(sa.text(
            "ALTER TYPE tooltemplatetype ADD VALUE IF NOT EXISTS 'image_openai_gpt_image_1_5'"
        ))
        print("Added 'image_openai_gpt_image_1_5' to tooltemplatetype enum")
    else:
        print("Note: 'image_openai_gpt_image_1_5' already exists in tooltemplatetype enum")


def downgrade() -> None:
    """Cannot easily remove enum values in PostgreSQL."""
    # PostgreSQL doesn't support removing enum values easily
    # Would require recreating the enum type
    print("Note: Cannot remove enum value 'image_openai_gpt_image_1_5' - manual migration required")
