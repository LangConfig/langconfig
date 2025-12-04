# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""add index for chat sessions

Revision ID: 002_chat_session_index
Revises: dbbae99c3f1c
Create Date: 2025-01-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_chat_session_index'
down_revision = 'dbbae99c3f1c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create index for efficient lookup of chat sessions by agent template
    op.create_index(
        'idx_chat_sessions_agent_id_active',
        'chat_sessions',
        ['agent_id', 'is_active'],
        unique=False,
        postgresql_where=sa.text('is_active = true')
    )


def downgrade() -> None:
    # Drop the index
    op.drop_index(
        'idx_chat_sessions_agent_id_active',
        table_name='chat_sessions'
    )
