"""add network exports table

Revision ID: a1b2c3d4e5f6
Revises: f9a1b2c3d4e5
Create Date: 2025-10-24 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f9a1b2c3d4e5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create network_exports table for Phase 6."""

    # Create network_exports table
    op.create_table(
        'network_exports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('session_ids', postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('node_count', sa.Integer(), nullable=False),
        sa.Column('edge_count', sa.Integer(), nullable=False),
        sa.Column('backboning_applied', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('backboning_algorithm', sa.String(length=50), nullable=True),
        sa.Column('backboning_alpha', sa.Float(), nullable=True),
        sa.Column('original_edge_count', sa.Integer(), nullable=True),
        sa.Column('backboning_statistics', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_network_exports_id', 'network_exports', ['id'])
    op.create_index('ix_network_exports_user_id', 'network_exports', ['user_id'])
    op.create_index('ix_network_exports_type', 'network_exports', ['type'])
    op.create_index('ix_network_exports_created_at', 'network_exports', ['created_at'])

    # Create GIN index for session_ids array (PostgreSQL-specific)
    op.create_index(
        'ix_network_exports_session_ids',
        'network_exports',
        ['session_ids'],
        postgresql_using='gin'
    )


def downgrade() -> None:
    """Drop network_exports table."""

    # Drop indexes
    op.drop_index('ix_network_exports_session_ids', table_name='network_exports')
    op.drop_index('ix_network_exports_created_at', table_name='network_exports')
    op.drop_index('ix_network_exports_type', table_name='network_exports')
    op.drop_index('ix_network_exports_user_id', table_name='network_exports')
    op.drop_index('ix_network_exports_id', table_name='network_exports')

    # Drop table
    op.drop_table('network_exports')
