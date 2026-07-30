"""Shared pagination primitives for bounded MCP list responses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Sequence, TypeVar


DEFAULT_PAGE_LIMIT = 100
MAX_PAGE_LIMIT = 1000

T = TypeVar("T")


@dataclass(frozen=True)
class Page(Generic[T]):
    """A bounded slice of a larger ordered result collection."""

    items: list[T]
    total_count: int
    offset: int
    limit: int
    next_offset: int | None

    def response_metadata(self) -> dict[str, int | None]:
        return {
            "count": self.total_count,
            "total_count": self.total_count,
            "returned_count": len(self.items),
            "offset": self.offset,
            "limit": self.limit,
            "next_offset": self.next_offset,
        }


def paginate(items: Sequence[T], *, offset: int = 0, limit: int = DEFAULT_PAGE_LIMIT) -> Page[T]:
    """Return one bounded page and a cursor for the next page, when present."""
    if offset < 0:
        raise ValueError("offset must be greater than or equal to 0")
    if limit < 1:
        raise ValueError("limit must be greater than or equal to 1")
    if limit > MAX_PAGE_LIMIT:
        raise ValueError(f"limit must not exceed {MAX_PAGE_LIMIT}")

    total_count = len(items)
    page_items = list(items[offset : offset + limit])
    next_offset = offset + limit if offset + limit < total_count else None
    return Page(
        items=page_items,
        total_count=total_count,
        offset=offset,
        limit=limit,
        next_offset=next_offset,
    )
