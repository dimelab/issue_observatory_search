"""Pagination utilities for database queries."""
from typing import Generic, TypeVar, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy import Select, func
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """
    Paginated response model.

    Contains items for the current page plus metadata about total results
    and pagination state.

    Attributes:
        items: List of items for current page
        total: Total number of items across all pages
        page: Current page number (1-indexed)
        per_page: Number of items per page
        pages: Total number of pages
        has_next: Whether there is a next page
        has_prev: Whether there is a previous page

    Example:
        {
            "items": [...],
            "total": 250,
            "page": 2,
            "per_page": 50,
            "pages": 5,
            "has_next": true,
            "has_prev": true
        }
    """
    items: List[T]
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., ge=1, description="Current page number")
    per_page: int = Field(..., ge=1, description="Items per page")
    pages: int = Field(..., ge=0, description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "items": [],
                "total": 250,
                "page": 2,
                "per_page": 50,
                "pages": 5,
                "has_next": True,
                "has_prev": True,
            }
        }


async def paginate(
    query: Select,
    db: AsyncSession,
    page: int = 1,
    per_page: int = 50,
    max_per_page: Optional[int] = None
) -> Page:
    """
    Paginate SQLAlchemy query.

    Executes two queries:
    1. COUNT query to get total number of results
    2. SELECT query with LIMIT/OFFSET to get page items

    Args:
        query: SQLAlchemy select statement
        db: Database session
        page: Page number (1-indexed, default: 1)
        per_page: Items per page (default: 50)
        max_per_page: Maximum items per page (optional)

    Returns:
        Page object with items and metadata

    Raises:
        ValueError: If page < 1 or per_page < 1

    Example:
        from sqlalchemy import select
        from backend.models.search import SearchSession

        # Build query
        query = select(SearchSession).where(SearchSession.user_id == user_id)

        # Paginate
        page_result = await paginate(query, db, page=2, per_page=50)

        # Access results
        sessions = page_result.items
        total = page_result.total
        has_more = page_result.has_next
    """
    # Validate parameters
    if page < 1:
        raise ValueError("Page must be >= 1")
    if per_page < 1:
        raise ValueError("Per page must be >= 1")

    # Apply max per_page limit
    if max_per_page and per_page > max_per_page:
        per_page = max_per_page

    # Count total items
    count_query = select(func.count()).select_from(query.subquery())
    result = await db.execute(count_query)
    total = result.scalar_one()

    # Calculate pagination metadata
    pages = (total + per_page - 1) // per_page if total > 0 else 0

    # Handle page out of range
    if page > pages and pages > 0:
        page = pages

    # Get page items
    offset = (page - 1) * per_page
    paginated_query = query.offset(offset).limit(per_page)
    result = await db.execute(paginated_query)
    items = result.scalars().all()

    return Page(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
        has_next=page < pages,
        has_prev=page > 1,
    )


async def paginate_cursor(
    query: Select,
    db: AsyncSession,
    cursor_column: str,
    cursor: Optional[str] = None,
    per_page: int = 50,
    direction: str = "forward"
) -> tuple[List, Optional[str], bool]:
    """
    Cursor-based pagination for better performance on large datasets.

    Uses keyset pagination which is more efficient than OFFSET-based
    pagination for large datasets.

    Args:
        query: SQLAlchemy select statement
        db: Database session
        cursor_column: Column name to use for cursor (e.g., "id", "created_at")
        cursor: Cursor value from previous page (optional)
        per_page: Items per page (default: 50)
        direction: "forward" or "backward"

    Returns:
        Tuple of (items, next_cursor, has_more)

    Example:
        from sqlalchemy import select
        from backend.models.search import SearchSession

        query = select(SearchSession).order_by(SearchSession.created_at.desc())

        # First page
        items, next_cursor, has_more = await paginate_cursor(
            query, db, "created_at", per_page=50
        )

        # Next page
        items, next_cursor, has_more = await paginate_cursor(
            query, db, "created_at", cursor=next_cursor, per_page=50
        )
    """
    # Apply cursor filter
    if cursor:
        if direction == "forward":
            query = query.where(getattr(query.column_descriptions[0]["type"], cursor_column) > cursor)
        else:
            query = query.where(getattr(query.column_descriptions[0]["type"], cursor_column) < cursor)

    # Fetch per_page + 1 to check if there are more items
    limited_query = query.limit(per_page + 1)
    result = await db.execute(limited_query)
    items = result.scalars().all()

    # Check if there are more items
    has_more = len(items) > per_page

    # Remove extra item
    if has_more:
        items = items[:per_page]

    # Get cursor for next page
    next_cursor = None
    if has_more and items:
        last_item = items[-1]
        next_cursor = str(getattr(last_item, cursor_column))

    return items, next_cursor, has_more


class PaginationParams(BaseModel):
    """
    Query parameters for pagination.

    Use as dependency in FastAPI endpoints.

    Example:
        @router.get("/sessions")
        async def get_sessions(
            pagination: PaginationParams = Depends(),
            db: AsyncSession = Depends(get_db)
        ):
            query = select(SearchSession)
            page = await paginate(query, db, pagination.page, pagination.per_page)
            return page
    """
    page: int = Field(default=1, ge=1, description="Page number")
    per_page: int = Field(default=50, ge=1, le=500, description="Items per page")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "page": 1,
                "per_page": 50
            }
        }
