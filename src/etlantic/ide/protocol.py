"""Editor-neutral protocol payloads for developer intelligence (0.44)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

PROTOCOL_VERSION = "etlantic.ide/1"


def _redact_dict(value: dict[str, Any]) -> dict[str, Any]:
    from etlantic.runtime.logging import redact_value

    return dict(redact_value(dict(value)))


@dataclass(frozen=True, slots=True)
class LocationLink:
    """A navigable file location (editor-neutral)."""

    uri: str
    line: int | None = None
    column: int | None = None
    end_line: int | None = None
    end_column: int | None = None
    symbol: str | None = None
    kind: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"uri": self.uri}
        if self.line is not None:
            payload["line"] = self.line
        if self.column is not None:
            payload["column"] = self.column
        if self.end_line is not None:
            payload["end_line"] = self.end_line
        if self.end_column is not None:
            payload["end_column"] = self.end_column
        if self.symbol is not None:
            payload["symbol"] = self.symbol
        if self.kind is not None:
            payload["kind"] = self.kind
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LocationLink:
        return cls(
            uri=str(data["uri"]),
            line=data.get("line"),
            column=data.get("column"),
            end_line=data.get("end_line"),
            end_column=data.get("end_column"),
            symbol=data.get("symbol"),
            kind=data.get("kind"),
        )


@dataclass(frozen=True, slots=True)
class SymbolPayload:
    """Workspace or document symbol."""

    name: str
    kind: str
    location: LocationLink
    container: str | None = None
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "kind": self.kind,
            "location": self.location.to_dict(),
        }
        if self.container is not None:
            payload["container"] = self.container
        if self.detail is not None:
            payload["detail"] = self.detail
        return payload


@dataclass(frozen=True, slots=True)
class DiagnosticPayload:
    """Editor-facing diagnostic with optional physical location."""

    code: str
    severity: str
    message: str
    path: tuple[str, ...] = ()
    location: LocationLink | None = None
    related: tuple[LocationLink, ...] = ()
    help: str | None = None
    phase: str | None = None
    actions: tuple[dict[str, Any], ...] = ()
    impact: str | None = None

    def to_dict(self) -> dict[str, Any]:
        from etlantic.runtime.logging import redact_message

        payload: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity,
            "message": redact_message(self.message),
            "path": list(self.path),
        }
        if self.location is not None:
            payload["location"] = self.location.to_dict()
        if self.related:
            payload["related"] = [item.to_dict() for item in self.related]
        if self.help:
            payload["help"] = redact_message(self.help)
        if self.phase:
            payload["phase"] = self.phase
        if self.actions:
            payload["actions"] = [_redact_dict(dict(a)) for a in self.actions]
        if self.impact:
            payload["impact"] = redact_message(self.impact)
        return payload

    @classmethod
    def from_diagnostic(cls, diagnostic: Any) -> DiagnosticPayload:
        """Build from :class:`etlantic.diagnostics.Diagnostic`."""
        location: LocationLink | None = None
        source = getattr(diagnostic, "source", None)
        if source is not None and source.path:
            location = LocationLink(
                uri=str(source.path),
                line=source.line,
                column=source.column,
                symbol=source.symbol,
                kind="diagnostic",
            )
        actions = tuple(
            a.to_dict() if hasattr(a, "to_dict") else dict(a)
            for a in getattr(diagnostic, "actions", ())
        )
        return cls(
            code=str(diagnostic.code),
            severity=str(
                diagnostic.severity.value
                if hasattr(diagnostic.severity, "value")
                else diagnostic.severity
            ),
            message=str(diagnostic.message),
            path=tuple(diagnostic.path or ()),
            location=location,
            help=diagnostic.help,
            phase=diagnostic.phase,
            actions=actions,
            impact=(diagnostic.metadata or {}).get("impact")
            if getattr(diagnostic, "metadata", None)
            else None,
        )


@dataclass(frozen=True, slots=True)
class GraphPreview:
    """Stable pipeline graph preview for editors."""

    pipeline_id: str
    pipeline_name: str
    nodes: tuple[dict[str, Any], ...] = ()
    edges: tuple[dict[str, Any], ...] = ()
    layout_key: str | None = None
    mermaid: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "protocol": PROTOCOL_VERSION,
            "pipeline_id": self.pipeline_id,
            "pipeline_name": self.pipeline_name,
            "nodes": list(self.nodes),
            "edges": list(self.edges),
        }
        if self.layout_key is not None:
            payload["layout_key"] = self.layout_key
        if self.mermaid is not None:
            payload["mermaid"] = self.mermaid
        return payload


@dataclass(frozen=True, slots=True)
class LineagePreview:
    """Field or port lineage preview (metadata only)."""

    pipeline_id: str
    edges: tuple[dict[str, Any], ...] = ()
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol": PROTOCOL_VERSION,
            "pipeline_id": self.pipeline_id,
            "edges": list(self.edges),
            "truncated": self.truncated,
        }


@dataclass(frozen=True, slots=True)
class PlanPreview:
    """Resolved plan preview for editors."""

    plan_id: str
    fingerprint: str
    profile_name: str | None = None
    node_count: int = 0
    regions: tuple[dict[str, Any], ...] = ()
    implementations: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol": PROTOCOL_VERSION,
            "plan_id": self.plan_id,
            "fingerprint": self.fingerprint,
            "profile_name": self.profile_name,
            "node_count": self.node_count,
            "regions": list(self.regions),
            "implementations": list(self.implementations),
        }


@dataclass(frozen=True, slots=True)
class ExplainPreview:
    """Plan explanation payload."""

    plan_id: str
    fingerprint: str
    steps: tuple[dict[str, Any], ...] = ()
    summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "protocol": PROTOCOL_VERSION,
            "plan_id": self.plan_id,
            "fingerprint": self.fingerprint,
            "steps": list(self.steps),
        }
        if self.summary is not None:
            payload["summary"] = self.summary
        return payload


@dataclass(frozen=True, slots=True)
class ImpactPreview:
    """Downstream impact of a contract or port change."""

    origin: str
    affected: tuple[dict[str, Any], ...] = ()
    diagnostics: tuple[DiagnosticPayload, ...] = ()
    summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "protocol": PROTOCOL_VERSION,
            "origin": self.origin,
            "affected": list(self.affected),
            "diagnostics": [d.to_dict() for d in self.diagnostics],
        }
        if self.summary is not None:
            payload["summary"] = self.summary
        return payload


@dataclass(frozen=True, slots=True)
class SemanticDiff:
    """Reviewable semantic edit summary."""

    edits: tuple[dict[str, Any], ...] = ()
    unrelated_rewrite_count: int = 0
    requires_revalidation: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol": PROTOCOL_VERSION,
            "edits": list(self.edits),
            "unrelated_rewrite_count": self.unrelated_rewrite_count,
            "requires_revalidation": self.requires_revalidation,
        }


@dataclass(frozen=True, slots=True)
class IdeCommand:
    """Editor command mapped onto public SDK operations."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol": PROTOCOL_VERSION,
            "name": self.name,
            "arguments": _redact_dict(dict(self.arguments)),
        }


@dataclass(frozen=True, slots=True)
class IdeResult:
    """Result of an :class:`IdeCommand`."""

    name: str
    ok: bool
    payload: dict[str, Any] = field(default_factory=dict)
    diagnostics: tuple[DiagnosticPayload, ...] = ()
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "protocol": PROTOCOL_VERSION,
            "name": self.name,
            "ok": self.ok,
            "payload": _redact_dict(dict(self.payload)),
            "diagnostics": [d.to_dict() for d in self.diagnostics],
        }
        if self.error is not None:
            from etlantic.runtime.logging import redact_message

            result["error"] = redact_message(self.error)
        return result
