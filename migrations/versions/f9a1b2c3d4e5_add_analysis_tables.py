"""add analysis tables

Revision ID: f9a1b2c3d4e5
Revises: e7f8a9b2c3d4
Create Date: 2025-10-23 23:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'f9a1b2c3d4e5'
down_revision = 'e7f8a9b2c3d4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create analysis tables for NLP processing results."""

    # Create content_analysis table
    op.create_table(
        'content_analysis',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('website_content_id', sa.Integer(), nullable=False),
        sa.Column('extract_nouns', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('extract_entities', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('max_nouns', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('min_frequency', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('nouns_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('entities_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('processing_duration', sa.Float(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['website_content_id'], ['website_content.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('website_content_id', name='uq_content_analysis_content_id')
    )

    # Create indexes for content_analysis
    op.create_index('ix_content_analysis_website_content_id', 'content_analysis', ['website_content_id'])
    op.create_index('ix_content_analysis_status', 'content_analysis', ['status'])
    op.create_index('ix_content_analysis_created_at', 'content_analysis', ['created_at'])

    # Create extracted_nouns table
    op.create_table(
        'extracted_nouns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('website_content_id', sa.Integer(), nullable=False),
        sa.Column('word', sa.String(length=255), nullable=False),
        sa.Column('lemma', sa.String(length=255), nullable=False),
        sa.Column('frequency', sa.Integer(), nullable=False),
        sa.Column('tfidf_score', sa.Float(), nullable=False),
        sa.Column('positions', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('language', sa.String(length=10), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['website_content_id'], ['website_content.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for extracted_nouns
    op.create_index('ix_extracted_nouns_website_content_id', 'extracted_nouns', ['website_content_id'])
    op.create_index('ix_extracted_nouns_word', 'extracted_nouns', ['word'])
    op.create_index('ix_extracted_nouns_lemma', 'extracted_nouns', ['lemma'])
    op.create_index('ix_extracted_nouns_tfidf_score', 'extracted_nouns', ['tfidf_score'])
    op.create_index('ix_extracted_nouns_language', 'extracted_nouns', ['language'])
    op.create_index('ix_extracted_nouns_created_at', 'extracted_nouns', ['created_at'])

    # Create composite index for common queries
    op.create_index(
        'ix_extracted_nouns_content_tfidf',
        'extracted_nouns',
        ['website_content_id', 'tfidf_score'],
        postgresql_using='btree'
    )

    # Create extracted_entities table
    op.create_table(
        'extracted_entities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('website_content_id', sa.Integer(), nullable=False),
        sa.Column('text', sa.String(length=500), nullable=False),
        sa.Column('label', sa.String(length=50), nullable=False),
        sa.Column('start_pos', sa.Integer(), nullable=False),
        sa.Column('end_pos', sa.Integer(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('language', sa.String(length=10), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['website_content_id'], ['website_content.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for extracted_entities
    op.create_index('ix_extracted_entities_website_content_id', 'extracted_entities', ['website_content_id'])
    op.create_index('ix_extracted_entities_text', 'extracted_entities', ['text'])
    op.create_index('ix_extracted_entities_label', 'extracted_entities', ['label'])
    op.create_index('ix_extracted_entities_language', 'extracted_entities', ['language'])
    op.create_index('ix_extracted_entities_created_at', 'extracted_entities', ['created_at'])

    # Create composite index for common queries
    op.create_index(
        'ix_extracted_entities_content_label',
        'extracted_entities',
        ['website_content_id', 'label'],
        postgresql_using='btree'
    )


def downgrade() -> None:
    """Drop analysis tables."""

    # Drop indexes first
    op.drop_index('ix_extracted_entities_content_label', table_name='extracted_entities')
    op.drop_index('ix_extracted_entities_created_at', table_name='extracted_entities')
    op.drop_index('ix_extracted_entities_language', table_name='extracted_entities')
    op.drop_index('ix_extracted_entities_label', table_name='extracted_entities')
    op.drop_index('ix_extracted_entities_text', table_name='extracted_entities')
    op.drop_index('ix_extracted_entities_website_content_id', table_name='extracted_entities')

    op.drop_index('ix_extracted_nouns_content_tfidf', table_name='extracted_nouns')
    op.drop_index('ix_extracted_nouns_created_at', table_name='extracted_nouns')
    op.drop_index('ix_extracted_nouns_language', table_name='extracted_nouns')
    op.drop_index('ix_extracted_nouns_tfidf_score', table_name='extracted_nouns')
    op.drop_index('ix_extracted_nouns_lemma', table_name='extracted_nouns')
    op.drop_index('ix_extracted_nouns_word', table_name='extracted_nouns')
    op.drop_index('ix_extracted_nouns_website_content_id', table_name='extracted_nouns')

    op.drop_index('ix_content_analysis_created_at', table_name='content_analysis')
    op.drop_index('ix_content_analysis_status', table_name='content_analysis')
    op.drop_index('ix_content_analysis_website_content_id', table_name='content_analysis')

    # Drop tables
    op.drop_table('extracted_entities')
    op.drop_table('extracted_nouns')
    op.drop_table('content_analysis')
