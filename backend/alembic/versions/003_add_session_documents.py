# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""add session documents and cost tracking

Revision ID: 003_session_documents
Revises: 002_chat_session_index
Create Date: 2025-01-16 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003_session_documents'
down_revision = '002_chat_session_index'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add session_documents table and cost tracking columns to chat_sessions."""

    # Get connection for checking existence
    conn = op.get_bind()

    # Add cost tracking columns to chat_sessions (check if they exist first)
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chat_sessions' AND column_name = 'total_cost_usd')"
    ))
    if not result.scalar():
        op.add_column('chat_sessions',
            sa.Column('total_cost_usd', sa.Float(), nullable=False, server_default='0.0')
        )

    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chat_sessions' AND column_name = 'rag_context_tokens')"
    ))
    if not result.scalar():
        op.add_column('chat_sessions',
            sa.Column('rag_context_tokens', sa.Integer(), nullable=False, server_default='0')
        )

    # Create enum types if they don't exist (reusing existing types from context_documents)
    # These are created when context_documents table was created, so we just reference them

    # Check and create DocumentType enum if it doesn't exist
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'documenttype')"
    ))
    if not result.scalar():
        conn.execute(sa.text(
            "CREATE TYPE documenttype AS ENUM ('text', 'markdown', 'pdf', 'code', 'json', 'other')"
        ))

    # Check and create IndexingStatus enum if it doesn't exist
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'indexingstatus')"
    ))
    if not result.scalar():
        conn.execute(sa.text(
            "CREATE TYPE indexingstatus AS ENUM ('not_indexed', 'indexing', 'ready', 'failed')"
        ))

    # Check if session_documents table already exists (from failed migration attempt)
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'session_documents')"
    ))
    table_exists = result.scalar()

    if not table_exists:
        # Create session_documents table
        op.create_table(
            'session_documents',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('session_id', sa.String(length=100), nullable=False),
            sa.Column('file_path', sa.String(length=500), nullable=False),
            sa.Column('filename', sa.String(length=255), nullable=False),
            sa.Column('original_filename', sa.String(length=255), nullable=False),
            sa.Column('file_size', sa.Integer(), nullable=False),
            sa.Column('mime_type', sa.String(length=100), nullable=True),
            sa.Column('document_type', postgresql.ENUM('text', 'markdown', 'pdf', 'code', 'json', 'other',
                        name='documenttype', create_type=False),
                nullable=False
            ),
            sa.Column('uploaded_at', sa.DateTime(timezone=True),
                      server_default=sa.text('now()'), nullable=False),
            sa.Column('message_index', sa.Integer(), nullable=True),
            sa.Column('indexing_status', postgresql.ENUM('not_indexed', 'indexing', 'ready', 'failed',
                        name='indexingstatus', create_type=False),
                nullable=False,
                server_default='not_indexed'
            ),
            sa.Column('indexed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('indexed_chunks_count', sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.session_id'],
                                   ondelete='CASCADE')
        )
    else:
        print("Note: session_documents table already exists, skipping creation")

    # Create indexes for efficient lookups (check if they exist first)
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_session_documents_id')"
    ))
    if not result.scalar():
        op.create_index(
            op.f('ix_session_documents_id'),
            'session_documents',
            ['id'],
            unique=False
        )

    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_session_documents_session_id')"
    ))
    if not result.scalar():
        op.create_index(
            op.f('ix_session_documents_session_id'),
            'session_documents',
            ['session_id'],
            unique=False
        )


def downgrade() -> None:
    """Remove session_documents table and cost tracking columns."""

    # Drop indexes
    op.drop_index(op.f('ix_session_documents_session_id'), table_name='session_documents')
    op.drop_index(op.f('ix_session_documents_id'), table_name='session_documents')

    # Drop session_documents table
    op.drop_table('session_documents')

    # Remove cost tracking columns from chat_sessions
    op.drop_column('chat_sessions', 'rag_context_tokens')
    op.drop_column('chat_sessions', 'total_cost_usd')
