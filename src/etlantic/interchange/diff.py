"""Contract diff / compatibility integration points."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import dpcs
import dtcs
import yaml
from contractmodel import CompatibilityMode, DataContract

from etlantic.contracts import Data, is_data_contract_type
from etlantic.diagnostics import Diagnostic, Severity, ValidationReport
from etlantic.interchange.diagnostics import map_toolkit_diagnostics
from etlantic.interchange.dpcs import pipeline_to_dpcs
from etlantic.interchange.dtcs import DtcsError, transformation_to_dtcs
from etlantic.interchange.security import read_text_bounded

_dpcs_api: Any = dpcs

_COMPATIBLE_DPCS_CATEGORIES = frozenset(
    {
        "compatible",
        "identical",
        "backwardcompatible",
        "forwardcompatible",
        "fullcompatible",
    }
)


def diff_data_contracts(
    previous: type[Data] | DataContract,
    current: type[Data] | DataContract,
    *,
    mode: CompatibilityMode = CompatibilityMode.BACKWARD,
) -> ValidationReport:
    """Compare two data contracts via ContractModel and return diagnostics."""
    left = _as_data_contract(previous)
    right = _as_data_contract(current)
    diff = left.diff(right, mode=mode)
    diagnostics: list[Diagnostic] = []
    for change in diff.breaking_changes:
        diagnostics.append(
            Diagnostic(
                code="PMDATA301",
                severity=Severity.ERROR,
                message=change.message,
                path=("data", change.field or ""),
                metadata={"toolkit_code": change.code, "breaking": True},
            )
        )
    for change in diff.non_breaking_changes:
        diagnostics.append(
            Diagnostic(
                code="PMDATA302",
                severity=Severity.WARNING,
                message=getattr(change, "message", str(change)),
                path=("data", getattr(change, "field", "") or ""),
                metadata={"breaking": False},
            )
        )
    if left.has_breaking_changes(right, mode=mode) and not diagnostics:
        diagnostics.append(
            Diagnostic(
                code="PMDATA301",
                severity=Severity.ERROR,
                message="Breaking data-contract changes detected.",
                path=("data",),
            )
        )
    return ValidationReport.from_diagnostics(diagnostics)


def diff_transformations(
    previous: type[Any] | dict[str, Any] | str | Path,
    current: type[Any] | dict[str, Any] | str | Path,
) -> ValidationReport:
    """Compare two transformations / DTCS docs via the dtcs toolkit."""
    try:
        left = _as_dtcs_doc(previous)
        right = _as_dtcs_doc(current)
        result = dtcs.compat_analyze(left, right)
    except (ValueError, TypeError, KeyError) as exc:
        return ValidationReport.from_diagnostics(
            [
                Diagnostic(
                    code="PMGEN203",
                    severity=Severity.ERROR,
                    message=f"DTCS diff failed: {exc}",
                    path=("dtcs", "diff"),
                )
            ]
        )
    except DtcsError as exc:
        # Fail closed with a stable ETLantic code; preserve toolkit details.
        base = [
            Diagnostic(
                code="PMGEN203",
                severity=Severity.ERROR,
                message=str(exc) or "DTCS diff failed.",
                path=("dtcs", "diff"),
            )
        ]
        if exc.report is not None and exc.report.diagnostics:
            return ValidationReport.from_diagnostics(
                [
                    *base,
                    *[
                        Diagnostic(
                            code=d.code,
                            severity=d.severity,
                            message=d.message,
                            path=d.path or ("dtcs", "diff"),
                            help=d.help,
                            related=d.related,
                            source=d.source,
                            metadata=d.metadata,
                            phase=d.phase,
                            actions=d.actions,
                        )
                        for d in exc.report.diagnostics
                    ],
                ]
            )
        return ValidationReport.from_diagnostics(base)
    if not isinstance(result, dict):
        return ValidationReport.from_diagnostics(
            [
                Diagnostic(
                    code="PMGEN301",
                    severity=Severity.ERROR,
                    message=f"Unexpected DTCS compat result: {result!r}",
                    path=("dtcs", "diff"),
                )
            ]
        )
    return map_toolkit_diagnostics(
        result.get("diagnostics"),
        default_code="PMGEN301",
        path=("dtcs", "diff"),
    )


def diff_pipelines(
    previous: type[Any] | dict[str, Any] | str | Path,
    current: type[Any] | dict[str, Any] | str | Path,
) -> ValidationReport:
    """Compare two pipelines / DPCS docs via the dpcs toolkit."""
    try:
        left = _as_dpcs_yaml(previous)
        right = _as_dpcs_yaml(current)
        result = _dpcs_api.compare_contract_yaml(left, right)
    except (ValueError, TypeError, KeyError) as exc:
        return ValidationReport.from_diagnostics(
            [
                Diagnostic(
                    code="PMGEN311",
                    severity=Severity.ERROR,
                    message=f"DPCS diff failed: {exc}",
                    path=("dpcs", "diff"),
                )
            ]
        )
    if not isinstance(result, dict):
        return ValidationReport.from_diagnostics(
            [
                Diagnostic(
                    code="PMGEN311",
                    severity=Severity.ERROR,
                    message=f"Unexpected DPCS compare result: {result!r}",
                    path=("dpcs", "diff"),
                )
            ]
        )

    report = map_toolkit_diagnostics(
        result.get("diagnostics"),
        default_code="PMGEN311",
        path=("dpcs", "diff"),
    )
    category = str(result.get("category") or "").replace("_", "").lower()
    if category and category not in _COMPATIBLE_DPCS_CATEGORIES and report.valid:
        return report.merge(
            ValidationReport.from_diagnostics(
                [
                    Diagnostic(
                        code="PMGEN311",
                        severity=Severity.ERROR,
                        message=(
                            f"DPCS documents are not compatible "
                            f"(category={result.get('category')!r})."
                        ),
                        path=("dpcs", "diff"),
                        metadata={"category": result.get("category")},
                    )
                ]
            )
        )
    return report


def _as_data_contract(value: type[Data] | DataContract) -> DataContract:
    if isinstance(value, DataContract):
        return value
    if is_data_contract_type(value):
        return DataContract.from_pydantic(value)
    raise TypeError("Expected Data / ContractModel class or DataContract instance")


def _as_dtcs_doc(value: type[Any] | dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, (str, Path)):
        path, text = read_text_bounded(value)
        parsed = dtcs.parse(text)
        if not isinstance(parsed, dict) or not isinstance(parsed.get("contract"), dict):
            parse_report = map_toolkit_diagnostics(
                (parsed or {}).get("report", {}).get("diagnostics")
                if isinstance(parsed, dict)
                else None,
                default_code="PMGEN203",
                source_path=str(path),
            )
            raise DtcsError(
                "DTCS parse did not return a contract document.",
                report=parse_report
                if not parse_report.valid
                else ValidationReport.from_diagnostics(
                    [
                        Diagnostic(
                            code="PMGEN203",
                            severity=Severity.ERROR,
                            message="DTCS parse did not return a contract document.",
                            path=("dtcs", "diff"),
                        )
                    ]
                ),
            )
        return dict(parsed["contract"])
    return transformation_to_dtcs(value)


def _as_dpcs_yaml(value: type[Any] | dict[str, Any] | str | Path) -> str:
    if isinstance(value, dict):
        return yaml.safe_dump(value, sort_keys=False)
    if isinstance(value, (str, Path)):
        _path, text = read_text_bounded(value)
        return text
    return yaml.safe_dump(pipeline_to_dpcs(value), sort_keys=False)
