"""Database query profiler for slow query logging."""
import time
import logging
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine
from backend.config import settings

logger = logging.getLogger(__name__)


def setup_db_profiler(engine: AsyncEngine) -> None:
    """
    Setup database query profiler.

    Logs slow queries (> threshold) with timing information.
    Helps identify performance bottlenecks.

    Args:
        engine: SQLAlchemy async engine
    """

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        """Record query start time."""
        conn.info.setdefault("query_start_time", []).append(time.time())

    @event.listens_for(engine.sync_engine, "after_cursor_execute")
    def after_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        """
        Log slow queries.

        Calculates query execution time and logs queries that exceed
        the slow threshold.
        """
        total = time.time() - conn.info["query_start_time"].pop()

        if total > settings.query_slow_threshold:
            # Clean up statement for logging
            clean_statement = " ".join(statement.split())
            if len(clean_statement) > 200:
                clean_statement = clean_statement[:200] + "..."

            logger.warning(
                f"SLOW QUERY ({total:.3f}s): {clean_statement}"
            )

            # In debug mode, log full query and parameters
            if settings.debug:
                logger.debug(
                    f"Full query: {statement}\n"
                    f"Parameters: {parameters}"
                )

    logger.info(
        f"Database profiler enabled "
        f"(slow query threshold: {settings.query_slow_threshold}s)"
    )
