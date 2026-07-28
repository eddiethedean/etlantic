"""Static plugin manifests inspectable without importing entry points (0.20)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from importlib.metadata import Distribution, PackageNotFoundError, distribution
from pathlib import Path
from typing import Any

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

from etlantic.diagnostics import Diagnostic, Severity

PLUGIN_MANIFEST_SCHEMA = "etlantic.plugin_manifest/1"
MANIFEST_FILENAME = "etlantic-plugin-manifest.json"


@dataclass(frozen=True, slots=True)
class PluginManifestEntry:
    """One entry-point declaration inside a static plugin manifest."""

    group: str
    name: str
    target: str
    protocol: str | None = None
    capabilities: tuple[str, ...] = ()
    engine: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "group": self.group,
            "name": self.name,
            "target": self.target,
            "protocol": self.protocol,
            "capabilities": list(self.capabilities),
            "engine": self.engine,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PluginManifestEntry:
        caps = data.get("capabilities") or ()
        return cls(
            group=str(data["group"]),
            name=str(data["name"]),
            target=str(data["target"]),
            protocol=(str(data["protocol"]) if data.get("protocol") else None),
            capabilities=tuple(str(c) for c in caps),
            engine=(str(data["engine"]) if data.get("engine") else None),
        )


@dataclass(frozen=True, slots=True)
class PluginManifest:
    """Static distribution metadata for an ETLantic plugin package."""

    schema: str
    package: str
    version: str
    protocol_range: str
    entries: tuple[PluginManifestEntry, ...] = ()
    capabilities: tuple[str, ...] = ()
    privileges: tuple[str, ...] = ()
    provenance: dict[str, Any] = field(default_factory=dict)
    digest: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "package": self.package,
            "version": self.version,
            "protocol_range": self.protocol_range,
            "entries": [e.to_dict() for e in self.entries],
            "capabilities": list(self.capabilities),
            "privileges": list(self.privileges),
            "provenance": dict(self.provenance),
            "digest": self.digest,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PluginManifest:
        schema = str(data.get("schema") or "")
        if schema != PLUGIN_MANIFEST_SCHEMA:
            raise ValueError(
                f"Unsupported plugin manifest schema {schema!r}; "
                f"expected {PLUGIN_MANIFEST_SCHEMA!r}"
            )
        entries_raw = data.get("entries") or []
        return cls(
            schema=schema,
            package=str(data["package"]),
            version=str(data["version"]),
            protocol_range=str(data.get("protocol_range") or "*"),
            entries=tuple(
                PluginManifestEntry.from_dict(dict(item))
                for item in entries_raw
                if isinstance(item, dict)
            ),
            capabilities=tuple(str(c) for c in (data.get("capabilities") or ())),
            privileges=tuple(str(p) for p in (data.get("privileges") or ())),
            provenance=dict(data.get("provenance") or {}),
            digest=(str(data["digest"]) if data.get("digest") else None),
        )

    def entry_for(self, *, group: str, name: str) -> PluginManifestEntry | None:
        for entry in self.entries:
            if entry.group == group and entry.name == name:
                return entry
        return None

    def protocol_compatible(self, required: str | None = None) -> bool:
        """Return True when ``protocol_range`` admits ``required`` (if given)."""
        if required is None:
            return True
        try:
            # Treat protocol ids like "etlantic.dataframe/1" as opaque tokens
            # matched by SpecifierSet when protocol_range looks like a version
            # pin; otherwise require exact equality or "*".
            rng = self.protocol_range.strip()
            if rng in {"*", ""}:
                return True
            if "/" in required and required == rng:
                return True
            # Allow comma-separated protocol ids.
            if "," in rng:
                return required in {p.strip() for p in rng.split(",")}
            # Version-like ranges applied to trailing numeric segment.
            if "/" in required:
                ver = required.rsplit("/", 1)[-1]
                try:
                    return Version(ver) in SpecifierSet(rng)
                except (InvalidVersion, InvalidSpecifier):
                    return required == rng
            return Version(required) in SpecifierSet(rng)
        except (InvalidVersion, InvalidSpecifier):
            return required == self.protocol_range


def compute_manifest_digest(payload: dict[str, Any]) -> str:
    """SHA-256 digest over canonical JSON (excluding digest field)."""
    body = {k: v for k, v in payload.items() if k != "digest"}
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def parse_plugin_manifest(
    text: str,
    *,
    verify_digest: bool = True,
) -> tuple[PluginManifest | None, list[Diagnostic]]:
    """Parse and optionally verify a manifest document."""
    diagnostics: list[Diagnostic] = []
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        diagnostics.append(
            Diagnostic(
                code="PMPLUG410",
                severity=Severity.ERROR,
                message=f"Invalid plugin manifest JSON: {exc}",
                phase="plugin_discover",
            )
        )
        return None, diagnostics
    if not isinstance(data, dict):
        diagnostics.append(
            Diagnostic(
                code="PMPLUG410",
                severity=Severity.ERROR,
                message="Plugin manifest must be a JSON object.",
                phase="plugin_discover",
            )
        )
        return None, diagnostics
    try:
        manifest = PluginManifest.from_dict(data)
    except (KeyError, TypeError, ValueError) as exc:
        diagnostics.append(
            Diagnostic(
                code="PMPLUG410",
                severity=Severity.ERROR,
                message=f"Invalid plugin manifest: {exc}",
                phase="plugin_discover",
            )
        )
        return None, diagnostics
    if verify_digest:
        if not manifest.digest:
            diagnostics.append(
                Diagnostic(
                    code="PMPLUG411",
                    severity=Severity.ERROR,
                    message=(
                        f"Plugin manifest for {manifest.package!r} is missing a "
                        "digest; verify_digest=True requires a sha256 digest."
                    ),
                    path=("plugin", manifest.package),
                    phase="plugin_evaluate",
                )
            )
            return None, diagnostics
        expected = compute_manifest_digest(data)
        if manifest.digest != expected:
            diagnostics.append(
                Diagnostic(
                    code="PMPLUG411",
                    severity=Severity.ERROR,
                    message=(
                        f"Plugin manifest digest mismatch for {manifest.package!r}: "
                        f"declared={manifest.digest!r} computed={expected!r}."
                    ),
                    path=("plugin", manifest.package),
                    phase="plugin_evaluate",
                )
            )
            return None, diagnostics
    return manifest, diagnostics


def _candidate_manifest_paths(dist: Distribution) -> list[str]:
    name = dist.metadata["Name"] or ""
    pkg = name.replace("-", "_")
    return [
        MANIFEST_FILENAME,
        f"{pkg}/{MANIFEST_FILENAME}",
        f"etlantic/{MANIFEST_FILENAME}",
    ]


def read_distribution_manifest_text(dist: Distribution) -> str | None:
    """Read static manifest text from distribution metadata / package files."""
    for candidate in _candidate_manifest_paths(dist):
        try:
            text = dist.read_text(candidate)
        except Exception:
            text = None
        if text:
            return text
        try:
            located = dist.locate_file(candidate)
        except Exception:
            located = None
        if located is not None:
            path = Path(located)
            if path.is_file():
                return path.read_text(encoding="utf-8")
    if dist.files:
        for file_path in dist.files:
            if Path(str(file_path)).name == MANIFEST_FILENAME:
                try:
                    return file_path.read_text(encoding="utf-8")
                except Exception:
                    continue
    return None


def load_manifest_for_distribution(
    dist_name: str,
    *,
    verify_digest: bool = True,
) -> tuple[PluginManifest | None, list[Diagnostic]]:
    """Load a static manifest for an installed distribution by name."""
    try:
        dist = distribution(dist_name)
    except PackageNotFoundError:
        return None, [
            Diagnostic(
                code="PMPLUG412",
                severity=Severity.ERROR,
                message=f"Distribution {dist_name!r} is not installed.",
                path=("plugin", dist_name),
                phase="plugin_discover",
            )
        ]
    return load_manifest_from_distribution(dist, verify_digest=verify_digest)


def load_manifest_from_distribution(
    dist: Distribution,
    *,
    verify_digest: bool = True,
) -> tuple[PluginManifest | None, list[Diagnostic]]:
    """Load and parse a static manifest from a Distribution object."""
    text = read_distribution_manifest_text(dist)
    if text is None:
        return None, [
            Diagnostic(
                code="PMPLUG413",
                severity=Severity.ERROR,
                message=(
                    f"Distribution {dist.metadata['Name']!r} has no "
                    f"{MANIFEST_FILENAME}."
                ),
                path=("plugin", dist.metadata["Name"]),
                phase="plugin_discover",
            )
        ]
    manifest, diagnostics = parse_plugin_manifest(text, verify_digest=verify_digest)
    if manifest is None:
        return None, diagnostics
    # Package identity must match the installed distribution.
    dist_name = str(dist.metadata["Name"] or "")
    dist_version = str(dist.version)
    if canonicalize_name(manifest.package) != canonicalize_name(dist_name):
        diagnostics.append(
            Diagnostic(
                code="PMPLUG414",
                severity=Severity.ERROR,
                message=(
                    f"Manifest package {manifest.package!r} does not match "
                    f"distribution {dist_name!r}."
                ),
                path=("plugin", dist_name),
                phase="plugin_evaluate",
            )
        )
        return None, diagnostics
    if manifest.version != dist_version:
        diagnostics.append(
            Diagnostic(
                code="PMPLUG415",
                severity=Severity.ERROR,
                message=(
                    f"Manifest version {manifest.version!r} does not match "
                    f"distribution version {dist_version!r}."
                ),
                path=("plugin", dist_name),
                phase="plugin_evaluate",
            )
        )
        # Still return the manifest so callers can decide fail-closed vs warn;
        # production authorize/load paths reject via evaluate diagnostics.
        return manifest, diagnostics
    return manifest, diagnostics
