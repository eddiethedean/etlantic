"""SparkForge / SQL builder project inventory scanner (Medallantic M7).

Analysis is static and secret-free: JSON IR parsing and text pattern matching
only. Never imports untrusted project code, never resolves secrets, never reads
production tables, and never mutates targets.
"""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

from etlantic.diagnostics import Diagnostic, Severity
from medallantic.diagnostics import (
    MDL200_INVENTORY,
    MDL210_MANUAL,
    MDL220_UNSUPPORTED,
    mdl_diagnostic,
)
from medallantic.ir import SparkForgePipelineSpec

BuilderKind = Literal[
    "pipeline_builder",
    "sql_pipeline_builder",
    "sparkforge_ir_json",
    "unknown",
]
Convertibility = Literal["auto", "manual", "unsupported"]


def _diagnostic_to_dict(diagnostic: Diagnostic) -> dict[str, Any]:
    return {
        "code": diagnostic.code,
        "severity": diagnostic.severity.value
        if hasattr(diagnostic.severity, "value")
        else str(diagnostic.severity),
        "message": diagnostic.message,
        "path": list(diagnostic.path),
        "phase": diagnostic.phase,
    }


_PY_BUILDER_PATTERNS = (
    re.compile(r"\bpipeline_builder\b"),
    re.compile(r"\bsql_pipeline_builder\b"),
    re.compile(r"\bSparkForge\b"),
    re.compile(r"from\s+sparkforge\b"),
    re.compile(r"import\s+sparkforge\b"),
)
_SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
}


@dataclass(frozen=True, slots=True)
class InventoryArtifact:
    """One discovered migration candidate (secret-free)."""

    path: str
    builder_kind: BuilderKind
    step_count: int
    convertibility: Convertibility
    diagnostic_codes: tuple[str, ...] = ()
    source_fingerprint: str | None = None
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "builder_kind": self.builder_kind,
            "step_count": self.step_count,
            "convertibility": self.convertibility,
            "diagnostic_codes": list(self.diagnostic_codes),
            "source_fingerprint": self.source_fingerprint,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class MigrationInventoryReport:
    """Secret-free project inventory for SparkForge migration."""

    root: str
    artifacts: tuple[InventoryArtifact, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "artifacts": [a.to_dict() for a in self.artifacts],
            "diagnostics": [_diagnostic_to_dict(d) for d in self.diagnostics],
            "counts": {
                "total": len(self.artifacts),
                "auto": sum(1 for a in self.artifacts if a.convertibility == "auto"),
                "manual": sum(
                    1 for a in self.artifacts if a.convertibility == "manual"
                ),
                "unsupported": sum(
                    1 for a in self.artifacts if a.convertibility == "unsupported"
                ),
            },
        }


