"""Trusted-workspace policy for opt-in import-based analysis (0.44)."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

TargetKind = Literal["json", "py_path", "module", "unknown"]


@dataclass(frozen=True, slots=True)
class TrustedWorkspacePolicy:
    """Explicit opt-in for importing user modules during analysis.

    Default analysis must not import project code. Construct this policy only
    when the host has obtained an explicit trusted-workspace decision.
    """

    enabled: bool = False
    allow_roots: tuple[str, ...] = ()
    allow_imports: bool = False
    allow_secret_resolution: bool = False
    allow_live_schema_query: bool = False
    timeout_seconds: float = 30.0
    max_memory_bytes: int | None = 256 * 1024 * 1024
    audit_label: str | None = None

    def __post_init__(self) -> None:
        if self.enabled and not self.allow_roots:
            raise ValueError(
                "TrustedWorkspacePolicy.enabled requires at least one allow_root"
            )
        if self.allow_secret_resolution and not self.enabled:
            raise ValueError("Secret resolution requires trusted mode")
        if self.allow_live_schema_query and not self.enabled:
            raise ValueError("Live schema queries require trusted mode")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    def permits_path(self, path: str | Path) -> bool:
        if not self.enabled:
            return False
        resolved = Path(path).resolve()
        for root in self.allow_roots:
            root_path = Path(root).resolve()
            try:
                resolved.relative_to(root_path)
                return True
            except ValueError:
                continue
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "allow_roots": list(self.allow_roots),
            "allow_imports": self.allow_imports,
            "allow_secret_resolution": self.allow_secret_resolution,
            "allow_live_schema_query": self.allow_live_schema_query,
            "timeout_seconds": self.timeout_seconds,
            "max_memory_bytes": self.max_memory_bytes,
            "audit_label": self.audit_label,
        }

    @classmethod
    def disabled(cls) -> TrustedWorkspacePolicy:
        return cls(enabled=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrustedWorkspacePolicy:
        return cls(
            enabled=bool(data.get("enabled", False)),
            allow_roots=tuple(str(r) for r in data.get("allow_roots", ())),
            allow_imports=bool(data.get("allow_imports", False)),
            allow_secret_resolution=bool(data.get("allow_secret_resolution", False)),
            allow_live_schema_query=bool(data.get("allow_live_schema_query", False)),
            timeout_seconds=float(data.get("timeout_seconds", 30.0)),
            max_memory_bytes=data.get("max_memory_bytes", 256 * 1024 * 1024),
            audit_label=data.get("audit_label"),
        )


@dataclass(frozen=True, slots=True)
class TrustAuditRecord:
    """Auditable record of a trusted-workspace operation."""

    operation: str
    target: str
    allowed: bool
    reason: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    policy: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "target": self.target,
            "allowed": self.allowed,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "policy": dict(self.policy),
        }


def split_target(target: str) -> tuple[str, str | None]:
    """Return ``(module_or_path, class_name_or_None)``.

    Windows drive letters (``C:\\...`` / ``C:/...``) are not treated as
    ``module:Class`` separators. Only the final ``:ClassName`` suffix splits.
    """
    if ":" not in target:
        return target, None
    left, right = target.rsplit(":", 1)
    # Bare Windows absolute path: ``C:\path`` or ``C:/path``.
    if len(left) == 1 and left.isalpha() and right[:1] in {"\\", "/"}:
        return target, None
    if not right:
        return target, None
    return left, right


def classify_target(target: str) -> TargetKind:
    """Classify an IDE/CLI pipeline target form."""
    module_part, _ = split_target(target)
    path = Path(module_part)
    if path.suffix.lower() == ".json":
        return "json"
    if path.suffix == ".py" or "/" in module_part or "\\" in module_part:
        return "py_path"
    if module_part and all(part.isidentifier() for part in module_part.split(".")):
        return "module"
    return "unknown"


def resolve_module_origin(module_name: str) -> Path | None:
    """Locate a module's origin path without importing it.

    Returns ``None`` for unresolved, builtin, or namespace-only modules without
    a filesystem location.
    """
    try:
        spec = importlib.util.find_spec(module_name)
    except (ImportError, ModuleNotFoundError, ValueError):
        return None
    if spec is None:
        return None
    origin = getattr(spec, "origin", None)
    if origin and origin not in {"built-in", "frozen"}:
        return Path(origin)
    locations = getattr(spec, "submodule_search_locations", None)
    if locations:
        return Path(next(iter(locations)))
    return None


def target_filesystem_path(target: str) -> Path | None:
    """Filesystem path that must fall under ``allow_roots`` for trusted ops."""
    kind = classify_target(target)
    module_part, _ = split_target(target)
    if kind == "json":
        return Path(module_part)
    if kind == "py_path":
        return Path(module_part)
    if kind == "module":
        return resolve_module_origin(module_part)
    return None


def deny_untrusted(
    policy: TrustedWorkspacePolicy,
    *,
    operation: str,
    target: str,
    require_imports: bool = False,
) -> TrustAuditRecord:
    """Return an audit record allowing or denying an operation under policy."""
    if not policy.enabled:
        return TrustAuditRecord(
            operation=operation,
            target=target,
            allowed=False,
            reason="trusted workspace not enabled",
            policy=policy.to_dict(),
        )

    kind = classify_target(target)
    if (kind in {"py_path", "module"} or require_imports) and not policy.allow_imports:
        return TrustAuditRecord(
            operation=operation,
            target=target,
            allowed=False,
            reason="imports not permitted by policy",
            policy=policy.to_dict(),
        )

    fs_path = target_filesystem_path(target)
    if kind == "module" and fs_path is None:
        return TrustAuditRecord(
            operation=operation,
            target=target,
            allowed=False,
            reason="module origin unresolved or outside workspace",
            policy=policy.to_dict(),
        )
    if kind == "unknown":
        return TrustAuditRecord(
            operation=operation,
            target=target,
            allowed=False,
            reason="unsupported target form",
            policy=policy.to_dict(),
        )
    if fs_path is not None and not policy.permits_path(fs_path):
        return TrustAuditRecord(
            operation=operation,
            target=target,
            allowed=False,
            reason="target outside allow_roots",
            policy=policy.to_dict(),
        )
    return TrustAuditRecord(
        operation=operation,
        target=target,
        allowed=True,
        reason="permitted by trusted policy",
        policy=policy.to_dict(),
    )


def deny_analysis_secret_flags(
    policy: TrustedWorkspacePolicy,
    *,
    operation: str,
    target: str,
) -> TrustAuditRecord | None:
    """Fail closed when analysis hosts enable secret or live-schema flags."""
    if policy.allow_secret_resolution or policy.allow_live_schema_query:
        return TrustAuditRecord(
            operation=operation,
            target=target,
            allowed=False,
            reason=(
                "analysis hosts fail closed on secret resolution and live schema queries"
            ),
            policy=policy.to_dict(),
        )
    return None
