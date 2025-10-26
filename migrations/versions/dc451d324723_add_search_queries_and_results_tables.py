"""Add search queries and results tables

Revision ID: dc451d324723
Revises: 3d1ba5a1ee1a
Create Date: 2025-10-23 08:58:05.546873

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dc451d324723'
down_revision: Union[str, Sequence[str], None] = '3d1ba5a1ee1a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create search_queries table
    op.create_table(
        'search_queries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('query_text', sa.String(length=500), nullable=False),
        sa.Column('search_engine', sa.String(length=50), nullable=False),
        sa.Column('max_results', sa.Integer(), nullable=False),
        sa.Column('allowed_domains', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('result_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['session_id'], ['search_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_search_queries_id'), 'search_queries', ['id'], unique=False)
    op.create_index(op.f('ix_search_queries_session_id'), 'search_queries', ['session_id'], unique=False)
    op.create_index(op.f('ix_search_queries_status'), 'search_queries', ['status'], unique=False)

    # Create search_results table
    op.create_table(
        'search_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('query_id', sa.Integer(), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('rank', sa.Integer(), nullable=False),
        sa.Column('domain', sa.String(length=255), nullable=False),
        sa.Column('scraped', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['query_id'], ['search_queries.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_search_results_domain'), 'search_results', ['domain'], unique=False)
    op.create_index(op.f('ix_search_results_id'), 'search_results', ['id'], unique=False)
    op.create_index(op.f('ix_search_results_query_id'), 'search_results', ['query_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('search_results')
    op.drop_table('search_queries')
