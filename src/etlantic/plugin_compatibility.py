"""Plugin compatibility report for independently installed packages (0.22).

``etlantic plugin compatibility`` evaluates a plugin's static
:class:`~etlantic.plugin_manifest.PluginManifest` against the installed core
without importing private modules. Checks cover protocol ranges, capability
vocabulary major, plan schema, Python requires, core pin, and allowlist
status.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, distribution, version
from typing import Any

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from etlantic.capabilities import (
    CAPABILITY_VOCABULARY_VERSION,
    vocabulary_major_compatible,
)
from etlantic.dataframe.protocol import DATAFRAME_PROTOCOL_VERSION
from etlantic.orchestration.protocol import ORCHESTRATION_PROTOCOL_VERSION
from etlantic.plan.model import PLAN_SCHEMA
from etlantic.plugin_manifest import (
    PluginManifest,
    load_manifest_for_distribution,
    parse_plugin_manifest,
)
from etlantic.runtime.scheduler import SCHEDULER_PROTOCOL
from etlantic.spark.protocol import SPARK_PROTOCOL_VERSION
from etlantic.sql.protocol import SQL_PROTOCOL_VERSION
from etlantic.transform.compiler import COMPILER_PROTOCOL as TRANSFORM_COMPILER_PROTOCOL

# Diagnostic codes for the compatibility report (secret-free, actionable).
COMPAT_OK = "PMPLUG440"
COMPAT_MISSING_PACKAGE = "PMPLUG441"
COMPAT_MISSING_MANIFEST = "PMPLUG442"
COMPAT_INVALID_MANIFEST = "PMPLUG443"
COMPAT_PROTOCOL = "PMPLUG444"
COMPAT_VOCABULARY = "PMPLUG445"
COMPAT_PLAN_SCHEMA = "PMPLUG446"
COMPAT_PYTHON = "PMPLUG447"
COMPAT_CORE_PIN = "PMPLUG448"
COMPAT_ALLOWLIST = "PMPLUG449"
COMPAT_MISSING_FIELDS = "PMPLUG450"

_KNOWN_CORE_PROTOCOLS: dict[str, str] = {
    "etlantic.dataframe": DATAFRAME_PROTOCOL_VERSION,
    "etlantic.sql": SQL_PROTOCOL_VERSION,
    "etlantic.spark": SPARK_PROTOCOL_VERSION,
    "etlantic.orchestration": ORCHESTRATION_PROTOCOL_VERSION,
    "etlantic.transform-compiler": TRANSFORM_COMPILER_PROTOCOL,
    "etlantic.scheduler": SCHEDULER_PROTOCOL,
}


@dataclass(frozen=True, slots=True)
class CompatibilityFinding:
    """One pass/fail finding inside a compatibility report row."""

    code: str
    ok: bool
    message: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "ok": self.ok,
            "message": self.message,
            "detail": dict(self.detail),
        }


@dataclass(frozen=True, slots=True)
class CompatibilityRow:
    """Compatibility evaluation for one plugin package."""

    package: str
    plugin_version: str | None
    core_version: str
    protocol_range: str | None
    protocols_checked: tuple[str, ...]
    plan_schema: str
    capability_vocabulary: str
    python_requires: str | None
    core_requires: str | None
    allowlist_status: str
    ok: bool
    findings: tuple[CompatibilityFinding, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "package": self.package,
            "plugin_version": self.plugin_version,
            "core_version": self.core_version,
            "protocol_range": self.protocol_range,
            "protocols_checked": list(self.protocols_checked),
            "plan_schema": self.plan_schema,
            "capability_vocabulary": self.capability_vocabulary,
            "python_requires": self.python_requires,
            "core_requires": self.core_requires,
            "allowlist_status": self.allowlist_status,
            "ok": self.ok,
            "findings": [f.to_dict() for f in self.findings],
        }


@dataclass(frozen=True, slots=True)
class CompatibilityReport:
    """Aggregate compatibility report across one or more plugins."""

    core_version: str
    plan_schema: str
    capability_vocabulary: str
    rows: tuple[CompatibilityRow, ...]

    @property
    def ok(self) -> bool:
        return all(row.ok for row in self.rows)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "core_version": self.core_version,
            "plan_schema": self.plan_schema,
            "capability_vocabulary": self.capability_vocabulary,
            "plugins": [row.to_dict() for row in self.rows],
        }


def _core_version() -> str:
    try:
        return version("etlantic")
    except PackageNotFoundError:
        from etlantic import __version__

        return __version__


def _python_version_string() -> str:
    info = sys.version_info
    return f"{info.major}.{info.minor}.{info.micro}"


def _resolve_required_protocols(manifest: PluginManifest) -> tuple[str, ...]:
    """Collect protocol ids the core must satisfy for this manifest."""
    found: list[str] = []
    for entry in manifest.entries:
        if entry.protocol:
            found.append(entry.protocol)
    # Fall back to comma-separated protocol_range tokens that look like ids.
    if not found and manifest.protocol_range not in {"*", ""}:
        for token in manifest.protocol_range.split(","):
            token = token.strip()
            if "/" in token:
                found.append(token)
    # Deduplicate while preserving order.
    seen: set[str] = set()
    ordered: list[str] = []
    for item in found:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return tuple(ordered)


def _core_protocol_for(protocol_id: str) -> str | None:
    family = protocol_id.rsplit("/", 1)[0] if "/" in protocol_id else protocol_id
    return _KNOWN_CORE_PROTOCOLS.get(family)


def evaluate_manifest(
    manifest: PluginManifest,
    *,
    python_requires: str | None = None,
    core_requires: str | None = None,
    allowlist: Sequence[str] | None = None,
    advertised_vocabulary: str | None = None,
) -> CompatibilityRow:
    """Evaluate a parsed manifest against the installed core.

    ``allowlist`` is the profile's ``plugin_allowlist``. ``None`` means no
    profile context (reported as ``unknown``); an empty sequence means the
    profile has no allowlist (``not_required`` for non-production use).
    """
    findings: list[CompatibilityFinding] = []
    core_ver = _core_version()

    # Required fields.
    missing: list[str] = []
    if not manifest.package:
        missing.append("package")
    if not manifest.version:
        missing.append("version")
    if not manifest.protocol_range:
        missing.append("protocol_range")
    if missing:
        findings.append(
            CompatibilityFinding(
                code=COMPAT_MISSING_FIELDS,
                ok=False,
                message=f"Manifest is missing required fields: {', '.join(missing)}.",
                detail={"missing": missing},
            )
        )

    protocols = _resolve_required_protocols(manifest)
    for protocol_id in protocols:
        core_proto = _core_protocol_for(protocol_id)
        if core_proto is None:
            # Unknown family is not a hard fail — future protocols may land
            # before core ships them; report as informational pass with note.
            findings.append(
                CompatibilityFinding(
                    code=COMPAT_PROTOCOL,
                    ok=True,
                    message=(
                        f"Protocol {protocol_id!r} is not a known core family; "
                        "skipped exact version match."
                    ),
                    detail={"protocol": protocol_id, "known": False},
                )
            )
            continue
        compatible = manifest.protocol_compatible(core_proto)
        findings.append(
            CompatibilityFinding(
                code=COMPAT_PROTOCOL,
                ok=compatible,
                message=(
                    f"Protocol range {manifest.protocol_range!r} "
                    f"{'admits' if compatible else 'rejects'} core {core_proto!r}."
                ),
                detail={
                    "protocol": protocol_id,
                    "core_protocol": core_proto,
                    "protocol_range": manifest.protocol_range,
                },
            )
        )

    vocab = advertised_vocabulary or CAPABILITY_VOCABULARY_VERSION
    vocab_ok = vocabulary_major_compatible(vocab)
    findings.append(
        CompatibilityFinding(
            code=COMPAT_VOCABULARY,
            ok=vocab_ok,
            message=(
                f"Capability vocabulary {vocab!r} is "
                f"{'compatible' if vocab_ok else 'incompatible'} with core "
                f"{CAPABILITY_VOCABULARY_VERSION!r}."
            ),
            detail={
                "advertised": vocab,
                "core": CAPABILITY_VOCABULARY_VERSION,
            },
        )
    )

    # Plan schema is a core constant; report it so plugins can pin against it.
    findings.append(
        CompatibilityFinding(
            code=COMPAT_PLAN_SCHEMA,
            ok=True,
            message=f"Core plan schema is {PLAN_SCHEMA}.",
            detail={"plan_schema": PLAN_SCHEMA},
        )
    )

    if python_requires:
        try:
            py_ok = Version(_python_version_string()) in SpecifierSet(python_requires)
        except (InvalidVersion, InvalidSpecifier):
            py_ok = False
        findings.append(
            CompatibilityFinding(
                code=COMPAT_PYTHON,
                ok=py_ok,
                message=(
                    f"Installed Python {_python_version_string()} "
                    f"{'satisfies' if py_ok else 'does not satisfy'} "
                    f"Requires-Python {python_requires!r}."
                ),
                detail={
                    "python": _python_version_string(),
                    "requires": python_requires,
                },
            )
        )

    if core_requires:
        try:
            req = Requirement(core_requires)
            pin_ok = Version(core_ver) in req.specifier
        except (InvalidRequirement, InvalidVersion):
            pin_ok = False
            req = None  # type: ignore[assignment]
        findings.append(
            CompatibilityFinding(
                code=COMPAT_CORE_PIN,
                ok=pin_ok,
                message=(
                    f"Core {core_ver} "
                    f"{'satisfies' if pin_ok else 'does not satisfy'} "
                    f"plugin pin {core_requires!r}."
                ),
                detail={"core_version": core_ver, "requires": core_requires},
            )
        )

    if allowlist is None:
        allowlist_status = "unknown"
    elif not allowlist:
        allowlist_status = "not_required"
    elif manifest.package in allowlist:
        allowlist_status = "allowed"
    else:
        allowlist_status = "blocked"
        findings.append(
            CompatibilityFinding(
                code=COMPAT_ALLOWLIST,
                ok=False,
                message=(
                    f"Package {manifest.package!r} is not in the profile "
                    "plugin_allowlist."
                ),
                detail={"allowlist": list(allowlist)},
            )
        )

    # If every finding so far is ok and we have no hard failures, emit a
    # summary OK finding for greppable reports.
    hard_failures = [f for f in findings if not f.ok]
    ok = not hard_failures and not missing
    if ok:
        findings.append(
            CompatibilityFinding(
                code=COMPAT_OK,
                ok=True,
                message=f"Plugin {manifest.package!r} is compatible with core {core_ver}.",
            )
        )

    return CompatibilityRow(
        package=manifest.package or "<unknown>",
        plugin_version=manifest.version or None,
        core_version=core_ver,
        protocol_range=manifest.protocol_range or None,
        protocols_checked=protocols,
        plan_schema=PLAN_SCHEMA,
        capability_vocabulary=CAPABILITY_VOCABULARY_VERSION,
        python_requires=python_requires,
        core_requires=core_requires,
        allowlist_status=allowlist_status if allowlist is not None else "unknown",
        ok=ok,
        findings=tuple(findings),
    )


def evaluate_manifest_text(
    text: str,
    *,
    python_requires: str | None = None,
    core_requires: str | None = None,
    allowlist: Sequence[str] | None = None,
    verify_digest: bool = True,
) -> CompatibilityRow:
    """Evaluate a raw manifest JSON document (fixture-friendly)."""
    manifest, diagnostics = parse_plugin_manifest(text, verify_digest=verify_digest)
    if manifest is None:
        messages = "; ".join(d.message for d in diagnostics) or "invalid manifest"
        return CompatibilityRow(
            package="<invalid>",
            plugin_version=None,
            core_version=_core_version(),
            protocol_range=None,
            protocols_checked=(),
            plan_schema=PLAN_SCHEMA,
            capability_vocabulary=CAPABILITY_VOCABULARY_VERSION,
            python_requires=python_requires,
            core_requires=core_requires,
            allowlist_status="unknown",
            ok=False,
            findings=(
                CompatibilityFinding(
                    code=COMPAT_INVALID_MANIFEST,
                    ok=False,
                    message=messages,
                ),
            ),
        )
    return evaluate_manifest(
        manifest,
        python_requires=python_requires,
        core_requires=core_requires,
        allowlist=allowlist,
    )


def _etlantic_requirement_from_dist(dist_name: str) -> tuple[str | None, str | None]:
    """Return (Requires-Python, Requires-Dist for etlantic) for an installed dist."""
    try:
        dist = distribution(dist_name)
    except PackageNotFoundError:
        return None, None
    python_requires = dist.metadata.get("Requires-Python")
    core_requires: str | None = None
    for raw in dist.requires or ():
        try:
            req = Requirement(raw)
        except InvalidRequirement:
            continue
        if req.name.lower() in {"etlantic"}:
            core_requires = str(req)
            break
    return python_requires, core_requires


def evaluate_installed_plugin(
    package: str,
    *,
    allowlist: Sequence[str] | None = None,
    verify_digest: bool = True,
) -> CompatibilityRow:
    """Load an installed package's manifest and evaluate compatibility."""
    python_requires, core_requires = _etlantic_requirement_from_dist(package)
    manifest, diagnostics = load_manifest_for_distribution(
        package, verify_digest=verify_digest
    )
    if manifest is None:
        codes = {d.code for d in diagnostics}
        if "PMPLUG412" in codes:
            code = COMPAT_MISSING_PACKAGE
            message = f"Distribution {package!r} is not installed."
        elif "PMPLUG413" in codes:
            code = COMPAT_MISSING_MANIFEST
            message = f"Distribution {package!r} has no etlantic-plugin-manifest.json."
        else:
            code = COMPAT_INVALID_MANIFEST
            message = "; ".join(d.message for d in diagnostics) or (
                f"Could not load manifest for {package!r}."
            )
        return CompatibilityRow(
            package=package,
            plugin_version=None,
            core_version=_core_version(),
            protocol_range=None,
            protocols_checked=(),
            plan_schema=PLAN_SCHEMA,
            capability_vocabulary=CAPABILITY_VOCABULARY_VERSION,
            python_requires=python_requires,
            core_requires=core_requires,
            allowlist_status="unknown"
            if allowlist is None
            else (
                "allowed"
                if package in allowlist
                else ("not_required" if not allowlist else "blocked")
            ),
            ok=False,
            findings=(CompatibilityFinding(code=code, ok=False, message=message),),
        )
    return evaluate_manifest(
        manifest,
        python_requires=python_requires,
        core_requires=core_requires,
        allowlist=allowlist,
    )


