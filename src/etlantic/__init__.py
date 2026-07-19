"""ETLantic — typed, contract-driven data pipeline modeling.

0.11 adds ``@Transformation.portable`` authoring through ``etlantic.transform``,
emitting ``dtcs.transform-plan/2``. Optional SparkForge migration adapter
(``etlantic-sparkforge``) remains available without introducing
bronze/silver/gold into core. Structured Streaming APIs remain experimental.
"""

from __future__ import annotations

import warnings
from typing import Any

from etlantic._version import __version__
from etlantic.capabilities import CapabilityDecision, PluginCapabilities
from etlantic.contracts import Data, load_data_contract, write_odcs
from etlantic.dataframe import (
    DATAFRAME_PROTOCOL_VERSION,
    ArtifactOwnership,
    DataframeValidationOutcome,
    DataframeValidationPolicy,
    discover_dataframe_plugins,
)
from etlantic.diagnostics import (
    Diagnostic,
    DiagnosticAction,
    Severity,
    SourceLocation,
    ValidationReport,
)
from etlantic.exceptions import (
    DataValidationError,
    ETLanticError,
    ModelDefinitionError,
    NodeExecutionError,
    PipelineCancelledError,
    PipelineExecutionError,
    PipelineTimeoutError,
    PipelineValidationError,
)
from etlantic.interchange import (
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
from etlantic.lifecycle import (
    Emit,
    FailureAction,
    Inject,
    OutboundEvent,
    PipelineRuntime,
    StepFailureContext,
)
from etlantic.model import Edge, LogicalGraph, Node, NodeKind
from etlantic.orchestration import (
    ORCHESTRATION_PROTOCOL_VERSION,
    compile_plan,
    discover_orchestrator_plugins,
)
from etlantic.pipeline import Extract, Load, Pipeline, Sink, Source, SubpipelineInstance
from etlantic.plan import (
    ArtifactRef,
    ArtifactStrategy,
    PipelinePlan,
    explain_plan,
    plan_pipeline,
)
from etlantic.policy import ValidationPolicy
from etlantic.ports import Input, Output, Parameter
from etlantic.profile import (
    Profile,
    development_profile,
    load_profile,
    production_profile,
    resolve_profile,
    test_profile,
    write_profile,
)
from etlantic.refs import OutputRef
from etlantic.registry import (
    BindingDescriptor,
    ImplementationDescriptor,
    PlanningContext,
    PluginDescriptor,
    RegistryBundle,
    builtin_stub_registry,
)
from etlantic.reliability import (
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
from etlantic.reliability_runtime import BackfillRequest
from etlantic.reports import PipelineRunReport, ReportStore
from etlantic.runtime import (
    DebugSession,
    MaterializationPolicy,
    RunIntent,
    RunRequest,
    RunSelection,
    RunStatus,
)
from etlantic.schema_drift import (
    DriftImpact,
    NormalizedSchema,
    SchemaChange,
    SchemaChangeSet,
    SchemaObservation,
    diff_contract_schemas,
    diff_normalized_schemas,
    normalize_schema_from_model,
)
from etlantic.schema_policy import DriftAction, SchemaDriftPolicy
from etlantic.secrets import SecretRef, SecretValue
from etlantic.spark import (
    SPARK_PROTOCOL_VERSION,
    STREAMING_STABILITY,
    DatasetRef,
    SparkUdfPolicy,
    discover_spark_plugins,
    discover_spark_providers,
)
from etlantic.sql import (
    SQL_PROTOCOL_VERSION,
    RelationRef,
    SqlQuery,
    col,
    concat,
    discover_sql_plugins,
    select,
)
from etlantic.storage import (
    CallableStorage,
    CsvStorage,
    JsonStorage,
    MemoryStorage,
    NullStorage,
)
from etlantic.transformation import ImplementationRecord, Step, Transformation

__all__ = [
    "DATAFRAME_PROTOCOL_VERSION",
    "ORCHESTRATION_PROTOCOL_VERSION",
    "SPARK_PROTOCOL_VERSION",
    "SQL_PROTOCOL_VERSION",
    "STREAMING_STABILITY",
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
    "DatasetRef",
    "DebugSession",
    "Diagnostic",
    "DiagnosticAction",
    "DriftAction",
    "DriftImpact",
    "ETLanticError",
    "Edge",
    "Emit",
    "Extract",
    "FailureAction",
    "FreshnessExpectation",
    "IdempotencyDeclaration",
    "ImplementationDescriptor",
    "ImplementationRecord",
    "Inject",
    "Input",
    "JsonStorage",
    "Load",
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
    "SparkUdfPolicy",
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
    "col",
    "compile_plan",
    "concat",
    "development_profile",
    "diff_contract_schemas",
    "diff_data_contracts",
    "diff_normalized_schemas",
    "diff_pipelines",
    "diff_transformations",
    "discover_dataframe_plugins",
    "discover_orchestrator_plugins",
    "discover_spark_plugins",
    "discover_spark_providers",
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
            "DataContractModel is deprecated; use etlantic.Data instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return Data
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
