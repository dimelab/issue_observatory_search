"""Phase 7: Advanced search features.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2025-10-24 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'  # Points to network exports table
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema for Phase 7."""

    # Add new columns to search_queries table for advanced features
    op.add_column('search_queries', sa.Column('date_from', sa.DateTime(), nullable=True))
    op.add_column('search_queries', sa.Column('date_to', sa.DateTime(), nullable=True))
    op.add_column('search_queries', sa.Column('temporal_snapshot', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('search_queries', sa.Column('domain_whitelist', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('search_queries', sa.Column('domain_blacklist', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('search_queries', sa.Column('tld_filter', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('search_queries', sa.Column('sphere_filter', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('search_queries', sa.Column('framing_type', sa.String(length=50), nullable=True))
    op.add_column('search_queries', sa.Column('language', sa.String(length=10), nullable=True))

    # Create indexes for new columns
    op.create_index(op.f('ix_search_queries_date_from'), 'search_queries', ['date_from'], unique=False)
    op.create_index(op.f('ix_search_queries_date_to'), 'search_queries', ['date_to'], unique=False)
    op.create_index(op.f('ix_search_queries_framing_type'), 'search_queries', ['framing_type'], unique=False)
    op.create_index(op.f('ix_search_queries_language'), 'search_queries', ['language'], unique=False)

    # Create query_expansion_candidates table
    op.create_table(
        'query_expansion_candidates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('parent_query_id', sa.Integer(), nullable=True),
        sa.Column('candidate_term', sa.String(length=500), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('approved', sa.Boolean(), nullable=True),
        sa.Column('generation', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('approved_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['approved_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['parent_query_id'], ['search_queries.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['session_id'], ['search_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_query_expansion_candidates_id'), 'query_expansion_candidates', ['id'], unique=False)
    op.create_index(op.f('ix_query_expansion_candidates_session_id'), 'query_expansion_candidates', ['session_id'], unique=False)
    op.create_index(op.f('ix_query_expansion_candidates_parent_query_id'), 'query_expansion_candidates', ['parent_query_id'], unique=False)
    op.create_index(op.f('ix_query_expansion_candidates_candidate_term'), 'query_expansion_candidates', ['candidate_term'], unique=False)
    op.create_index(op.f('ix_query_expansion_candidates_source'), 'query_expansion_candidates', ['source'], unique=False)
    op.create_index(op.f('ix_query_expansion_candidates_approved'), 'query_expansion_candidates', ['approved'], unique=False)
    op.create_index(op.f('ix_query_expansion_candidates_generation'), 'query_expansion_candidates', ['generation'], unique=False)
    op.create_index(op.f('ix_query_expansion_candidates_created_at'), 'query_expansion_candidates', ['created_at'], unique=False)

    # Create query_templates table
    op.create_table(
        'query_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('framing_type', sa.String(length=50), nullable=False),
        sa.Column('template', sa.Text(), nullable=False),
        sa.Column('variables', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('language', sa.String(length=10), nullable=False),
        sa.Column('is_public', sa.Boolean(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_query_templates_id'), 'query_templates', ['id'], unique=False)
    op.create_index(op.f('ix_query_templates_user_id'), 'query_templates', ['user_id'], unique=False)
    op.create_index(op.f('ix_query_templates_name'), 'query_templates', ['name'], unique=False)
    op.create_index(op.f('ix_query_templates_framing_type'), 'query_templates', ['framing_type'], unique=False)
    op.create_index(op.f('ix_query_templates_language'), 'query_templates', ['language'], unique=False)
    op.create_index(op.f('ix_query_templates_is_public'), 'query_templates', ['is_public'], unique=False)

    # Create queries_from_templates table
    op.create_table(
        'queries_from_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=False),
        sa.Column('search_query_id', sa.Integer(), nullable=False),
        sa.Column('substitutions', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['search_query_id'], ['search_queries.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['template_id'], ['query_templates.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_queries_from_templates_id'), 'queries_from_templates', ['id'], unique=False)
    op.create_index(op.f('ix_queries_from_templates_template_id'), 'queries_from_templates', ['template_id'], unique=False)
    op.create_index(op.f('ix_queries_from_templates_search_query_id'), 'queries_from_templates', ['search_query_id'], unique=False)

    # Create bulk_search_uploads table
    op.create_table(
        'bulk_search_uploads',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('row_count', sa.Integer(), nullable=False),
        sa.Column('validation_status', sa.String(length=20), nullable=False),
        sa.Column('validation_errors', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('session_id', sa.Integer(), nullable=True),
        sa.Column('task_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['search_sessions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bulk_search_uploads_id'), 'bulk_search_uploads', ['id'], unique=False)
    op.create_index(op.f('ix_bulk_search_uploads_user_id'), 'bulk_search_uploads', ['user_id'], unique=False)
    op.create_index(op.f('ix_bulk_search_uploads_validation_status'), 'bulk_search_uploads', ['validation_status'], unique=False)
    op.create_index(op.f('ix_bulk_search_uploads_session_id'), 'bulk_search_uploads', ['session_id'], unique=False)
    op.create_index(op.f('ix_bulk_search_uploads_task_id'), 'bulk_search_uploads', ['task_id'], unique=False)

    # Create bulk_search_rows table
    op.create_table(
        'bulk_search_rows',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('upload_id', sa.Integer(), nullable=False),
        sa.Column('row_number', sa.Integer(), nullable=False),
        sa.Column('query_data', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('search_query_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['search_query_id'], ['search_queries.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['upload_id'], ['bulk_search_uploads.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bulk_search_rows_id'), 'bulk_search_rows', ['id'], unique=False)
    op.create_index(op.f('ix_bulk_search_rows_upload_id'), 'bulk_search_rows', ['upload_id'], unique=False)
    op.create_index(op.f('ix_bulk_search_rows_status'), 'bulk_search_rows', ['status'], unique=False)


def downgrade() -> None:
    """Downgrade database schema (rollback Phase 7)."""

    # Drop bulk search tables
    op.drop_index(op.f('ix_bulk_search_rows_status'), table_name='bulk_search_rows')
    op.drop_index(op.f('ix_bulk_search_rows_upload_id'), table_name='bulk_search_rows')
    op.drop_index(op.f('ix_bulk_search_rows_id'), table_name='bulk_search_rows')
    op.drop_table('bulk_search_rows')

    op.drop_index(op.f('ix_bulk_search_uploads_task_id'), table_name='bulk_search_uploads')
    op.drop_index(op.f('ix_bulk_search_uploads_session_id'), table_name='bulk_search_uploads')
    op.drop_index(op.f('ix_bulk_search_uploads_validation_status'), table_name='bulk_search_uploads')
    op.drop_index(op.f('ix_bulk_search_uploads_user_id'), table_name='bulk_search_uploads')
    op.drop_index(op.f('ix_bulk_search_uploads_id'), table_name='bulk_search_uploads')
    op.drop_table('bulk_search_uploads')

    # Drop template tables
    op.drop_index(op.f('ix_queries_from_templates_search_query_id'), table_name='queries_from_templates')
    op.drop_index(op.f('ix_queries_from_templates_template_id'), table_name='queries_from_templates')
    op.drop_index(op.f('ix_queries_from_templates_id'), table_name='queries_from_templates')
    op.drop_table('queries_from_templates')

    op.drop_index(op.f('ix_query_templates_is_public'), table_name='query_templates')
    op.drop_index(op.f('ix_query_templates_language'), table_name='query_templates')
    op.drop_index(op.f('ix_query_templates_framing_type'), table_name='query_templates')
    op.drop_index(op.f('ix_query_templates_name'), table_name='query_templates')
    op.drop_index(op.f('ix_query_templates_user_id'), table_name='query_templates')
    op.drop_index(op.f('ix_query_templates_id'), table_name='query_templates')
    op.drop_table('query_templates')

    # Drop query expansion table
    op.drop_index(op.f('ix_query_expansion_candidates_created_at'), table_name='query_expansion_candidates')
    op.drop_index(op.f('ix_query_expansion_candidates_generation'), table_name='query_expansion_candidates')
    op.drop_index(op.f('ix_query_expansion_candidates_approved'), table_name='query_expansion_candidates')
    op.drop_index(op.f('ix_query_expansion_candidates_source'), table_name='query_expansion_candidates')
    op.drop_index(op.f('ix_query_expansion_candidates_candidate_term'), table_name='query_expansion_candidates')
    op.drop_index(op.f('ix_query_expansion_candidates_parent_query_id'), table_name='query_expansion_candidates')
    op.drop_index(op.f('ix_query_expansion_candidates_session_id'), table_name='query_expansion_candidates')
    op.drop_index(op.f('ix_query_expansion_candidates_id'), table_name='query_expansion_candidates')
    op.drop_table('query_expansion_candidates')

    # Remove new columns from search_queries
    op.drop_index(op.f('ix_search_queries_language'), table_name='search_queries')
    op.drop_index(op.f('ix_search_queries_framing_type'), table_name='search_queries')
    op.drop_index(op.f('ix_search_queries_date_to'), table_name='search_queries')
    op.drop_index(op.f('ix_search_queries_date_from'), table_name='search_queries')

    op.drop_column('search_queries', 'language')
    op.drop_column('search_queries', 'framing_type')
    op.drop_column('search_queries', 'sphere_filter')
    op.drop_column('search_queries', 'tld_filter')
    op.drop_column('search_queries', 'domain_blacklist')
    op.drop_column('search_queries', 'domain_whitelist')
    op.drop_column('search_queries', 'temporal_snapshot')
    op.drop_column('search_queries', 'date_to')
    op.drop_column('search_queries', 'date_from')
