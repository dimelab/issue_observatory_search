#!/usr/bin/env python3
"""List search results that were stored as Google redirect links.

Google returns result links beyond the top three as redirects
(google.com/goto?url=...). Searches made before the Serper client resolved them
(SerperSearch._resolve_links) stored those links instead of the real URLs. They
cannot be repaired afterwards, because Serper only resolves them shortly after
the search, so the keywords have to be searched again. This lists the affected
sessions and keywords and changes nothing.

Usage:
    python scripts/find_redirect_results.py
    python scripts/find_redirect_results.py --user 3
"""

# Add the project root to sys.path so "backend" resolves when this file is run
# as "python scripts/<name>.py" (sys.path[0] is the script's own directory).
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import asyncio
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.search_engines.base import is_google_redirect
from backend.database import AsyncSessionLocal
from backend.models.search import SearchQuery, SearchResult, SearchSession


async def find_redirect_results(
    db: AsyncSession, user_id: Optional[int] = None
) -> list[dict]:
    """
    Find the queries that hold Google redirect links as results.

    Args:
        db: Database session
        user_id: Only look at this user's sessions

    Returns:
        list[dict]: One entry per affected query, ordered by session and
            query: session_id, session_name, user_id, query_id, query_text,
            redirects (how many results are redirect links), total (all its
            results)
    """
    # The database narrows the candidates; is_google_redirect decides
    statement = select(SearchResult.query_id, SearchResult.url).where(
        SearchResult.url.like("%/goto%"), SearchResult.domain.like("%google.%")
    )
    redirects: dict[int, int] = {}
    for query_id, url in (await db.execute(statement)).all():
        if is_google_redirect(url):
            redirects[query_id] = redirects.get(query_id, 0) + 1
    if not redirects:
        return []

    statement = (
        select(
            SearchSession.id,
            SearchSession.name,
            SearchSession.user_id,
            SearchQuery.id,
            SearchQuery.query_text,
            func.count(SearchResult.id),
        )
        .join(SearchQuery, SearchQuery.session_id == SearchSession.id)
        .join(SearchResult, SearchResult.query_id == SearchQuery.id)
        .where(SearchQuery.id.in_(list(redirects)))
        .group_by(
            SearchSession.id,
            SearchSession.name,
            SearchSession.user_id,
            SearchQuery.id,
            SearchQuery.query_text,
        )
        .order_by(SearchSession.id, SearchQuery.id)
    )
    if user_id is not None:
        statement = statement.where(SearchSession.user_id == user_id)

    return [
        {
            "session_id": session_id,
            "session_name": session_name,
            "user_id": owner_id,
            "query_id": query_id,
            "query_text": query_text,
            "redirects": redirects[query_id],
            "total": total,
        }
        for session_id, session_name, owner_id, query_id, query_text, total in (
            await db.execute(statement)
        ).all()
    ]


def print_report(rows: list[dict]) -> None:
    """Print the affected keywords grouped by session."""
    if not rows:
        print("No search results stored as Google redirect links.")
        return

    current = None
    for row in rows:
        if row["session_id"] != current:
            current = row["session_id"]
            print(
                f"\nSession {row['session_id']} \"{row['session_name']}\" "
                f"(user {row['user_id']})"
            )
        print(
            f"  query {row['query_id']:>6}  {row['query_text']!r}: "
            f"{row['redirects']} of {row['total']} results are redirect links"
        )

    sessions = len({row["session_id"] for row in rows})
    links = sum(row["redirects"] for row in rows)
    print(
        f"\n{links} redirect links in {len(rows)} keywords of {sessions} sessions. "
        "They cannot be resolved now: search these keywords again."
    )


async def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="List search results stored as Google redirect links"
    )
    parser.add_argument("--user", type=int, help="only this user's sessions")
    args = parser.parse_args()

    async with AsyncSessionLocal() as db:
        print_report(await find_redirect_results(db, args.user))


if __name__ == "__main__":
    asyncio.run(main())
