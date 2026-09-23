# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnnecessaryIsInstance=false
"""Transformation ↔ DTCS document adaptation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import dtcs
import yaml

from etlantic.diagnostics import (
    Diagnostic,
    Severity,
    SourceLocation,
    ValidationReport,
)
from etlantic.exceptions import ETLanticError, ModelDefinitionError
from etlantic.identity import identity_slug, transformation_id
from etlantic.interchange.diagnostics import map_toolkit_diagnostics
from etlantic.interchange.odcs import schema_fields_for_dtcs
from etlantic.interchange.policy import (
    DEFAULT_DTCS_VERSION,
    check_dtcs_version,
)
from etlantic.interchange.provenance import ArtifactProvenance, ProvenanceKind
from etlantic.interchange.security import read_text_bounded, resolve_safe_path
from etlantic.ports import Input, Output, Parameter


class DtcsError(ETLanticError):
    """Raised when DTCS generation or loading fails."""

    def __init__(self, message: str, *, report: ValidationReport | None = None) -> None:
        super().__init__(message)
        self.report = report or ValidationReport()


def transformation_to_dtcs(transformation_cls: type[Any]) -> dict[str, Any]:
    """Build a DTCS document dict from a Transformation subclass."""
    from etlantic.transformation import Transformation

    if not isinstance(transformation_cls, type) or not issubclass(
        transformation_cls, Transformation
    ):
        raise ModelDefinitionError("to_dtcs requires a Transformation subclass")

    problems = transformation_cls.validate_definition()
    if problems:
        raise DtcsError("; ".join(problems))

    published_id = getattr(
        transformation_cls, "__published_id__", None
    ) or transformation_id(transformation_cls)
    published_version = (
        getattr(transformation_cls, "__published_version__", None) or "0.1.0"
    )

    inputs: list[dict[str, Any]] = []
    for port in transformation_cls.inputs():
        entry: dict[str, Any] = {"id": port.name}
        if port.contract_type is not None:
            try:
                entry["schema"] = {"fields": schema_fields_for_dtcs(port.contract_type)}
            except ValueError as exc:
                raise DtcsError(
                    str(exc),
                    report=ValidationReport.from_diagnostics(
                        [
                            Diagnostic(
                                code="PMGEN206",
                                severity=Severity.ERROR,
                                message=str(exc),
                                path=("dtcs", "inputs", port.name),
                            )
                        ]
                    ),
                ) from exc
            entry["etlantic:contractId"] = _published_or_authoring_id(
                port.contract_type
            )
            entry["etlantic:contractVersion"] = _published_or_authoring_version(
                port.contract_type
            )
        inputs.append(entry)

    outputs: list[dict[str, Any]] = []
    for port in transformation_cls.outputs():
        entry = {"id": port.name}
        if port.contract_type is not None:
            try:
                entry["schema"] = {"fields": schema_fields_for_dtcs(port.contract_type)}
            except ValueError as exc:
                raise DtcsError(
                    str(exc),
                    report=ValidationReport.from_diagnostics(
                        [
                            Diagnostic(
                                code="PMGEN206",
                                severity=Severity.ERROR,
                                message=str(exc),
                                path=("dtcs", "outputs", port.name),
                            )
                        ]
                    ),
                ) from exc
            entry["etlantic:contractId"] = _published_or_authoring_id(
                port.contract_type
            )
            entry["etlantic:contractVersion"] = _published_or_authoring_version(
                port.contract_type
            )
        outputs.append(entry)

    parameters: list[dict[str, Any]] = []
    for port in transformation_cls.parameters():
        param: dict[str, Any] = {
            "id": port.name,
            "type": _parameter_type_name(port.contract_type),
        }
        if port.has_default:
            param["default"] = port.default
        parameters.append(param)

    doc: dict[str, Any] = {
        "dtcsVersion": DEFAULT_DTCS_VERSION,
        "id": published_id,
        "name": transformation_cls.__name__,
        "version": published_version,
        "inputs": inputs,
        "outputs": outputs,
    }
    if parameters:
        # DTCS toolkit rejects a top-level `parameters` field; use a namespaced
        # vendor extension that round-trips through ETLantic.
        doc["etlantic:parameters"] = parameters
    if outputs:
        doc["lineage"] = {
            "mappings": [
                {
                    "output": out["id"],
                    "inputs": [inp["id"] for inp in inputs] or [out["id"]],
                }
                for out in outputs
            ]
        }

    report = validate_dtcs_document(doc)
    if not report.valid:
        raise DtcsError(report.errors[0].message, report=report)
    return doc


def write_dtcs(transformation_cls: type[Any], path: str | Path) -> Path:
    """Write a Transformation to a DTCS YAML file."""
    doc = transformation_to_dtcs(transformation_cls)
    resolved = resolve_safe_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(_stable_yaml(doc), encoding="utf-8")
    return resolved


def transformation_from_dtcs(
    source: str | Path | dict[str, Any],
    *,
    contracts: dict[str, type[Any]] | None = None,
    root: str | Path | None = None,
    class_name: str | None = None,
) -> type[Any]:
    """Load a DTCS artifact into a dynamic Transformation subclass."""
    from etlantic.transformation import Transformation

    path_str: str | None = None
    if isinstance(source, dict):
        doc = dict(source)
    else:
        resolved, text = read_text_bounded(source, root=root)
        path_str = str(resolved)
        parsed = dtcs.parse(text)
        if not isinstance(parsed, dict) or "contract" not in parsed:
            raise DtcsError(
                "DTCS parse did not return a contract document.",
                report=ValidationReport.from_diagnostics(
                    [
                        Diagnostic(
                            code="PMGEN203",
                            severity=Severity.ERROR,
                            message="DTCS parse did not return a contract document.",
                            source=SourceLocation(path=path_str),
                        )
                    ]
                ),
            )
        parse_report = map_toolkit_diagnostics(
            parsed.get("report", {}).get("diagnostics"),
            default_code="PMGEN203",
            source_path=path_str,
        )
        if not parse_report.valid:
            raise DtcsError(parse_report.errors[0].message, report=parse_report)
        doc = dict(parsed["contract"])

    version_report = check_dtcs_version(doc.get("dtcsVersion"), path=("dtcs",))
    if not version_report.valid:
        raise DtcsError(version_report.errors[0].message, report=version_report)

    report = validate_dtcs_document(doc, source_path=path_str)
    if not report.valid:
        raise DtcsError(report.errors[0].message, report=report)

    contract_map = dict(contracts or {})
    annotations: dict[str, Any] = {}
    namespace: dict[str, Any] = {
        "__module__": "etlantic.interchange.generated",
        "__published_id__": str(doc["id"]),
        "__published_version__": str(doc.get("version") or "0.1.0"),
        "__provenance__": ArtifactProvenance(
            kind=ProvenanceKind.DTCS,
            path=path_str,
            identity=str(doc["id"]),
            version=str(doc.get("version") or "0.1.0"),
        ),
    }

    for entry in doc.get("inputs") or []:
        name = str(entry["id"])
        annotations[name] = Input[_resolve_port_contract(entry, contract_map)]
    for entry in doc.get("outputs") or []:
        name = str(entry["id"])
        annotations[name] = Output[_resolve_port_contract(entry, contract_map)]
    for entry in list(doc.get("etlantic:parameters") or []) + list(
        doc.get("parameters") or []
    ):
        name = str(entry["id"])
        py_type = _parameter_python_type(entry.get("type"))
        annotations[name] = Parameter[py_type]
        if "default" in entry:
            namespace[name] = entry["default"]

    namespace["__annotations__"] = annotations
    dynamic_name = class_name or _safe_class_name(str(doc.get("name") or doc["id"]))
    return type(dynamic_name, (Transformation,), namespace)


def validate_dtcs_document(
    doc: dict[str, Any],
    *,
    source_path: str | None = None,
) -> ValidationReport:
    """Validate a DTCS document via the dtcs toolkit and version policy."""
    version_report = check_dtcs_version(doc.get("dtcsVersion"), path=("dtcs",))
    toolkit = dtcs.validate(doc)
    toolkit_report = map_toolkit_diagnostics(
        toolkit.get("diagnostics"),
        default_code="PMGEN204",
        source_path=source_path,
        path=("dtcs",),
    )
    return version_report.merge(toolkit_report)


def dtcs_filename(transformation_cls: type[Any]) -> str:
    """Stable DTCS filename for a transformation class."""
    published = getattr(
        transformation_cls, "__published_id__", None
    ) or transformation_id(transformation_cls)
    return f"{identity_slug(str(published))}.dtcs.yaml"


def _resolve_port_contract(
    entry: dict[str, Any],
    contracts: dict[str, type[Any]],
) -> type[Any]:
    ref_id: str | None = None
    if entry.get("etlantic:contractId") is not None:
        ref_id = str(entry["etlantic:contractId"])
    else:
        ref = entry.get("contractRef")
        if isinstance(ref, dict) and ref.get("id") is not None:
            ref_id = str(ref["id"])
        elif isinstance(ref, str):
            ref_id = ref
    resolved = _lookup_contract(ref_id, contracts) if ref_id else None
    if resolved is not None:
        return resolved
    if ref_id:
        raise DtcsError(
            f"Unresolved data-contract reference {ref_id!r}.",
            report=ValidationReport.from_diagnostics(
                [
                    Diagnostic(
                        code="PMGEN205",
                        severity=Severity.ERROR,
                        message=f"Unresolved data-contract reference {ref_id!r}.",
                        path=("dtcs", "contractRef", ref_id),
                        help="Load ODCS contracts into the registry before from_dtcs.",
                    )
                ]
            ),
        )
    # Fall back to a synthetic empty contract when schema-only ports appear.
    from contractmodel import ContractModel

    fields = ((entry.get("schema") or {}).get("fields")) or []
    annotations = {
        str(field["name"]): _annotation_for_dtcs_type(field.get("type"))
        for field in fields
        if "name" in field
    }
    name = _safe_class_name(str(entry.get("id") or "AnonymousContract"))
    return type(
        name,
        (ContractModel,),
        {
            "__annotations__": annotations,
            "__module__": "etlantic.interchange.generated",
        },
    )


def _lookup_contract(
    ref_id: str,
    contracts: dict[str, type[Any]],
) -> type[Any] | None:
    """Resolve a contract ref against bare or ``odcs:``-prefixed registry keys."""
    candidates = [ref_id]
    if ref_id.startswith("odcs:"):
        candidates.append(ref_id[5:])
    else:
        candidates.append(f"odcs:{ref_id}")
    for key in candidates:
        if key in contracts:
            return contracts[key]
    for value in contracts.values():
        published = getattr(value, "__published_id__", None)
        if published == ref_id or f"odcs:{published}" == ref_id:
            return value
    return None


def _published_or_authoring_id(contract_type: type[Any]) -> str:
    from etlantic.identity import published_contract_id, qualified_type_id

    return published_contract_id(contract_type) or qualified_type_id(contract_type)


def _published_or_authoring_version(contract_type: type[Any]) -> str:
    from etlantic.identity import published_contract_version

    return published_contract_version(contract_type) or "1.0.0"


def _parameter_type_name(annotation: Any) -> str:
    if annotation is None:
        return "string"
    mapping = {
        int: "integer",
        float: "number",
        bool: "boolean",
        str: "string",
    }
    return mapping.get(annotation, "string")


def _parameter_python_type(type_name: Any) -> type[Any]:
    mapping: dict[str, type[Any]] = {
        "integer": int,
        "number": float,
        "boolean": bool,
        "string": str,
    }
    return mapping.get(str(type_name or "string").lower(), str)


def _annotation_for_dtcs_type(type_name: Any) -> type[Any]:
    """Map DTCS field types to Python annotations for schema-only ports."""
    from datetime import date, datetime, time
    from decimal import Decimal

    mapping: dict[str, type[Any]] = {
        "integer": int,
        "number": float,
        "decimal": Decimal,
        "boolean": bool,
        "string": str,
        "datetime": datetime,
        "date": date,
        "time": time,
        "binary": bytes,
        "bytes": bytes,
    }
    return mapping.get(str(type_name or "string").lower(), str)


def _safe_class_name(name: str) -> str:
    parts = [p for p in name.replace("-", "_").replace(".", "_").split("_") if p]
    cleaned = "".join(p[:1].upper() + p[1:] for p in parts) or "Generated"
    if cleaned[0].isdigit():
        cleaned = f"T{cleaned}"
    return cleaned


def _stable_yaml(doc: dict[str, Any]) -> str:
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
