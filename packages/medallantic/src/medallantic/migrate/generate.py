"""Safe native Medallantic definition generation from SparkForge IR (M7).

Generators never resolve secrets, never import untrusted project code, and
never read production tables. Only auto-safe inventory artifacts / IR payloads
are converted; manual and unsupported paths emit stable ``MDL*`` diagnostics.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from etlantic.authoring import (
    FACADE_PROTOCOL_VERSION,
    PipelineDefinition,
    definition_from_pipeline,
    definition_provenance,
    inspect_definition,
)
from etlantic.diagnostics import Diagnostic, Severity
from medallantic.adapt import AdaptationResult, AdapterError, adapt_pipeline
from medallantic.diagnostics import (
    MDL210_MANUAL,
    MDL220_UNSUPPORTED,
    MDL230_GENERATED,
    mdl_diagnostic,
)
from medallantic.ir import SparkForgePipelineSpec
from medallantic.migrate.inventory import Convertibility, InventoryArtifact

GENERATOR_ID = "medallantic.migrate.generate"


@dataclass(frozen=True, slots=True)
class GenerationResult:
    """Result of safe native generation from SparkForge IR."""

    definition: PipelineDefinition | None
    convertibility: Convertibility
    diagnostics: tuple[Diagnostic, ...]
    source_fingerprint: str | None = None
    adaptation: AdaptationResult | None = None

    def to_dict(self) -> dict[str, Any]:
        inspection = (
            inspect_definition(self.definition).to_dict()
            if self.definition is not None
            else None
        )
        return {
            "convertibility": self.convertibility,
            "source_fingerprint": self.source_fingerprint,
            "definition_inspection": inspection,
            "diagnostics": [
                {
                    "code": d.code,
                    "severity": d.severity.value
                    if hasattr(d.severity, "value")
                    else str(d.severity),
                    "message": d.message,
                    "path": list(d.path),
                    "phase": d.phase,
                }
                for d in self.diagnostics
            ],
            "facade_protocol_version": FACADE_PROTOCOL_VERSION,
            "generator_id": GENERATOR_ID,
        }


def _fingerprint_payload(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(text.encode("utf-8")).hexdigest()


def generate_from_ir(
    payload: dict[str, Any],
    *,
    source_path: str | None = None,
    require_auto: bool = True,
) -> GenerationResult:
    """Generate a native ``PipelineDefinition`` from SparkForge IR JSON.

    Args:
        payload: Secret-free SparkForge pipeline IR mapping.
        source_path: Optional path label for diagnostics.
        require_auto: When True, refuse generation unless convertibility is auto.

    Returns:
        ``GenerationResult`` with stamped provenance on success.
    """
    diagnostics: list[Diagnostic] = []
    path_label = source_path or "<memory>"
    source_fp = _fingerprint_payload(payload)

    try:
        spec, parse_diags = SparkForgePipelineSpec.parse(payload)
    except Exception as exc:
        diagnostics.append(
            mdl_diagnostic(
                MDL220_UNSUPPORTED,
                f"IR parse failed for {path_label}: {exc}",
                severity=Severity.ERROR,
                path=(path_label,),
                phase="migration_generate",
            )
        )
        return GenerationResult(
            definition=None,
            convertibility="unsupported",
            diagnostics=tuple(diagnostics),
            source_fingerprint=source_fp,
        )

    diagnostics.extend(parse_diags)
    if any(d.severity is Severity.ERROR for d in parse_diags):
        diagnostics.append(
            mdl_diagnostic(
                MDL220_UNSUPPORTED,
                f"IR has structural errors; refusing generation for {path_label}",
                severity=Severity.ERROR,
                path=(path_label,),
                phase="migration_generate",
            )
        )
        return GenerationResult(
            definition=None,
            convertibility="unsupported",
            diagnostics=tuple(diagnostics),
            source_fingerprint=source_fp,
        )

    # Symbolic transform refs → manual.
    manual = False
    for step in spec.steps:
        ref = getattr(step, "transform_ref", None)
        if ref and ":" not in str(ref) and "." not in str(ref):
            manual = True
            diagnostics.append(
                mdl_diagnostic(
                    MDL210_MANUAL,
                    f"Manual conversion required for symbolic transform_ref {ref!r}",
                    severity=Severity.WARNING,
                    path=(path_label, step.name),
                    phase="migration_generate",
                )
            )

    convertibility: Convertibility = "manual" if manual else "auto"
    if require_auto and convertibility != "auto":
        return GenerationResult(
            definition=None,
            convertibility=convertibility,
            diagnostics=tuple(diagnostics),
            source_fingerprint=source_fp,
        )

    try:
        adapted = adapt_pipeline(spec)
    except AdapterError as exc:
        diagnostics.append(
            mdl_diagnostic(
                MDL220_UNSUPPORTED,
                f"Adaptation failed for {path_label}: {exc}",
                severity=Severity.ERROR,
                path=(path_label,),
                phase="migration_generate",
            )
        )
        return GenerationResult(
            definition=None,
            convertibility="unsupported",
            diagnostics=tuple(diagnostics),
            source_fingerprint=source_fp,
        )

    # Prefer facade-stamped definition from lowering result when available.
    defn = adapted.definition
    if not isinstance(defn, PipelineDefinition):
        defn = definition_from_pipeline(adapted.pipeline_cls)

    stamped = definition_provenance(
        defn,
        generator_id=GENERATOR_ID,
        source_fingerprint=source_fp,
        facade_protocol_version=FACADE_PROTOCOL_VERSION,
        facade_identity="medallantic",
        extras={
            "source_path": path_label,
            "builder_kind": str(getattr(spec, "engine", "") or "sparkforge_ir"),
        },
        action="attach",
    )
    assert isinstance(stamped, PipelineDefinition)
    diagnostics.append(
        mdl_diagnostic(
            MDL230_GENERATED,
            f"Generated native Medallantic definition from {path_label}",
            severity=Severity.INFO,
            path=(path_label,),
            phase="migration_generate",
        )
    )
    return GenerationResult(
        definition=stamped,
        convertibility=convertibility,
        diagnostics=tuple(diagnostics),
        source_fingerprint=source_fp,
        adaptation=adapted,
    )


def _stable_source_label(file_path: Path) -> str:
    """Return a cross-machine path label for provenance / fingerprints.

    Absolute paths make ``pipeline_fingerprint`` host-dependent (CI vs local).
    Prefer a path relative to the process cwd when the file lives under it;
    otherwise use the basename.
    """
    resolved = file_path.resolve()
    try:
        return str(resolved.relative_to(Path.cwd().resolve())).replace("\\", "/")
    except ValueError:
        return file_path.name


def generate_from_path(
    path: str | Path,
    *,
    require_auto: bool = True,
) -> GenerationResult:
    """Load JSON IR from disk and generate a native definition."""
    file_path = Path(path)
    label = _stable_source_label(file_path)
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return GenerationResult(
            definition=None,
            convertibility="unsupported",
            diagnostics=(
                mdl_diagnostic(
                    MDL220_UNSUPPORTED,
                    f"Cannot read IR JSON {label}: {exc}",
                    severity=Severity.ERROR,
                    path=(label,),
                    phase="migration_generate",
                ),
            ),
            source_fingerprint=None,
        )
    if not isinstance(payload, dict):
        return GenerationResult(
            definition=None,
            convertibility="unsupported",
            diagnostics=(
                mdl_diagnostic(
                    MDL220_UNSUPPORTED,
                    f"IR root must be an object: {label}",
                    severity=Severity.ERROR,
                    path=(label,),
                    phase="migration_generate",
                ),
            ),
        )
    return generate_from_ir(payload, source_path=label, require_auto=require_auto)


def generate_from_artifact(
    artifact: InventoryArtifact,
    *,
    root: str | Path,
    require_auto: bool = True,
) -> GenerationResult:
    """Generate from an inventory artifact under ``root`` when auto-safe."""
    if artifact.convertibility != "auto" and require_auto:
        return GenerationResult(
            definition=None,
            convertibility=artifact.convertibility,
            diagnostics=(
                mdl_diagnostic(
                    MDL210_MANUAL
                    if artifact.convertibility == "manual"
                    else MDL220_UNSUPPORTED,
                    f"Artifact {artifact.path} is {artifact.convertibility}; "
                    "refusing auto generation",
                    severity=Severity.WARNING,
                    path=(artifact.path,),
                    phase="migration_generate",
                ),
            ),
            source_fingerprint=artifact.source_fingerprint,
        )
    return generate_from_path(Path(root) / artifact.path, require_auto=require_auto)


__all__ = [
    "GENERATOR_ID",
    "GenerationResult",
    "generate_from_artifact",
    "generate_from_ir",
    "generate_from_path",
]