def build_compatibility_report(
    packages: Iterable[str],
    *,
    allowlist: Sequence[str] | None = None,
) -> CompatibilityReport:
    """Build a multi-plugin compatibility report for installed packages."""
    rows = tuple(
        evaluate_installed_plugin(name, allowlist=allowlist) for name in packages
    )
    return CompatibilityReport(
        core_version=_core_version(),
        plan_schema=PLAN_SCHEMA,
        capability_vocabulary=CAPABILITY_VOCABULARY_VERSION,
        rows=rows,
    )


def render_compatibility_human(report: CompatibilityReport) -> str:
    """Render a human-readable compatibility report."""
    lines = [
        f"ETLantic core {report.core_version}",
        f"Plan schema: {report.plan_schema}",
        f"Capability vocabulary: {report.capability_vocabulary}",
        "",
    ]
    for row in report.rows:
        status = "PASS" if row.ok else "FAIL"
        lines.append(f"[{status}] {row.package} {row.plugin_version or '?'}")
        lines.append(f"  protocol_range: {row.protocol_range or '(none)'}")
        lines.append(f"  python_requires: {row.python_requires or '(none)'}")
        lines.append(f"  core_requires: {row.core_requires or '(none)'}")
        lines.append(f"  allowlist: {row.allowlist_status}")
        for finding in row.findings:
            mark = "ok" if finding.ok else "FAIL"
            lines.append(f"  - [{mark}] {finding.code}: {finding.message}")
        lines.append("")
    lines.append("Overall: " + ("PASS" if report.ok else "FAIL"))
    return "\n".join(lines)
