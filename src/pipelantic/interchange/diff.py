"""Contract diff / compatibility integration points."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import dpcs
import dtcs
import yaml
from contractmodel import CompatibilityMode, DataContract

from pipelantic.contracts import DataContractModel, is_data_contract_type
from pipelantic.diagnostics import Diagnostic, Severity, ValidationReport
from pipelantic.interchange.diagnostics import map_toolkit_diagnostics
from pipelantic.interchange.dpcs import pipeline_to_dpcs
from pipelantic.interchange.dtcs import transformation_to_dtcs
from pipelantic.interchange.security import read_text_bounded


def diff_data_contracts(
    previous: type[DataContractModel] | DataContract,
    current: type[DataContractModel] | DataContract,
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
    left = _as_dtcs_doc(previous)
    right = _as_dtcs_doc(current)
    result = dtcs.compat_analyze(left, right)
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
    left = _as_dpcs_yaml(previous)
    right = _as_dpcs_yaml(current)
    result = dpcs.compare_contract_yaml(left, right)
    if isinstance(result, dict):
        return map_toolkit_diagnostics(
            result.get("diagnostics"),
            default_code="PMGEN311",
            path=("dpcs", "diff"),
        )
    # Some bindings return a plain summary string/bool.
    if result:
        return ValidationReport()
    return ValidationReport.from_diagnostics(
        [
            Diagnostic(
                code="PMGEN311",
                severity=Severity.ERROR,
                message="DPCS documents are not compatible.",
                path=("dpcs", "diff"),
            )
        ]
    )


def _as_data_contract(value: type[DataContractModel] | DataContract) -> DataContract:
    if isinstance(value, DataContract):
        return value
    if is_data_contract_type(value):
        return DataContract.from_pydantic(value)
    raise TypeError("Expected DataContractModel class or DataContract instance")


def _as_dtcs_doc(value: type[Any] | dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, (str, Path)):
        _path, text = read_text_bounded(value)
        parsed = dtcs.parse(text)
        return dict(parsed["contract"])
    return transformation_to_dtcs(value)


def _as_dpcs_yaml(value: type[Any] | dict[str, Any] | str | Path) -> str:
    if isinstance(value, dict):
        return yaml.safe_dump(value, sort_keys=False)
    if isinstance(value, (str, Path)):
        _path, text = read_text_bounded(value)
        return text
    return yaml.safe_dump(pipeline_to_dpcs(value), sort_keys=False)
