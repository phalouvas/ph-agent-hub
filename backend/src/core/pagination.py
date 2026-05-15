# =============================================================================
# PH Agent Hub — Pagination Utilities
# =============================================================================
# Shared helpers for server-side pagination, sorting, and filtering across
# all admin list endpoints.
# =============================================================================

from __future__ import annotations

import math
from typing import Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy import func, select, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response envelope used by all admin list endpoints."""

    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


async def paginate(
    db: AsyncSession,
    base_stmt,
    page: int | None = None,
    page_size: int = 25,
) -> tuple[list, int]:
    """Execute a paginated query and return (items, total).

    The base_stmt should be a fully-formed select() with WHERE clauses and
    ORDER BY already applied.  When ``page`` is None, returns ALL matching
    rows without pagination.  When ``page`` is an integer, applies
    LIMIT/OFFSET and runs a parallel COUNT(*).
    """
    if page is None:
        # Return all items without pagination
        result = await db.execute(base_stmt)
        items = list(result.scalars().all())
        return items, len(items)

    # Count total matching rows
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    stmt = base_stmt.offset(offset).limit(page_size)
    result = await db.execute(stmt)
    items = list(result.scalars().all())

    return items, total


def apply_sorting(
    stmt,
    sort_by: str | None,
    sort_dir: str | None,
    column_map: dict[str, object],
    default_sort: object | None = None,
):
    """Apply ORDER BY to a statement from a column_name→SA column mapping.

    ``column_map`` maps API-facing sort_by values to SQLAlchemy column
    objects.  If ``sort_by`` is not in the map, the ``default_sort`` is
    used (which defaults to no ordering).
    """
    if sort_by and sort_by in column_map:
        col = column_map[sort_by]
        order_fn = desc if (sort_dir or "").lower() == "desc" else asc
        stmt = stmt.order_by(order_fn(col))
    elif default_sort is not None:
        stmt = stmt.order_by(default_sort)
    return stmt


def apply_search(
    stmt,
    search: str | None,
    columns: list[object],
):
    """Apply a LIKE filter across one or more columns.

    Each column is wrapped with ``column.ilike('%search%')``, combined
    with OR.  If search is empty or None the statement is returned unchanged.
    """
    if not search:
        return stmt
    terms = search.strip().split()
    if not terms:
        return stmt
    from sqlalchemy import or_
    filters = []
    for col in columns:
        for term in terms:
            filters.append(col.ilike(f"%{term}%"))
    return stmt.where(or_(*filters))
