"""Page / item / byte ceilings for connector listing and reads."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from typing import Any, TypeVar

from etlantic.connectors.errors import ConnectorReadError

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class BatchCeilings:
    """Hard ceilings for pagination and materialization."""

    max_pages: int = 1_000
    max_items: int = 1_000_000
    max_bytes: int = 256 * 1024 * 1024
    max_page_items: int = 10_000
    max_concurrency: int = 4

    def __post_init__(self) -> None:
        for name in (
            "max_pages",
            "max_items",
            "max_bytes",
            "max_page_items",
            "max_concurrency",
        ):
            if int(getattr(self, name)) < 1:
                raise ValueError(f"{name} must be >= 1")


@dataclass
class BatchBudget:
    """Mutable remaining budget tracker."""

    ceilings: BatchCeilings
    pages: int = 0
    items: int = 0
    bytes_used: int = 0

    def consume_page(self, *, item_count: int, byte_count: int = 0) -> None:
        if item_count > self.ceilings.max_page_items:
            raise ConnectorReadError(
                f"page item count {item_count} exceeds max_page_items "
                f"{self.ceilings.max_page_items}",
                code="PMCONN930",
            )
        next_pages = self.pages + 1
        if next_pages > self.ceilings.max_pages:
            raise ConnectorReadError(
                f"page ceiling exceeded ({self.ceilings.max_pages})",
                code="PMCONN931",
            )
        next_items = self.items + item_count
        if next_items > self.ceilings.max_items:
            raise ConnectorReadError(
                f"item ceiling exceeded ({self.ceilings.max_items})",
                code="PMCONN932",
            )
        next_bytes = self.bytes_used + max(0, byte_count)
        if next_bytes > self.ceilings.max_bytes:
            raise ConnectorReadError(
                f"byte ceiling exceeded ({self.ceilings.max_bytes})",
                code="PMCONN933",
            )
        self.pages = next_pages
        self.items = next_items
        self.bytes_used = next_bytes

    def remaining_items(self) -> int:
        return max(0, self.ceilings.max_items - self.items)

    def remaining_bytes(self) -> int:
        return max(0, self.ceilings.max_bytes - self.bytes_used)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pages": self.pages,
            "items": self.items,
            "bytes": self.bytes_used,
            "ceilings": {
                "max_pages": self.ceilings.max_pages,
                "max_items": self.ceilings.max_items,
                "max_bytes": self.ceilings.max_bytes,
                "max_page_items": self.ceilings.max_page_items,
                "max_concurrency": self.ceilings.max_concurrency,
            },
        }


def iter_capped(
    items: Iterable[T],
    *,
    max_items: int,
    size_of: Callable[[T], int] | None = None,
    max_bytes: int | None = None,
    provider: str | None = None,
) -> Iterator[T]:
    """Yield items until item or byte ceilings are hit (then raise)."""
    count = 0
    bytes_used = 0
    for count, item in enumerate(items, start=1):
        if count > max_items:
            raise ConnectorReadError(
                f"item ceiling exceeded ({max_items})",
                code="PMCONN932",
                provider=provider,
            )
        if size_of is not None and max_bytes is not None:
            bytes_used += int(size_of(item))
            if bytes_used > max_bytes:
                raise ConnectorReadError(
                    f"byte ceiling exceeded ({max_bytes})",
                    code="PMCONN933",
                    provider=provider,
                )
        yield item


__all__ = [
    "BatchBudget",
    "BatchCeilings",
    "iter_capped",
]
