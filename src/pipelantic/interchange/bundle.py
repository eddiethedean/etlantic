"""Deterministic contract bundles and discovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipelantic.diagnostics import Diagnostic, Severity, ValidationReport
from pipelantic.exceptions import PipelanticError
from pipelantic.identity import published_contract_id, transformation_id
from pipelantic.interchange.dpcs import (
    dpcs_filename,
    pipeline_from_dpcs,
    pipeline_to_dpcs,
)
from pipelantic.interchange.dtcs import dtcs_filename, write_dtcs
from pipelantic.interchange.odcs import odcs_filename, write_odcs
from pipelantic.interchange.provenance import ArtifactProvenance, ProvenanceKind
from pipelantic.interchange.security import resolve_safe_path
from pipelantic.model import NodeKind


class BundleError(PipelanticError):
    """Raised when contract bundle generation or loading fails."""

    def __init__(self, message: str, *, report: ValidationReport | None = None) -> None:
        super().__init__(message)
        self.report = report or ValidationReport()


@dataclass
class ContractBundle:
    """In-memory view of a generated or loaded contract bundle."""

    root: Path | None = None
    pipeline_id: str | None = None
    data_contracts: dict[str, type[Any]] = field(default_factory=dict)
    transformations: dict[str, type[Any]] = field(default_factory=dict)
    pipeline: type[Any] | None = None
    documents: dict[str, dict[str, Any]] = field(default_factory=dict)
    paths: dict[str, Path] = field(default_factory=dict)
    provenance: dict[str, ArtifactProvenance] = field(default_factory=dict)


def generate_contracts(pipeline_cls: type[Any]) -> ContractBundle:
    """Discover contracts and build an in-memory bundle for ``pipeline_cls``."""
    from pipelantic.pipeline import Pipeline

    if not isinstance(pipeline_cls, type) or not issubclass(pipeline_cls, Pipeline):
        raise BundleError("generate_contracts requires a Pipeline subclass")

    report = pipeline_cls.validate()
    if not report.valid:
        raise BundleError(
            "Refusing to generate contracts from an invalid pipeline.",
            report=report,
        )

    graph = pipeline_cls.build_graph()
    data_contracts: dict[str, type[Any]] = {}
    transformations: dict[str, type[Any]] = {}

    for node in graph.nodes:
        if (node.kind is NodeKind.SOURCE and node.contract_type is not None) or (
            node.kind is NodeKind.SINK and node.contract_type is not None
        ):
            _remember_data_contract(data_contracts, node.contract_type)
        elif node.kind is NodeKind.STEP:
            member = pipeline_cls.__pipeline_members__[node.name]
            transform = member.transformation
            tid = getattr(transform, "__published_id__", None) or transformation_id(
                transform
            )
            transformations[str(tid)] = transform
            for port in (*transform.inputs(), *transform.outputs()):
                if port.contract_type is not None:
                    _remember_data_contract(data_contracts, port.contract_type)

    data_locations = {
        cid: f"data/{odcs_filename(model)}" for cid, model in data_contracts.items()
    }
    transform_locations = {
        tid: f"transformations/{dtcs_filename(transform)}"
        for tid, transform in transformations.items()
    }
    dpcs_doc = pipeline_to_dpcs(
        pipeline_cls,
        data_locations=data_locations,
        transform_locations=transform_locations,
    )

    documents: dict[str, dict[str, Any]] = {
        f"pipelines/{dpcs_filename(pipeline_cls)}": dpcs_doc,
    }
    for transform in transformations.values():
        from pipelantic.interchange.dtcs import transformation_to_dtcs

        documents[f"transformations/{dtcs_filename(transform)}"] = (
            transformation_to_dtcs(transform)
        )
    for model in data_contracts.values():
        from pipelantic.interchange.odcs import data_contract_document

        documents[f"data/{odcs_filename(model)}"] = data_contract_document(model)

    return ContractBundle(
        pipeline_id=str(dpcs_doc["id"]),
        data_contracts=data_contracts,
        transformations=transformations,
        pipeline=pipeline_cls,
        documents=documents,
        provenance={
            str(dpcs_doc["id"]): ArtifactProvenance(
                kind=ProvenanceKind.PYTHON,
                identity=str(dpcs_doc["id"]),
                version=str(dpcs_doc.get("version")),
            )
        },
    )


def write_contracts(pipeline_cls: type[Any], directory: str | Path) -> ContractBundle:
    """Generate and write a deterministic contract bundle under ``directory``."""
    bundle = generate_contracts(pipeline_cls)
    root = resolve_safe_path(directory)
    root.mkdir(parents=True, exist_ok=True)
    (root / "data").mkdir(exist_ok=True)
    (root / "transformations").mkdir(exist_ok=True)
    (root / "pipelines").mkdir(exist_ok=True)

    paths: dict[str, Path] = {}
    for cid, model in sorted(bundle.data_contracts.items(), key=lambda item: item[0]):
        path = root / "data" / odcs_filename(model)
        write_odcs(model, path, root=root)
        paths[f"odcs:{cid}"] = path

    for tid, transform in sorted(
        bundle.transformations.items(), key=lambda item: item[0]
    ):
        path = root / "transformations" / dtcs_filename(transform)
        write_dtcs(transform, path)
        paths[f"dtcs:{tid}"] = path

    pipeline_path = root / "pipelines" / dpcs_filename(pipeline_cls)
    from pipelantic.interchange.dpcs import write_dpcs

    write_dpcs(
        pipeline_cls,
        pipeline_path,
        data_locations={
            cid: f"data/{odcs_filename(model)}"
            for cid, model in bundle.data_contracts.items()
        },
        transform_locations={
            tid: f"transformations/{dtcs_filename(transform)}"
            for tid, transform in bundle.transformations.items()
        },
    )
    paths["pipeline"] = pipeline_path
    bundle.root = root
    bundle.paths = paths
    return bundle


def load_bundle(directory: str | Path) -> ContractBundle:
    """Load a contract bundle directory and reconstruct the pipeline class."""
    root = resolve_safe_path(directory)
    if not root.is_dir():
        raise BundleError(
            f"Contract bundle directory not found: {root}",
            report=ValidationReport.from_diagnostics(
                [
                    Diagnostic(
                        code="PMSRC104",
                        severity=Severity.ERROR,
                        message=f"Contract bundle directory not found: {root}",
                    )
                ]
            ),
        )

    pipeline_files = sorted((root / "pipelines").glob("*.dpcs.yaml"))
    if not pipeline_files:
        raise BundleError(
            "Bundle contains no DPCS pipeline artifacts.",
            report=ValidationReport.from_diagnostics(
                [
                    Diagnostic(
                        code="PMGEN230",
                        severity=Severity.ERROR,
                        message="Bundle contains no DPCS pipeline artifacts.",
                        path=("bundle", "pipelines"),
                    )
                ]
            ),
        )
    if len(pipeline_files) > 1:
        raise BundleError(
            "Bundle contains multiple DPCS pipelines; pass an explicit path.",
            report=ValidationReport.from_diagnostics(
                [
                    Diagnostic(
                        code="PMGEN231",
                        severity=Severity.ERROR,
                        message="Bundle contains multiple DPCS pipelines.",
                        path=("bundle", "pipelines"),
                    )
                ]
            ),
        )

    # Locations in DPCS are relative to the DPCS file directory (pipelines/).
    pipeline_cls = pipeline_from_dpcs(pipeline_files[0], root=root)
    graph = pipeline_cls.build_graph()
    data_contracts: dict[str, type[Any]] = {}
    transformations: dict[str, type[Any]] = {}
    for node in graph.nodes:
        if node.contract_type is not None:
            _remember_data_contract(data_contracts, node.contract_type)
        if node.kind is NodeKind.STEP:
            member = pipeline_cls.__pipeline_members__[node.name]
            tid = getattr(member.transformation, "__published_id__", None) or (
                transformation_id(member.transformation)
            )
            transformations[str(tid)] = member.transformation

    return ContractBundle(
        root=root,
        pipeline_id=getattr(pipeline_cls, "__published_id__", None),
        data_contracts=data_contracts,
        transformations=transformations,
        pipeline=pipeline_cls,
        paths={"pipeline": pipeline_files[0]},
        provenance={
            str(getattr(pipeline_cls, "__published_id__", pipeline_cls.__name__)): (
                ArtifactProvenance(
                    kind=ProvenanceKind.DPCS,
                    path=str(pipeline_files[0]),
                    identity=getattr(pipeline_cls, "__published_id__", None),
                    version=getattr(pipeline_cls, "__published_version__", None),
                )
            )
        },
    )


def _remember_data_contract(
    store: dict[str, type[Any]],
    model: type[Any],
) -> None:
    cid = published_contract_id(model) or model.__name__.lower()
    store[cid] = model