def _fingerprint_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _looks_like_ir(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    return "steps" in payload and isinstance(payload.get("steps"), list)


def _classify_json_ir(
    payload: dict[str, Any],
    *,
    diagnostics: list[Diagnostic],
    path: str,
) -> tuple[Convertibility, tuple[str, ...], int, BuilderKind]:
    codes: list[str] = []
    try:
        spec, parse_diags = SparkForgePipelineSpec.parse(payload)
    except Exception as exc:
        codes.append(MDL220_UNSUPPORTED)
        diagnostics.append(
            mdl_diagnostic(
                MDL220_UNSUPPORTED,
                f"Unable to parse SparkForge IR at {path}: {exc}",
                severity=Severity.WARNING,
                path=(path,),
                phase="migration_inventory",
            )
        )
        return "unsupported", tuple(codes), 0, "sparkforge_ir_json"

    for diag in parse_diags:
        diagnostics.append(diag)
        codes.append(diag.code)

    step_count = len(spec.steps)
    # Heuristic: symbolic transform_ref without module:attr → manual.
    manual_reasons: list[str] = []
    for step in spec.steps:
        transform_ref = getattr(step, "transform_ref", None) or (
            dict(getattr(step, "metadata", {}) or {}).get("transform_ref")
        )
        if (
            transform_ref
            and ":" not in str(transform_ref)
            and "." not in str(transform_ref)
        ):
            manual_reasons.append(f"symbolic transform_ref {transform_ref!r}")
        kind = str(getattr(step, "kind", "") or "")
        if "delta" in kind.lower() or "maintenance" in kind.lower():
            manual_reasons.append(f"plugin-dependent kind {kind!r}")

    builder_kind: BuilderKind = "sparkforge_ir_json"
    engine = str(getattr(spec, "engine", "") or "").lower()
    if engine in {"sql", "sqlalchemy", "moltres"}:
        builder_kind = "sql_pipeline_builder"
    elif engine in {"spark", "pyspark", "local", "sparkless"}:
        builder_kind = "pipeline_builder"

    error_codes = {d.code for d in parse_diags if d.severity is Severity.ERROR}
    if error_codes:
        codes.append(MDL220_UNSUPPORTED)
        return "unsupported", tuple(dict.fromkeys(codes)), step_count, builder_kind
    if manual_reasons:
        codes.append(MDL210_MANUAL)
        diagnostics.append(
            mdl_diagnostic(
                MDL210_MANUAL,
                f"Manual conversion points at {path}: {'; '.join(manual_reasons)}",
                severity=Severity.WARNING,
                path=(path,),
                phase="migration_inventory",
            )
        )
        return "manual", tuple(dict.fromkeys(codes)), step_count, builder_kind
    codes.append(MDL200_INVENTORY)
    return "auto", tuple(dict.fromkeys(codes)), step_count, builder_kind


def _scan_json_file(
    path: Path,
    *,
    root: Path,
    diagnostics: list[Diagnostic],
) -> InventoryArtifact | None:
    try:
        text = path.read_text(encoding="utf-8")
        payload = json.loads(text)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not _looks_like_ir(payload):
        return None
    convertibility, codes, step_count, builder_kind = _classify_json_ir(
        payload, diagnostics=diagnostics, path=_rel(path, root)
    )
    return InventoryArtifact(
        path=_rel(path, root),
        builder_kind=builder_kind,
        step_count=step_count,
        convertibility=convertibility,
        diagnostic_codes=codes,
        source_fingerprint=_fingerprint_text(text),
        notes=("json_ir",),
    )


def _python_builder_kind(text: str) -> BuilderKind | None:
    if "sql_pipeline_builder" in text:
        return "sql_pipeline_builder"
    if "pipeline_builder" in text or "sparkforge" in text.lower():
        return "pipeline_builder"
    return None


def _count_steps_in_python(text: str) -> int:
    """Best-effort static count of step-like dicts / method calls (no exec)."""
    count = 0
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return len(re.findall(r"\b(?:bronze|silver|gold)_", text))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = ""
            if isinstance(func, ast.Attribute):
                name = func.attr
            elif isinstance(func, ast.Name):
                name = func.id
            if name.lower() in {
                "bronze",
                "silver",
                "gold",
                "add_bronze",
                "add_silver",
                "add_gold",
                "step",
            }:
                count += 1
        if isinstance(node, ast.Dict):
            keys = []
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    keys.append(key.value)
            if "kind" in keys and ("name" in keys or "layer" in keys):
                count += 1
    return count


def _scan_python_file(
    path: Path,
    *,
    root: Path,
    diagnostics: list[Diagnostic],
) -> InventoryArtifact | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    if not any(p.search(text) for p in _PY_BUILDER_PATTERNS):
        return None
    kind = _python_builder_kind(text) or "unknown"
    step_count = _count_steps_in_python(text)
    # Python sources always require manual review (no untrusted import).
    codes = (MDL210_MANUAL,)
    diagnostics.append(
        mdl_diagnostic(
            MDL210_MANUAL,
            f"Python builder module {_rel(path, root)} requires manual "
            "conversion (static inventory only; project code is not imported).",
            severity=Severity.WARNING,
            path=(_rel(path, root),),
            phase="migration_inventory",
        )
    )
    return InventoryArtifact(
        path=_rel(path, root),
        builder_kind=kind,
        step_count=step_count,
        convertibility="manual",
        diagnostic_codes=codes,
        source_fingerprint=_fingerprint_text(text),
        notes=("python_static", "no_untrusted_import"),
    )


def _iter_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.suffix.lower() in {".json", ".py"}:
            yield path


def scan_project(path: str | Path) -> MigrationInventoryReport:
    """Scan a project tree for SparkForge / SQL builder migration candidates.

    Args:
        path: Project root or a single JSON/Python file.

    Returns:
        Secret-free ``MigrationInventoryReport``.
    """
    root = Path(path)
    if not root.exists():
        diag = mdl_diagnostic(
            MDL220_UNSUPPORTED,
            f"Inventory path does not exist: {root}",
            severity=Severity.ERROR,
            path=(str(root),),
            phase="migration_inventory",
        )
        return MigrationInventoryReport(root=str(root), diagnostics=(diag,))

    diagnostics: list[Diagnostic] = []
    artifacts: list[InventoryArtifact] = []
    for file_path in sorted(_iter_files(root)):
        if file_path.suffix.lower() == ".json":
            artifact = _scan_json_file(
                file_path,
                root=root if root.is_dir() else root.parent,
                diagnostics=diagnostics,
            )
        else:
            artifact = _scan_python_file(
                file_path,
                root=root if root.is_dir() else root.parent,
                diagnostics=diagnostics,
            )
        if artifact is not None:
            artifacts.append(artifact)

    diagnostics.insert(
        0,
        mdl_diagnostic(
            MDL200_INVENTORY,
            f"Scanned {root}; found {len(artifacts)} migration candidate(s).",
            severity=Severity.INFO,
            path=(str(root),),
            phase="migration_inventory",
        ),
    )
    return MigrationInventoryReport(
        root=str(root.resolve()),
        artifacts=tuple(artifacts),
        diagnostics=tuple(diagnostics),
    )


__all__ = [
    "BuilderKind",
    "Convertibility",
    "InventoryArtifact",
    "MigrationInventoryReport",
    "scan_project",
]
