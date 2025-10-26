"""add scraping tables

Revision ID: e7f8a9b2c3d4
Revises: dc451d324723
Create Date: 2025-10-23 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e7f8a9b2c3d4'
down_revision = 'dc451d324723'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create scraping_jobs table
    op.create_table(
        'scraping_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('depth', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('domain_filter', sa.String(length=50), nullable=False, server_default='same_domain'),
        sa.Column('allowed_tlds', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('delay_min', sa.Float(), nullable=False, server_default='2.0'),
        sa.Column('delay_max', sa.Float(), nullable=False, server_default='5.0'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('timeout', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('respect_robots_txt', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('total_urls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('urls_scraped', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('urls_failed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('urls_skipped', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('current_depth', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('celery_task_id', sa.String(length=255), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['session_id'], ['search_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scraping_jobs_id'), 'scraping_jobs', ['id'], unique=False)
    op.create_index(op.f('ix_scraping_jobs_user_id'), 'scraping_jobs', ['user_id'], unique=False)
    op.create_index(op.f('ix_scraping_jobs_session_id'), 'scraping_jobs', ['session_id'], unique=False)
    op.create_index(op.f('ix_scraping_jobs_status'), 'scraping_jobs', ['status'], unique=False)
    op.create_index(op.f('ix_scraping_jobs_celery_task_id'), 'scraping_jobs', ['celery_task_id'], unique=False)
    op.create_index(op.f('ix_scraping_jobs_created_at'), 'scraping_jobs', ['created_at'], unique=False)

    # Update websites table - add new columns
    op.add_column('websites', sa.Column('meta_description', sa.Text(), nullable=True))

    # Update website_content table - add new columns
    op.add_column('website_content', sa.Column('scraping_job_id', sa.Integer(), nullable=True))
    op.add_column('website_content', sa.Column('html_content', sa.Text(), nullable=True))
    op.add_column('website_content', sa.Column('title', sa.String(length=500), nullable=True))
    op.add_column('website_content', sa.Column('meta_description', sa.Text(), nullable=True))
    op.add_column('website_content', sa.Column('parent_url', sa.Text(), nullable=True))
    op.add_column('website_content', sa.Column('outbound_links', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('website_content', sa.Column('http_status_code', sa.Integer(), nullable=True))
    op.add_column('website_content', sa.Column('final_url', sa.Text(), nullable=True))
    op.add_column('website_content', sa.Column('scrape_duration', sa.Integer(), nullable=True))

    # Add foreign key for scraping_job_id
    op.create_foreign_key(
        'fk_website_content_scraping_job_id',
        'website_content',
        'scraping_jobs',
        ['scraping_job_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Create indexes on new columns
    op.create_index(op.f('ix_website_content_scraping_job_id'), 'website_content', ['scraping_job_id'], unique=False)
    op.create_index(op.f('ix_website_content_url'), 'website_content', ['url'], unique=False)
    op.create_index(op.f('ix_website_content_scrape_depth'), 'website_content', ['scrape_depth'], unique=False)
    op.create_index(op.f('ix_website_content_status'), 'website_content', ['status'], unique=False)


def downgrade() -> None:
    # Drop indexes from website_content
    op.drop_index(op.f('ix_website_content_status'), table_name='website_content')
    op.drop_index(op.f('ix_website_content_scrape_depth'), table_name='website_content')
    op.drop_index(op.f('ix_website_content_url'), table_name='website_content')
    op.drop_index(op.f('ix_website_content_scraping_job_id'), table_name='website_content')

    # Drop foreign key from website_content
    op.drop_constraint('fk_website_content_scraping_job_id', 'website_content', type_='foreignkey')

    # Drop columns from website_content
    op.drop_column('website_content', 'scrape_duration')
    op.drop_column('website_content', 'final_url')
    op.drop_column('website_content', 'http_status_code')
    op.drop_column('website_content', 'outbound_links')
    op.drop_column('website_content', 'parent_url')
    op.drop_column('website_content', 'meta_description')
    op.drop_column('website_content', 'title')
    op.drop_column('website_content', 'html_content')
    op.drop_column('website_content', 'scraping_job_id')

    # Drop column from websites
    op.drop_column('websites', 'meta_description')

    # Drop indexes from scraping_jobs
    op.drop_index(op.f('ix_scraping_jobs_created_at'), table_name='scraping_jobs')
    op.drop_index(op.f('ix_scraping_jobs_celery_task_id'), table_name='scraping_jobs')
    op.drop_index(op.f('ix_scraping_jobs_status'), table_name='scraping_jobs')
    op.drop_index(op.f('ix_scraping_jobs_session_id'), table_name='scraping_jobs')
    op.drop_index(op.f('ix_scraping_jobs_user_id'), table_name='scraping_jobs')
    op.drop_index(op.f('ix_scraping_jobs_id'), table_name='scraping_jobs')

    # Drop scraping_jobs table
    op.drop_table('scraping_jobs')
