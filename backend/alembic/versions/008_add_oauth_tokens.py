# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""add oauth_tokens table for Google OAuth integration

Revision ID: 008_oauth_tokens
Revises: 007_gpt_image_1_5
Create Date: 2025-01-05 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '008_oauth_tokens'
down_revision = '007_add_gpt_image_1_5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create oauth_tokens table for storing OAuth credentials securely."""

    # Get connection for checking existence
    conn = op.get_bind()

    # Check if oauth_tokens table already exists
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'oauth_tokens')"
    ))
    table_exists = result.scalar()

    if not table_exists:
        op.create_table(
            'oauth_tokens',
            sa.Column('id', sa.Integer(), nullable=False),

            # Provider identification
            sa.Column('provider', sa.String(length=50), nullable=False),

            # Token data (encrypted at application level)
            sa.Column('access_token', sa.Text(), nullable=False),
            sa.Column('refresh_token', sa.Text(), nullable=True),
            sa.Column('token_type', sa.String(length=50), default='Bearer', nullable=True),

            # Token metadata
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('scope', sa.Text(), nullable=True),

            # Timestamps
            sa.Column('created_at', sa.DateTime(timezone=True),
                      server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True),
                      server_default=sa.text('now()'), nullable=True),

            # Constraints
            sa.PrimaryKeyConstraint('id'),
            # Single-user app: one token per provider
            sa.UniqueConstraint('provider', name='uq_oauth_tokens_provider')
        )
    else:
        print("Note: oauth_tokens table already exists, skipping creation")

    # Create index on provider for efficient lookups
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_oauth_tokens_provider')"
    ))
    if not result.scalar():
        op.create_index(
            op.f('ix_oauth_tokens_provider'),
            'oauth_tokens',
            ['provider'],
            unique=True
        )


def downgrade() -> None:
    """Remove oauth_tokens table."""

    # Drop index
    op.drop_index(op.f('ix_oauth_tokens_provider'), table_name='oauth_tokens')

    # Drop table
    op.drop_table('oauth_tokens')
