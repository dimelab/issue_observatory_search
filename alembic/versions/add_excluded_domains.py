"""Add excluded_domains to scraping jobs

Revision ID: add_excluded_domains
Revises: (check existing migrations)
Create Date: 2025-01-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_excluded_domains'
down_revision = None  # TODO: Set this to the latest migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add excluded_domains column to scraping_jobs table."""
    op.add_column(
        'scraping_jobs',
        sa.Column('excluded_domains', postgresql.JSON(astext_type=sa.Text()), nullable=True)
    )


def downgrade() -> None:
    """Remove excluded_domains column from scraping_jobs table."""
    op.drop_column('scraping_jobs', 'excluded_domains')
