# pyright: reportUnknownVariableType=false
"""Bounded in-memory secret cache with TTL and revocation."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any

from etlantic.runtime.context import TrustedExecutionScope
from etlantic.secrets.ref import SecretRef
from etlantic.secrets.value import SecretValue


@dataclass
class _CacheEntry:
    value: SecretValue
    expires_at: float
    lease_id: str | None = None


@dataclass
class SecretCache:
    """Process-local bounded secret cache (never serialized)."""

    max_entries: int = 128
    default_ttl_seconds: float = 60.0
    _entries: dict[tuple[str, tuple[str, ...] | None], _CacheEntry] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if type(self.max_entries) is not int or self.max_entries < 1:
            raise ValueError("max_entries must be a positive integer")
        self.default_ttl_seconds = _validated_ttl(
            self.default_ttl_seconds, field_name="default_ttl_seconds"
        )

    def _key(
        self,
        reference: SecretRef,
        trusted_scope: TrustedExecutionScope | None = None,
    ) -> tuple[str, tuple[str, ...] | None]:
        """Partition managed cache entries by their authenticated authority."""
        return (
            reference.identity(),
            trusted_scope.cache_partition if trusted_scope is not None else None,
        )

    def get(
        self,
        reference: SecretRef,
        *,
        trusted_scope: TrustedExecutionScope | None = None,
    ) -> SecretValue | None:
        key = self._key(reference, trusted_scope)
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at <= time.monotonic():
            self._entries.pop(key, None)
            return None
        return entry.value

    def put(
        self,
        reference: SecretRef,
        value: SecretValue,
        *,
        ttl_seconds: float | None = None,
        lease_id: str | None = None,
        trusted_scope: TrustedExecutionScope | None = None,
    ) -> None:
        if type(self.max_entries) is not int or self.max_entries < 1:
            raise ValueError("max_entries must be a positive integer")
        ttl = _validated_ttl(
            self.default_ttl_seconds if ttl_seconds is None else ttl_seconds,
            field_name="ttl_seconds",
        )
        key = self._key(reference, trusted_scope)
        if ttl == 0:
            self._entries.pop(key, None)
            return
        while len(self._entries) >= self.max_entries and self._entries:
            oldest = next(iter(self._entries))
            self._entries.pop(oldest, None)
        self._entries[key] = _CacheEntry(
            value=value,
            expires_at=time.monotonic() + ttl,
            lease_id=lease_id,
        )

    def invalidate(self, reference: SecretRef | None = None) -> None:
        if reference is None:
            self._entries.clear()
            return
        identity = reference.identity()
        for key in tuple(self._entries):
            if key[0] == identity:
                self._entries.pop(key, None)

    def revoke(self, *, provider: str | None = None, name: str | None = None) -> int:
        """Invalidate matching entries; return count removed."""
        to_remove = [
            key
            for key, entry in self._entries.items()
            if (provider is None or entry.value.provider == provider)
            and (name is None or entry.value.name == name)
        ]
        for key in to_remove:
            self._entries.pop(key, None)
        return len(to_remove)

    def stats(self) -> dict[str, Any]:
        return {
            "entries": len(self._entries),
            "max_entries": self.max_entries,
            "default_ttl_seconds": self.default_ttl_seconds,
        }


def _validated_ttl(value: float, *, field_name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{field_name} must be a finite non-negative number")
    return float(value)
