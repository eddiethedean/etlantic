"""Authoring catalog for visual builders and service discovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from etlantic._version import __version__
from etlantic.authoring.definition import PIPELINE_SCHEMA, PipelineDefinition


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """UI-safe metadata for a discoverable authoring component."""

    identity: str
    kind: str
    display_name: str
    description: str = ""
    types: tuple[str, ...] = ()
    required: bool = False
    default: Any = None
    constraints: dict[str, Any] = field(default_factory=dict)
    choices: tuple[Any, ...] = ()
    sensitive: bool = False
    deprecated: bool = False
    capabilities: tuple[str, ...] = ()
    endpoints: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity,
            "kind": self.kind,
            "display_name": self.display_name,
            "description": self.description,
            "types": list(self.types),
            "required": self.required,
            "default": self.default,
            "constraints": dict(self.constraints),
            "choices": list(self.choices),
            "sensitive": self.sensitive,
            "deprecated": self.deprecated,
            "capabilities": list(self.capabilities),
            "endpoints": list(self.endpoints),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class AuthoringCatalog:
    """Machine-readable authoring catalog."""

    schema: str = "etlantic.authoring-catalog/1"
    version: str = __version__
    document_versions: tuple[str, ...] = (PIPELINE_SCHEMA,)
    operations: tuple[str, ...] = (
        "add_node",
        "remove_node",
        "connect",
        "disconnect",
        "update",
        "clone",
        "move",
    )
    lifecycle_actions: tuple[str, ...] = (
        "validate",
        "plan",
        "compile",
        "generate",
        "visualize",
        "run",
        "cancel",
        "report",
    )
    entries: tuple[CatalogEntry, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "version": self.version,
            "document_versions": list(self.document_versions),
            "operations": list(self.operations),
            "lifecycle_actions": list(self.lifecycle_actions),
            "entries": [e.to_dict() for e in self.entries],
        }


def catalog_from_definition(defn: PipelineDefinition) -> AuthoringCatalog:
    """Build a catalog slice from contracts/transforms present in a definition."""
    entries: list[CatalogEntry] = []
    for contract in defn.contracts:
        entries.append(
            CatalogEntry(
                identity=contract.identity,
                kind="contract",
                display_name=contract.name,
                description="Data contract",
                types=tuple(f.type for f in contract.fields),
                endpoints=("port:input", "port:output"),
            )
        )
    for xf in defn.transformations:
        entries.append(
            CatalogEntry(
                identity=xf.identity,
                kind="transformation",
                display_name=xf.name,
                description="Transformation",
                endpoints=tuple(
                    f"port:{p.direction}:{p.name}" for p in xf.ports if p.direction != "parameter"
                ),
                capabilities=tuple(sorted({r.engine for r in xf.implementation_refs})),
            )
        )
    entries.extend(
        [
            CatalogEntry(
                identity="etlantic.extract",
                kind="extract",
                display_name="Extract",
                description="Logical extract boundary",
                endpoints=("port:output:result",),
            ),
            CatalogEntry(
                identity="etlantic.load",
                kind="load",
                display_name="Load",
                description="Logical load boundary",
                endpoints=("port:input:input",),
            ),
            CatalogEntry(
                identity="etlantic.step",
                kind="step",
                display_name="Step",
                description="Transformation step",
            ),
        ]
    )
    return AuthoringCatalog(entries=tuple(entries))


def discover_authoring_catalog(
    *,
    definition: PipelineDefinition | None = None,
) -> AuthoringCatalog:
    """Publish the environment authoring catalog (optionally scoped to a definition)."""
    if definition is not None:
        return catalog_from_definition(definition)
    return AuthoringCatalog(
        entries=(
            CatalogEntry(
                identity="etlantic.extract",
                kind="extract",
                display_name="Extract",
                description="Logical extract boundary",
                endpoints=("port:output:result",),
            ),
            CatalogEntry(
                identity="etlantic.load",
                kind="load",
                display_name="Load",
                description="Logical load boundary",
                endpoints=("port:input:input",),
            ),
            CatalogEntry(
                identity="etlantic.step",
                kind="step",
                display_name="Step",
                description="Transformation step",
            ),
            CatalogEntry(
                identity="etlantic.subpipeline",
                kind="subpipeline",
                display_name="Subpipeline",
                description="Nested pipeline",
            ),
        )
    )


def negotiate_capabilities() -> dict[str, Any]:
    """Return schema/capability negotiation payload for applications."""
    catalog = discover_authoring_catalog()
    return {
        "etlantic_version": __version__,
        "document_versions": list(catalog.document_versions),
        "operations": list(catalog.operations),
        "lifecycle_actions": list(catalog.lifecycle_actions),
        "catalog_schema": catalog.schema,
    }
