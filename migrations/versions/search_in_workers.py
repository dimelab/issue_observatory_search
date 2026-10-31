"""Run searches in Celery workers: task id and failure message on search sessions

Revision ID: search_in_workers
Revises: scrape_already_collected
Create Date: 2026-11-02 12:00:00.000000

Adds search_sessions.celery_task_id (the task queued for the session) and
search_sessions.error_message (why a search failed). Progress needs no columns: it is
counted from the statuses of the session's queries, and search_sessions.updated_at is the
running search's heartbeat.

Each column is only added if it is missing, so the migration is safe on a database where
it was added by hand.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "search_in_workers"
down_revision = "scrape_already_collected"
branch_labels = None
depends_on = None

TABLE = "search_sessions"


def _columns() -> set:
    """Names of the table's columns (only meaningful when online)."""
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(TABLE)}


def upgrade() -> None:
    """Add celery_task_id and error_message (existing sessions get NULL)."""
    offline = op.get_context().as_sql  # SQL-script mode cannot inspect the database
    existing = set() if offline else _columns()
    if "celery_task_id" not in existing:
        op.add_column(
            TABLE, sa.Column("celery_task_id", sa.String(length=255), nullable=True)
        )
    if "error_message" not in existing:
        op.add_column(TABLE, sa.Column("error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    """Drop celery_task_id and error_message."""
    offline = op.get_context().as_sql
    existing = None if offline else _columns()
    for column in ("error_message", "celery_task_id"):
        if existing is None or column in existing:
            op.drop_column(TABLE, column)
