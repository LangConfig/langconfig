"""add gpt-image-2 tool template type

Revision ID: 016_add_gpt_image_2
Revises: 015_pii_profiles
Create Date: 2026-06-01 00:10:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "016_add_gpt_image_2"
down_revision = "015_pii_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TYPE tooltemplatetype ADD VALUE IF NOT EXISTS 'image_openai_gpt_image_2'"
    ))


def downgrade() -> None:
    print("Note: Cannot remove enum value 'image_openai_gpt_image_2' from PostgreSQL enum")
