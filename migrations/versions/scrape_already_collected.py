"""Record how many URLs a scraping job left out as already collected

Revision ID: scrape_already_collected
Revises: v6_0_0_enhancements
Create Date: 2026-10-15 12:00:00.000000

Adds scraping_jobs.urls_already_collected. A scraping job skips URLs that an earlier job
on the same search session scraped successfully; this column keeps how many, so the job
page can show it (total_urls only counts what the job itself works on).

The column is only added if it is missing, so the migration is safe on a database where
it was already added by hand.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'scrape_already_collected'
down_revision = 'v6_0_0_enhancements'
branch_labels = None
depends_on = None

TABLE = 'scraping_jobs'
COLUMN = 'urls_already_collected'


def _has_column() -> bool:
    """Whether scraping_jobs already has the column (only meaningful when online)."""
    inspector = sa.inspect(op.get_bind())
    return COLUMN in {column['name'] for column in inspector.get_columns(TABLE)}


def upgrade() -> None:
    """Add urls_already_collected (existing jobs get 0)."""
    offline = op.get_context().as_sql  # SQL-script mode cannot inspect the database
    if not offline and _has_column():
        return
    op.add_column(
        TABLE,
        sa.Column(COLUMN, sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    """Drop urls_already_collected."""
    offline = op.get_context().as_sql
    if offline or _has_column():
        op.drop_column(TABLE, COLUMN)
