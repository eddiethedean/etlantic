"""Window specification helpers for portable analytic functions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from etlantic.transform.column import coerce_column
from etlantic.transform.protocol import PROFILE_WINDOW_V1, PROFILE_WINDOW_V2


@dataclass(frozen=True, slots=True)
class WindowSpec:
    """Immutable window specification."""

    partition_by: tuple[Any, ...] = ()
    order_by: tuple[Any, ...] = ()
    frame_type: str | None = None  # rows | range
    start: Any | None = None
    end: Any | None = None
    profiles: frozenset[str] = field(
        default_factory=lambda: frozenset({PROFILE_WINDOW_V1, PROFILE_WINDOW_V2})
    )

    def partitionBy(self, *cols: Any) -> WindowSpec:
        return WindowSpec(
            partition_by=tuple(cols),
            order_by=self.order_by,
            frame_type=self.frame_type,
            start=self.start,
            end=self.end,
            profiles=self.profiles,
        )

    def orderBy(self, *cols: Any) -> WindowSpec:
        return WindowSpec(
            partition_by=self.partition_by,
            order_by=tuple(cols),
            frame_type=self.frame_type,
            start=self.start,
            end=self.end,
            profiles=self.profiles,
        )

    def rowsBetween(self, start: Any, end: Any) -> WindowSpec:
        return WindowSpec(
            partition_by=self.partition_by,
            order_by=self.order_by,
            frame_type="rows",
            start=start,
            end=end,
            profiles=self.profiles,
        )

    def rangeBetween(self, start: Any, end: Any) -> WindowSpec:
        return WindowSpec(
            partition_by=self.partition_by,
            order_by=self.order_by,
            frame_type="range",
            start=start,
            end=end,
            profiles=self.profiles,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "partitionBy": [
                c if isinstance(c, str) else coerce_column(c).node
                for c in self.partition_by
            ],
            "orderBy": [
                {
                    "expression": coerce_column(c).node,
                    **(
                        {"direction": coerce_column(c).sort_direction}
                        if coerce_column(c).sort_direction
                        else {}
                    ),
                    **(
                        {"nulls": coerce_column(c).nulls}
                        if coerce_column(c).nulls
                        else {}
                    ),
                }
                for c in self.order_by
            ],
        }
        if self.frame_type is not None:
            payload["frame"] = {
                "type": self.frame_type,
                "start": self.start,
                "end": self.end,
            }
        return payload


class Window:
    """Factory for window specifications."""

    unboundedPreceding = "unboundedPreceding"
    unboundedFollowing = "unboundedFollowing"
    currentRow = "currentRow"

    @staticmethod
    def partitionBy(*cols: Any) -> WindowSpec:
        return WindowSpec().partitionBy(*cols)

    @staticmethod
    def orderBy(*cols: Any) -> WindowSpec:
        return WindowSpec().orderBy(*cols)
