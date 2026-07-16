"""Pipelantic — typed, contract-driven data pipeline modeling.

0.2 adds contract interoperability: ODCS via ContractModel, DTCS/DPCS
generate and load, deterministic bundles, and compatibility hooks.

Data contracts are provided by ContractModel. This package re-exports
``DataContractModel`` as an alias of ``contractmodel.ContractModel`` for
documentation-aligned imports.
"""

from pipelantic._version import __version__
from pipelantic.contracts import DataContractModel, load_data_contract, write_odcs
from pipelantic.diagnostics import (
    Diagnostic,
    Severity,
    SourceLocation,
    ValidationReport,
)
from pipelantic.exceptions import (
    ModelDefinitionError,
    PipelanticError,
    PipelineValidationError,
)
from pipelantic.interchange import (
    ArtifactProvenance,
    ContractBundle,
    ProvenanceKind,
    diff_data_contracts,
    diff_pipelines,
    diff_transformations,
    generate_contracts,
    graphs_equivalent,
    load_bundle,
    normalize_pipeline,
    write_contracts,
)
from pipelantic.model import Edge, LogicalGraph, Node, NodeKind
from pipelantic.pipeline import Pipeline, Sink, Source, SubpipelineInstance
from pipelantic.ports import Input, Output, Parameter
from pipelantic.refs import OutputRef
from pipelantic.transformation import ImplementationRecord, Step, Transformation

__all__ = [
    "ArtifactProvenance",
    "ContractBundle",
    "DataContractModel",
    "Diagnostic",
    "Edge",
    "ImplementationRecord",
    "Input",
    "LogicalGraph",
    "ModelDefinitionError",
    "Node",
    "NodeKind",
    "Output",
    "OutputRef",
    "Parameter",
    "PipelanticError",
    "Pipeline",
    "PipelineValidationError",
    "ProvenanceKind",
    "Severity",
    "Sink",
    "Source",
    "SourceLocation",
    "Step",
    "SubpipelineInstance",
    "Transformation",
    "ValidationReport",
    "__version__",
    "diff_data_contracts",
    "diff_pipelines",
    "diff_transformations",
    "generate_contracts",
    "graphs_equivalent",
    "load_bundle",
    "load_data_contract",
    "normalize_pipeline",
    "write_contracts",
    "write_odcs",
]
