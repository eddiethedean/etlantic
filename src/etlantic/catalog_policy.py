"""Catalog / schema mutation authorization (domain-neutral).

Production profiles fail closed unless an explicit allowlist authorizes
catalog or schema mutations. No engine drivers live in core.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from etlantic.diagnostics import Diagnostic, Severity
from etlantic.plugin_trust import is_production_profile


class CatalogMutationKind(StrEnum):
    """Portable catalog / schema mutation kinds."""

    CREATE_NAMESPACE = "create_namespace"
    DROP_NAMESPACE = "drop_namespace"
    CREATE_TABLE = "create_table"
    DROP_TABLE = "drop_table"
    ALTER_TABLE = "alter_table"
    REFRESH_TABLE = "refresh_table"
    CROSS_SCHEMA_READ = "cross_schema_read"
    CROSS_SCHEMA_WRITE = "cross_schema_write"


@dataclass(frozen=True, slots=True)
class CatalogMutationPolicy:
    """Profile-scoped authorization for catalog/schema mutations."""

    allow_mutations: bool = False
    allowed_kinds: frozenset[str] = field(default_factory=frozenset)
    allowed_namespaces: frozenset[str] = field(default_factory=frozenset)
    production_fail_closed: bool = True

    def allows(
        self,
        kind: str | CatalogMutationKind,
        *,
        namespace: str | None = None,
        profile_name: str = "development",
        security_domain: str | None = None,
        security_mode: str | None = None,
    ) -> bool:
        key = kind.value if isinstance(kind, CatalogMutationKind) else str(kind)
        production = is_production_profile(
            name=profile_name,
            security_domain=security_domain,
            security_mode=security_mode,
        )
        if production and self.production_fail_closed and not self.allow_mutations:
            return False
        if not self.allow_mutations and production:
            return False
        if self.allowed_kinds and key not in self.allowed_kinds:
            return False
        if (
            namespace is not None
            and self.allowed_namespaces
            and namespace not in self.allowed_namespaces
        ):
            return False
        if production:
            return self.allow_mutations
        # Non-production: allow when explicitly enabled or unrestricted kinds.
        return self.allow_mutations or not self.allowed_kinds

    def authorize(
        self,
        kind: str | CatalogMutationKind,
        *,
        namespace: str | None = None,
        profile_name: str = "development",
        security_domain: str | None = None,
        security_mode: str | None = None,
        path: tuple[str, ...] = ("catalog", "mutation"),
    ) -> list[Diagnostic]:
        """Return error diagnostics when the mutation is not authorized."""
        if self.allows(
            kind,
            namespace=namespace,
            profile_name=profile_name,
            security_domain=security_domain,
            security_mode=security_mode,
        ):
            return []
        key = kind.value if isinstance(kind, CatalogMutationKind) else str(kind)
        return [
            Diagnostic(
                code="PMCAT100",
                severity=Severity.ERROR,
                message=(
                    f"Catalog mutation {key!r}"
                    + (f" on namespace {namespace!r}" if namespace else "")
                    + " is not authorized by CatalogMutationPolicy; failing closed."
                ),
                path=path,
                phase="catalog",
            )
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "allow_mutations": self.allow_mutations,
            "allowed_kinds": sorted(self.allowed_kinds),
            "allowed_namespaces": sorted(self.allowed_namespaces),
            "production_fail_closed": self.production_fail_closed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> CatalogMutationPolicy:
        raw = dict(data or {})
        return cls(
            allow_mutations=bool(raw.get("allow_mutations", False)),
            allowed_kinds=frozenset(str(x) for x in (raw.get("allowed_kinds") or ())),
            allowed_namespaces=frozenset(
                str(x) for x in (raw.get("allowed_namespaces") or ())
            ),
            production_fail_closed=bool(raw.get("production_fail_closed", True)),
        )
