"""ODCS load/save facades over ContractModel ``DataContract``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from contractmodel import ContractModel, DataContract

from pipelantic.diagnostics import (
    Diagnostic,
    Severity,
    SourceLocation,
    ValidationReport,
)
from pipelantic.exceptions import PipelanticError
from pipelantic.identity import identity_slug
from pipelantic.interchange.policy import check_odcs_version
from pipelantic.interchange.provenance import ArtifactProvenance, ProvenanceKind
from pipelantic.interchange.security import read_text_bounded, resolve_safe_path


class ContractLoadError(PipelanticError):
    """Raised when an ODCS artifact cannot be loaded safely."""

    def __init__(self, message: str, *, report: ValidationReport | None = None) -> None:
        super().__init__(message)
        self.report = report or ValidationReport()


def load_data_contract(
    path: str | Path,
    *,
    root: str | Path | None = None,
    class_name: str | None = None,
) -> type[ContractModel]:
    """Load an ODCS file into a ``ContractModel`` subclass via ContractModel."""
    resolved, _text = read_text_bounded(path, root=root)
    data_contract = DataContract.from_odcs(resolved)
    version_report = check_odcs_version(
        _odcs_api_version(data_contract),
        path=("odcs", str(resolved)),
    )
    if not version_report.valid:
        raise ContractLoadError(
            version_report.errors[0].message,
            report=version_report,
        )

    model = data_contract.to_pydantic(class_name=class_name)
    model.__published_id__ = str(data_contract.contract_id)  # type: ignore[attr-defined]
    model.__published_version__ = str(data_contract.version)  # type: ignore[attr-defined]
    model.__provenance__ = ArtifactProvenance(  # type: ignore[attr-defined]
        kind=ProvenanceKind.ODCS,
        path=str(resolved),
        identity=str(data_contract.contract_id),
        version=str(data_contract.version),
    )
    return model


def write_odcs(
    model: type[ContractModel],
    path: str | Path,
    *,
    root: str | Path | None = None,
) -> Path:
    """Write a ``ContractModel`` class to an ODCS YAML file."""
    resolved = resolve_safe_path(path, root=root)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    data_contract = DataContract.from_pydantic(model)
    version_report = check_odcs_version(
        _odcs_api_version(data_contract),
        path=("odcs", str(resolved)),
    )
    if not version_report.valid:
        raise ContractLoadError(
            version_report.errors[0].message,
            report=version_report,
        )
    data_contract.save(resolved, format="odcs")
    return resolved


def data_contract_document(model: type[ContractModel]) -> dict[str, Any]:
    """Return the ODCS document dict for a data-contract class."""
    return dict(DataContract.from_pydantic(model).to_odcs())


def odcs_filename(model: type[ContractModel]) -> str:
    """Stable ODCS filename for a data-contract class."""
    published = getattr(model, "__published_id__", None)
    if not isinstance(published, str) or not published:
        published = str(DataContract.from_pydantic(model).contract_id)
    return f"{identity_slug(published)}.odcs.yaml"


def schema_fields_for_dtcs(model: type[ContractModel]) -> list[dict[str, Any]]:
    """Project ContractModel fields into DTCS schema field dicts."""
    data_contract = DataContract.from_pydantic(model)
    fields: list[dict[str, Any]] = []
    for field in data_contract.fields:
        logical = getattr(field.logical_type, "value", field.logical_type)
        fields.append(
            {
                "name": field.name,
                "type": _dtcs_type(str(logical)),
                "nullable": bool(field.nullable) or not bool(field.required),
            }
        )
    return fields


def _dtcs_type(logical_type: str) -> str:
    mapping = {
        "integer": "integer",
        "long": "integer",
        "number": "number",
        "float": "number",
        "double": "number",
        "string": "string",
        "boolean": "boolean",
        "bool": "boolean",
        "date": "date",
        "datetime": "timestamp",
        "timestamp": "timestamp",
        "object": "object",
        "array": "array",
    }
    return mapping.get(logical_type.lower(), "string")


def _odcs_api_version(data_contract: DataContract) -> str | None:
    document = data_contract.to_odcs()
    if isinstance(document, dict):
        value = document.get("apiVersion")
        return str(value) if value is not None else None
    return None


def ensure_data_contract_type(
    model: Any,
    *,
    path: tuple[str, ...] = (),
) -> ValidationReport:
    """Return a diagnostic when ``model`` is not a ContractModel subclass."""
    if isinstance(model, type) and issubclass(model, ContractModel):
        return ValidationReport()
    return ValidationReport.from_diagnostics(
        [
            Diagnostic(
                code="PMDATA101",
                severity=Severity.ERROR,
                message="Expected a DataContractModel / ContractModel subclass.",
                path=path,
                source=SourceLocation(object_ref=repr(model)),
            )
        ]
    )
