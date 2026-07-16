"""Pipelantic — typed, contract-driven data pipeline modeling.

0.6 adds SQL-native execution with an independently installable
PostgreSQL reference plugin (``pipelantic-sql``).
"""

from __future__ import annotations

import warnings
from typing import Any

from pipelantic._version import __version__
from pipelantic.capabilities import CapabilityDecision, PluginCapabilities
from pipelantic.contracts import Data, load_data_contract, write_odcs
from pipelantic.dataframe import (
    DATAFRAME_PROTOCOL_VERSION,
    ArtifactOwnership,
    DataframeValidationOutcome,
    DataframeValidationPolicy,
    discover_dataframe_plugins,
)
from pipelantic.diagnostics import (
    Diagnostic,
    DiagnosticAction,
    Severity,
    SourceLocation,
    ValidationReport,
)
from pipelantic.exceptions import (
    DataValidationError,
    ModelDefinitionError,
    NodeExecutionError,
    PipelanticError,
    PipelineCancelledError,
    PipelineExecutionError,
    PipelineTimeoutError,
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
from pipelantic.lifecycle import (
    Emit,
    FailureAction,
    Inject,
    OutboundEvent,
    PipelineRuntime,
    StepFailureContext,
)
from pipelantic.model import Edge, LogicalGraph, Node, NodeKind
from pipelantic.pipeline import Pipeline, Sink, Source, SubpipelineInstance
from pipelantic.plan import (
    ArtifactRef,
    ArtifactStrategy,
    PipelinePlan,
    explain_plan,
    plan_pipeline,
)
from pipelantic.policy import ValidationPolicy
from pipelantic.ports import Input, Output, Parameter
from pipelantic.profile import (
    Profile,
    development_profile,
    load_profile,
    production_profile,
    resolve_profile,
    test_profile,
    write_profile,
)
from pipelantic.refs import OutputRef
from pipelantic.registry import (
    BindingDescriptor,
    ImplementationDescriptor,
    PlanningContext,
    PluginDescriptor,
    RegistryBundle,
    builtin_stub_registry,
)
from pipelantic.reliability import (
    BackfillDeclaration,
    FreshnessExpectation,
    IdempotencyDeclaration,
    MaterializationIntent,
    MaterializationMode,
    PartitionCompletenessExpectation,
    ReconciliationDeclaration,
    ReliabilityEvidence,
    RepairDeclaration,
    RetrySafetyDeclaration,
    WriteIntent,
    WriteMode,
)
from pipelantic.reliability_runtime import BackfillRequest
from pipelantic.reports import PipelineRunReport, ReportStore
from pipelantic.runtime import (
    DebugSession,
    MaterializationPolicy,
    RunIntent,
    RunRequest,
    RunSelection,
    RunStatus,
)
from pipelantic.schema_drift import (
    DriftImpact,
    NormalizedSchema,
    SchemaChange,
    SchemaChangeSet,
    SchemaObservation,
    diff_contract_schemas,
    diff_normalized_schemas,
    normalize_schema_from_model,
)
from pipelantic.schema_policy import DriftAction, SchemaDriftPolicy
from pipelantic.secrets import SecretRef, SecretValue
from pipelantic.sql import (
    SQL_PROTOCOL_VERSION,
    RelationRef,
    SqlQuery,
    discover_sql_plugins,
    select,
)
from pipelantic.storage import (
    CallableStorage,
    CsvStorage,
    JsonStorage,
    MemoryStorage,
    NullStorage,
)
from pipelantic.transformation import ImplementationRecord, Step, Transformation

__all__ = [
    "DATAFRAME_PROTOCOL_VERSION",
    "SQL_PROTOCOL_VERSION",
    "ArtifactOwnership",
    "ArtifactProvenance",
    "ArtifactRef",
    "ArtifactStrategy",
    "BackfillDeclaration",
    "BackfillRequest",
    "BindingDescriptor",
    "CallableStorage",
    "CapabilityDecision",
    "ContractBundle",
    "CsvStorage",
    "Data",
    "DataContractModel",
    "DataValidationError",
    "DataframeValidationOutcome",
    "DataframeValidationPolicy",
    "DebugSession",
    "Diagnostic",
    "DiagnosticAction",
    "DriftAction",
    "DriftImpact",
    "Edge",
    "Emit",
    "FailureAction",
    "FreshnessExpectation",
    "IdempotencyDeclaration",
    "ImplementationDescriptor",
    "ImplementationRecord",
    "Inject",
    "Input",
    "JsonStorage",
    "LogicalGraph",
    "MaterializationIntent",
    "MaterializationMode",
    "MaterializationPolicy",
    "MemoryStorage",
    "ModelDefinitionError",
    "Node",
    "NodeExecutionError",
    "NodeKind",
    "NormalizedSchema",
    "NullStorage",
    "OutboundEvent",
    "Output",
    "OutputRef",
    "Parameter",
    "PartitionCompletenessExpectation",
    "PipelanticError",
    "Pipeline",
    "PipelineCancelledError",
    "PipelineExecutionError",
    "PipelinePlan",
    "PipelineRunReport",
    "PipelineRuntime",
    "PipelineTimeoutError",
    "PipelineValidationError",
    "PlanningContext",
    "PluginCapabilities",
    "PluginDescriptor",
    "Profile",
    "ProvenanceKind",
    "ReconciliationDeclaration",
    "RegistryBundle",
    "RelationRef",
    "ReliabilityEvidence",
    "RepairDeclaration",
    "ReportStore",
    "RetrySafetyDeclaration",
    "RunIntent",
    "RunRequest",
    "RunSelection",
    "RunStatus",
    "SchemaChange",
    "SchemaChangeSet",
    "SchemaDriftPolicy",
    "SchemaObservation",
    "SecretRef",
    "SecretValue",
    "Severity",
    "Sink",
    "Source",
    "SourceLocation",
    "SqlQuery",
    "Step",
    "StepFailureContext",
    "SubpipelineInstance",
    "Transformation",
    "ValidationPolicy",
    "ValidationReport",
    "WriteIntent",
    "WriteMode",
    "__version__",
    "builtin_stub_registry",
    "development_profile",
    "diff_contract_schemas",
    "diff_data_contracts",
    "diff_normalized_schemas",
    "diff_pipelines",
    "diff_transformations",
    "discover_dataframe_plugins",
    "discover_sql_plugins",
    "explain_plan",
    "generate_contracts",
    "graphs_equivalent",
    "load_bundle",
    "load_data_contract",
    "load_profile",
    "normalize_pipeline",
    "normalize_schema_from_model",
    "plan_pipeline",
    "production_profile",
    "resolve_profile",
    "select",
    "test_profile",
    "write_contracts",
    "write_odcs",
    "write_profile",
]


def __getattr__(name: str) -> Any:
    if name == "DataContractModel":
        warnings.warn(
            "DataContractModel is deprecated; use pipelantic.Data instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return Data
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
