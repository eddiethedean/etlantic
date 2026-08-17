"""Experimental Confluent-compatible schema-registry adapter (fake HTTP)."""

from __future__ import annotations

import os

from etlantic.streaming.registry import InMemorySchemaRegistry

__version__ = "0.47.0"


def live_registry_url() -> str | None:
    value = str(os.environ.get("ETLANTIC_SCHEMA_REGISTRY_URL") or "").strip()
    return value or None


class FakeConfluentRegistry(InMemorySchemaRegistry):
    """In-process Confluent-compatible adapter (no HTTP client in default tests)."""

    vendor: str = "confluent-fake"

    def subjects(self) -> list[str]:
        return sorted(self._subjects)

    def get_versions(self, subject: str) -> list[int]:
        return [item.version for item in self._subjects.get(subject) or ()]

    def get_config(self, subject: str) -> dict[str, str]:
        versions = self._subjects.get(subject) or []
        mode = versions[-1].compatibility.value if versions else "backward"
        return {"compatibility": mode, "vendor": self.vendor}


def create_registry() -> FakeConfluentRegistry:
    return FakeConfluentRegistry()


__all__ = [
    "FakeConfluentRegistry",
    "__version__",
    "create_registry",
    "live_registry_url",
]
