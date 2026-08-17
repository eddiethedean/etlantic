"""ETLantic — typed, contract-driven data pipeline modeling.

Recommended application and tutorial import style (0.22+)::

    import etlantic as etl


    class Customer(etl.Data): ...

Curated root symbols (stable): ``Data``, ``Transformation``, ``Pipeline``,
``Extract``, ``Load``, ``Input``, ``Output``, ``Parameter``, ``Profile``,
``PipelineRuntime``, ``PipelinePlan``, ``plan_pipeline``, ``explain_plan``,
``ValidationReport``, ``PipelineRunReport``, ``SecretRef``, ``compile_plan``,
and ``__version__``.

Lazy namespaces (import-safe; no optional engines until accessed):
``transform``, ``dataframe``, ``sql``, ``spark``, ``orchestration``, ``viz``,
``secrets``, ``testing``, ``quality``, ``connectors``, ``service``,
``control_plane``, ``optimization``, and ``streaming`` (for example ``etl.sql`` after
``import etlantic as etl``).

``from etlantic import Data, Pipeline`` and public submodule imports remain
supported. Specialist symbols live on owning modules or lazy namespaces
(``etl.dataframe``, ``etl.sql``, …) — not on the curated root.

Optional plugins live in separate packages (``etlantic-polars``,
``etlantic-sql``, ``etlantic-pyspark``, ``etlantic-airflow``, …). Install only
the engines you need and pin matching minors throughout ETLantic's 0.x roadmap.
"""

from __future__ import annotations

import importlib
from typing import Any

from etlantic._version import __version__
from etlantic.contracts import Data
from etlantic.diagnostics import ValidationReport
from etlantic.lifecycle import PipelineRuntime
from etlantic.orchestration import compile_plan
from etlantic.pipeline import Extract, Load, Pipeline
from etlantic.plan import PipelinePlan, explain_plan, plan_pipeline
from etlantic.ports import Input, Output, Parameter
from etlantic.profile import Profile
from etlantic.reports import PipelineRunReport
from etlantic.secrets import SecretRef
from etlantic.transformation import Transformation

# Curated root facade (stable ownership — see surface-inventory.json).
# Lazy namespaces and removed-root messages are resolved in __getattr__.

_CURATED: dict[str, Any] = {
    "Data": Data,
    "Transformation": Transformation,
    "Pipeline": Pipeline,
    "Extract": Extract,
    "Load": Load,
    "Input": Input,
    "Output": Output,
    "Parameter": Parameter,
    "Profile": Profile,
    "PipelineRuntime": PipelineRuntime,
    "PipelinePlan": PipelinePlan,
    "plan_pipeline": plan_pipeline,
    "explain_plan": explain_plan,
    "ValidationReport": ValidationReport,
    "PipelineRunReport": PipelineRunReport,
    "SecretRef": SecretRef,
    "compile_plan": compile_plan,
    "__version__": __version__,
}

# Namespace names remain in __all__; modules are bound above.
_LAZY_NAMESPACES: dict[str, str] = {
    "authoring": "etlantic.authoring",
    "transform": "etlantic.transform",
    "dataframe": "etlantic.dataframe",
    "sql": "etlantic.sql",
    "spark": "etlantic.spark",
    "quality": "etlantic.quality",
    "orchestration": "etlantic.orchestration",
    "viz": "etlantic.viz",
    "secrets": "etlantic.secrets",
    "testing": "etlantic.testing",
    "service": "etlantic.service",
    "connectors": "etlantic.connectors",
    "control_plane": "etlantic.control_plane",
    "optimization": "etlantic.optimization",
    "streaming": "etlantic.streaming",
}

# Demoted root aliases were removed in 0.37.0 (see _REMOVED_0_37).
_DEMOTED_ALIASES: dict[str, tuple[str, str]] = {}

_REMOVED_0_37: dict[str, str] = {
    "ArtifactOwnership": (
        "ArtifactOwnership was removed from the etlantic root in 0.37.0; "
        "import from etlantic.dataframe instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "ArtifactRef": (
        "ArtifactRef was removed from the etlantic root in 0.37.0; "
        "import from etlantic.plan instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "ArtifactStrategy": (
        "ArtifactStrategy was removed from the etlantic root in 0.37.0; "
        "import from etlantic.plan instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "BackfillRequest": (
        "BackfillRequest was removed from the etlantic root in 0.37.0; "
        "import from etlantic.reliability_runtime instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "CapabilityDecision": (
        "CapabilityDecision was removed from the etlantic root in 0.37.0; "
        "import from etlantic.capabilities instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "DataframeValidationOutcome": (
        "DataframeValidationOutcome was removed from the etlantic root in 0.37.0; "
        "import from etlantic.dataframe instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "DataframeValidationPolicy": (
        "DataframeValidationPolicy was removed from the etlantic root in 0.37.0; "
        "import from etlantic.dataframe instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "DatasetRef": (
        "DatasetRef was removed from the etlantic root in 0.37.0; "
        "import from etlantic.spark instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "Diagnostic": (
        "Diagnostic was removed from the etlantic root in 0.37.0; "
        "import from etlantic.diagnostics instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "DiagnosticAction": (
        "DiagnosticAction was removed from the etlantic root in 0.37.0; "
        "import from etlantic.diagnostics instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "DriftAction": (
        "DriftAction was removed from the etlantic root in 0.37.0; "
        "import from etlantic.schema_policy instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "Edge": (
        "Edge was removed from the etlantic root in 0.37.0; "
        "import from etlantic.model instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "ImplementationRecord": (
        "ImplementationRecord was removed from the etlantic root in 0.37.0; "
        "import from etlantic.transformation instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "LogicalGraph": (
        "LogicalGraph was removed from the etlantic root in 0.37.0; "
        "import from etlantic.model instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "Node": (
        "Node was removed from the etlantic root in 0.37.0; "
        "import from etlantic.model instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "NodeKind": (
        "NodeKind was removed from the etlantic root in 0.37.0; "
        "import from etlantic.model instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "OutboundPolicy": (
        "OutboundPolicy was removed from the etlantic root in 0.37.0; "
        "import from etlantic.outbound instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "OutputRef": (
        "OutputRef was removed from the etlantic root in 0.37.0; "
        "import from etlantic.refs instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "PluginCapabilities": (
        "PluginCapabilities was removed from the etlantic root in 0.37.0; "
        "import from etlantic.capabilities instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "PluginManifest": (
        "PluginManifest was removed from the etlantic root in 0.37.0; "
        "import from etlantic.plugin_manifest instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "ReportStore": (
        "ReportStore was removed from the etlantic root in 0.37.0; "
        "import from etlantic.reports instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "SafeIoPolicy": (
        "SafeIoPolicy was removed from the etlantic root in 0.37.0; "
        "import from etlantic.io_policy instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "SchemaDriftPolicy": (
        "SchemaDriftPolicy was removed from the etlantic root in 0.37.0; "
        "import from etlantic.schema_policy instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "SecretValue": (
        "SecretValue was removed from the etlantic root in 0.37.0; "
        "import from etlantic.secrets instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "Severity": (
        "Severity was removed from the etlantic root in 0.37.0; "
        "import from etlantic.diagnostics instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "SourceLocation": (
        "SourceLocation was removed from the etlantic root in 0.37.0; "
        "import from etlantic.diagnostics instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "SparkUdfPolicy": (
        "SparkUdfPolicy was removed from the etlantic root in 0.37.0; "
        "import from etlantic.spark instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "Step": (
        "Step was removed from the etlantic root in 0.37.0; "
        "import from etlantic.transformation instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "SubpipelineInstance": (
        "SubpipelineInstance was removed from the etlantic root in 0.37.0; "
        "import from etlantic.pipeline instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "ValidationPolicy": (
        "ValidationPolicy was removed from the etlantic root in 0.37.0; "
        "import from etlantic.policy instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "discover_dataframe_plugins": (
        "discover_dataframe_plugins was removed from the etlantic root in 0.37.0; "
        "import from etlantic.dataframe instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "discover_orchestrator_plugins": (
        "discover_orchestrator_plugins was removed from the etlantic root in 0.37.0; "
        "import from etlantic.orchestration instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "discover_spark_plugins": (
        "discover_spark_plugins was removed from the etlantic root in 0.37.0; "
        "import from etlantic.spark instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "discover_spark_providers": (
        "discover_spark_providers was removed from the etlantic root in 0.37.0; "
        "import from etlantic.spark instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "load_data_contract": (
        "load_data_contract was removed from the etlantic root in 0.37.0; "
        "import from etlantic.contracts instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "write_odcs": (
        "write_odcs was removed from the etlantic root in 0.37.0; "
        "import from etlantic.contracts instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
    "DataContractModel": (
        "DataContractModel was removed from the etlantic root in 0.37.0; "
        "use etlantic.Data / ContractModel instead. See docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md."
    ),
}


_REMOVED_AUTHORING = {
    "Source": (
        "Source was removed in ETLantic 0.16. Use Extract instead. "
        "See docs/11_DEVELOPMENT/MIGRATION_0_15_TO_0_16.md."
    ),
    "Sink": (
        "Sink was removed in ETLantic 0.16. Use Load instead. "
        "See docs/11_DEVELOPMENT/MIGRATION_0_15_TO_0_16.md."
    ),
}


_REMOVED_0_26: dict[str, str] = {
    "ArtifactProvenance": (
        "ArtifactProvenance was removed from the etlantic root in 0.26.0; "
        "import from etlantic.interchange instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "CallableStorage": (
        "CallableStorage was removed from the etlantic root in 0.26.0; "
        "import from etlantic.storage instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "ContractBundle": (
        "ContractBundle was removed from the etlantic root in 0.26.0; "
        "import from etlantic.interchange instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "CsvStorage": (
        "CsvStorage was removed from the etlantic root in 0.26.0; "
        "import from etlantic.storage instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "DATAFRAME_PROTOCOL_VERSION": (
        "DATAFRAME_PROTOCOL_VERSION was removed from the etlantic root in 0.26.0; "
        "import from etlantic.dataframe instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "DataValidationError": (
        "DataValidationError was removed from the etlantic root in 0.26.0; "
        "import from etlantic.exceptions instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "DebugSession": (
        "DebugSession was removed from the etlantic root in 0.26.0; "
        "import from etlantic.runtime instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "ETLanticError": (
        "ETLanticError was removed from the etlantic root in 0.26.0; "
        "import from etlantic.exceptions instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "JsonStorage": (
        "JsonStorage was removed from the etlantic root in 0.26.0; "
        "import from etlantic.storage instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "MaterializationPolicy": (
        "MaterializationPolicy was removed from the etlantic root in 0.26.0; "
        "import from etlantic.runtime instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "MemoryStorage": (
        "MemoryStorage was removed from the etlantic root in 0.26.0; "
        "import from etlantic.storage instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "ModelDefinitionError": (
        "ModelDefinitionError was removed from the etlantic root in 0.26.0; "
        "import from etlantic.exceptions instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "NodeExecutionError": (
        "NodeExecutionError was removed from the etlantic root in 0.26.0; "
        "import from etlantic.exceptions instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "NullStorage": (
        "NullStorage was removed from the etlantic root in 0.26.0; "
        "import from etlantic.storage instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "ORCHESTRATION_PROTOCOL_VERSION": (
        "ORCHESTRATION_PROTOCOL_VERSION was removed from the etlantic root in 0.26.0; "
        "import from etlantic.orchestration instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "PLUGIN_MANIFEST_SCHEMA": (
        "PLUGIN_MANIFEST_SCHEMA was removed from the etlantic root in 0.26.0; "
        "import from etlantic.plugin_manifest instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "PipelineCancelledError": (
        "PipelineCancelledError was removed from the etlantic root in 0.26.0; "
        "import from etlantic.exceptions instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "PipelineExecutionError": (
        "PipelineExecutionError was removed from the etlantic root in 0.26.0; "
        "import from etlantic.exceptions instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "PipelineTimeoutError": (
        "PipelineTimeoutError was removed from the etlantic root in 0.26.0; "
        "import from etlantic.exceptions instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "PipelineValidationError": (
        "PipelineValidationError was removed from the etlantic root in 0.26.0; "
        "import from etlantic.exceptions instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "ProvenanceKind": (
        "ProvenanceKind was removed from the etlantic root in 0.26.0; "
        "import from etlantic.interchange instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "RunIntent": (
        "RunIntent was removed from the etlantic root in 0.26.0; "
        "import from etlantic.runtime instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "RunRequest": (
        "RunRequest was removed from the etlantic root in 0.26.0; "
        "import from etlantic.runtime instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "RunSelection": (
        "RunSelection was removed from the etlantic root in 0.26.0; "
        "import from etlantic.runtime instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "RunStatus": (
        "RunStatus was removed from the etlantic root in 0.26.0; "
        "import from etlantic.runtime instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "SPARK_PROTOCOL_VERSION": (
        "SPARK_PROTOCOL_VERSION was removed from the etlantic root in 0.26.0; "
        "import from etlantic.spark instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "SQL_PROTOCOL_VERSION": (
        "SQL_PROTOCOL_VERSION was removed from the etlantic root in 0.26.0; "
        "import from etlantic.sql instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "STREAMING_STABILITY": (
        "STREAMING_STABILITY was removed from the etlantic root in 0.26.0; "
        "import from etlantic.spark instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "UnsafeSerializationError": (
        "UnsafeSerializationError was removed from the etlantic root in 0.26.0; "
        "import from etlantic.serialization_policy instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "diff_data_contracts": (
        "diff_data_contracts was removed from the etlantic root in 0.26.0; "
        "import from etlantic.interchange instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "diff_pipelines": (
        "diff_pipelines was removed from the etlantic root in 0.26.0; "
        "import from etlantic.interchange instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "diff_transformations": (
        "diff_transformations was removed from the etlantic root in 0.26.0; "
        "import from etlantic.interchange instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "generate_contracts": (
        "generate_contracts was removed from the etlantic root in 0.26.0; "
        "import from etlantic.interchange instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "graphs_equivalent": (
        "graphs_equivalent was removed from the etlantic root in 0.26.0; "
        "import from etlantic.interchange instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "load_bundle": (
        "load_bundle was removed from the etlantic root in 0.26.0; "
        "import from etlantic.interchange instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "normalize_pipeline": (
        "normalize_pipeline was removed from the etlantic root in 0.26.0; "
        "import from etlantic.interchange instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
    "write_contracts": (
        "write_contracts was removed from the etlantic root in 0.26.0; "
        "import from etlantic.interchange instead. See docs/11_DEVELOPMENT/MIGRATION_0_25_TO_0_26.md."
    ),
}

_REMOVED_0_27: dict[str, str] = {
    "BackfillDeclaration": (
        "BackfillDeclaration was removed from the etlantic root in 0.27.0; "
        "import from etlantic.reliability instead. See docs/11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md."
    ),
    "BindingDescriptor": (
        "BindingDescriptor was removed from the etlantic root in 0.27.0; "
        "import from etlantic.registry instead. See docs/11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md."
    ),
    "DriftImpact": (
        "DriftImpact was removed from the etlantic root in 0.27.0; "
        "import from etlantic.schema_drift instead. See docs/11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md."
    ),
    "FreshnessExpectation": (
        "FreshnessExpectation was removed from the etlantic root in 0.27.0; "
        "import from etlantic.reliability instead. See docs/11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md."
    ),
    "IdempotencyDeclaration": (
        "IdempotencyDeclaration was removed from the etlantic root in 0.27.0; "
        "import from etlantic.reliability instead. See docs/11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md."
    ),
    "ImplementationDescriptor": (
        "ImplementationDescriptor was removed from the etlantic root in 0.27.0; "
        "import from etlantic.registry instead. See docs/11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md."
    ),
    "MaterializationIntent": (
        "MaterializationIntent was removed from the etlantic root in 0.27.0; "
        "import from etlantic.reliability instead. See docs/11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md."
    ),
    "MaterializationMode": (
        "MaterializationMode was removed from the etlantic root in 0.27.0; "
        "import from etlantic.reliability instead. See docs/11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md."
    ),
    "NormalizedSchema": (
        "NormalizedSchema was removed from the etlantic root in 0.27.0; "
        "import from etlantic.schema_drift instead. See docs/11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md."
    ),
    "PartitionCompletenessExpectation": (
        "PartitionCompletenessExpectation was removed from the etlantic root in 0.27.0; "
        "import from etlantic.reliability instead. See docs/11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md."
    ),
    "PlanningContext": (
        "PlanningContext was removed from the etlantic root in 0.27.0; "
        "import from etlantic.registry instead. See docs/11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md."
    ),
    "PluginDescriptor": (
        "PluginDescriptor was removed from the etlantic root in 0.27.0; "
        "import from etlantic.registry instead. See docs/11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md."
    ),
    "ReconciliationDeclaration": (
        "ReconciliationDeclaration was removed from the etlantic root in 0.27.0; "
        "import from etlantic.reliability instead. See docs/11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md."
    ),
    "RegistryBundle": (
        "RegistryBundle was removed from the etlantic root in 0.27.0; "
        "import from etlantic.registry instead. See docs/11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md."
    ),
    "ReliabilityEvidence": (
        "ReliabilityEvidence was removed from the etlantic root in 0.27.0; "
        "import from etlantic.reliability instead. See docs/11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md."
    ),
    "RepairDeclaration": (
        "RepairDeclaration was removed from the etlantic root in 0.27.0; "
        "import from etlantic.reliability instead. See docs/11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md."
    ),
    "RetrySafetyDeclaration": (
        "RetrySafetyDeclaration was removed from the etlantic root in 0.27.0; "
        "import from etlantic.reliability instead. See docs/11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md."
    ),
    "SchemaChange": (
        "SchemaChange was removed from the etlantic root in 0.27.0; "
        "import from etlantic.schema_drift instead. See docs/11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md."
    ),
    "SchemaChangeSet": (
        "SchemaChangeSet was removed from the etlantic root in 0.27.0; "
        "import from etlantic.schema_drift instead. See docs/11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md."
    ),
    "SchemaObservation": (
        "SchemaObservation was removed from the etlantic root in 0.27.0; "
        "import from etlantic.schema_drift instead. See docs/11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md."
    ),
    "WriteIntent": (
        "WriteIntent was removed from the etlantic root in 0.27.0; "
        "import from etlantic.reliability instead. See docs/11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md."
    ),
    "WriteMode": (
        "WriteMode was removed from the etlantic root in 0.27.0; "
        "import from etlantic.reliability instead. See docs/11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md."
    ),
    "builtin_stub_registry": (
        "builtin_stub_registry was removed from the etlantic root in 0.27.0; "
        "import from etlantic.registry instead. See docs/11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md."
    ),
    "diff_contract_schemas": (
        "diff_contract_schemas was removed from the etlantic root in 0.27.0; "
        "import from etlantic.schema_drift instead. See docs/11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md."
    ),
    "diff_normalized_schemas": (
        "diff_normalized_schemas was removed from the etlantic root in 0.27.0; "
        "import from etlantic.schema_drift instead. See docs/11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md."
    ),
    "normalize_schema_from_model": (
        "normalize_schema_from_model was removed from the etlantic root in 0.27.0; "
        "import from etlantic.schema_drift instead. See docs/11_DEVELOPMENT/MIGRATION_0_26_TO_0_27.md."
    ),
}

_REMOVED_0_28: dict[str, str] = {
    "Emit": (
        "Emit was removed from the etlantic root in 0.28.0; "
        "import from etlantic.lifecycle instead. See docs/11_DEVELOPMENT/MIGRATION_0_27_TO_0_28.md."
    ),
    "FailureAction": (
        "FailureAction was removed from the etlantic root in 0.28.0; "
        "import from etlantic.lifecycle instead. See docs/11_DEVELOPMENT/MIGRATION_0_27_TO_0_28.md."
    ),
    "Inject": (
        "Inject was removed from the etlantic root in 0.28.0; "
        "import from etlantic.lifecycle instead. See docs/11_DEVELOPMENT/MIGRATION_0_27_TO_0_28.md."
    ),
    "OutboundEvent": (
        "OutboundEvent was removed from the etlantic root in 0.28.0; "
        "import from etlantic.lifecycle instead. See docs/11_DEVELOPMENT/MIGRATION_0_27_TO_0_28.md."
    ),
    "RelationRef": (
        "RelationRef was removed from the etlantic root in 0.28.0; "
        "import from etlantic.sql instead. See docs/11_DEVELOPMENT/MIGRATION_0_27_TO_0_28.md."
    ),
    "SqlQuery": (
        "SqlQuery was removed from the etlantic root in 0.28.0; "
        "import from etlantic.sql instead. See docs/11_DEVELOPMENT/MIGRATION_0_27_TO_0_28.md."
    ),
    "StepFailureContext": (
        "StepFailureContext was removed from the etlantic root in 0.28.0; "
        "import from etlantic.lifecycle instead. See docs/11_DEVELOPMENT/MIGRATION_0_27_TO_0_28.md."
    ),
    "col": (
        "col was removed from the etlantic root in 0.28.0; "
        "import from etlantic.sql instead. See docs/11_DEVELOPMENT/MIGRATION_0_27_TO_0_28.md."
    ),
    "concat": (
        "concat was removed from the etlantic root in 0.28.0; "
        "import from etlantic.sql instead. See docs/11_DEVELOPMENT/MIGRATION_0_27_TO_0_28.md."
    ),
    "development_profile": (
        "development_profile was removed from the etlantic root in 0.28.0; "
        "import from etlantic.profile instead. See docs/11_DEVELOPMENT/MIGRATION_0_27_TO_0_28.md."
    ),
    "discover_sql_plugins": (
        "discover_sql_plugins was removed from the etlantic root in 0.28.0; "
        "import from etlantic.sql instead. See docs/11_DEVELOPMENT/MIGRATION_0_27_TO_0_28.md."
    ),
    "load_profile": (
        "load_profile was removed from the etlantic root in 0.28.0; "
        "import from etlantic.profile instead. See docs/11_DEVELOPMENT/MIGRATION_0_27_TO_0_28.md."
    ),
    "production_profile": (
        "production_profile was removed from the etlantic root in 0.28.0; "
        "import from etlantic.profile instead. See docs/11_DEVELOPMENT/MIGRATION_0_27_TO_0_28.md."
    ),
    "resolve_profile": (
        "resolve_profile was removed from the etlantic root in 0.28.0; "
        "import from etlantic.profile instead. See docs/11_DEVELOPMENT/MIGRATION_0_27_TO_0_28.md."
    ),
    "select": (
        "select was removed from the etlantic root in 0.28.0; "
        "import from etlantic.sql instead. See docs/11_DEVELOPMENT/MIGRATION_0_27_TO_0_28.md."
    ),
    "test_profile": (
        "test_profile was removed from the etlantic root in 0.28.0; "
        "import from etlantic.profile instead. See docs/11_DEVELOPMENT/MIGRATION_0_27_TO_0_28.md."
    ),
    "write_profile": (
        "write_profile was removed from the etlantic root in 0.28.0; "
        "import from etlantic.profile instead. See docs/11_DEVELOPMENT/MIGRATION_0_27_TO_0_28.md."
    ),
}


__all__ = [
    *list(_CURATED.keys()),
]


def __dir__() -> list[str]:
    return sorted(
        set(__all__)
        | set(_REMOVED_0_26)
        | set(_REMOVED_0_27)
        | set(_REMOVED_0_28)
        | set(_REMOVED_0_37)
        | set(_LAZY_NAMESPACES)
    )


def __getattr__(name: str) -> Any:
    if name in _REMOVED_AUTHORING:
        raise AttributeError(_REMOVED_AUTHORING[name])
    if name in _REMOVED_0_26:
        raise AttributeError(_REMOVED_0_26[name])
    if name in _REMOVED_0_27:
        raise AttributeError(_REMOVED_0_27[name])
    if name in _REMOVED_0_28:
        raise AttributeError(_REMOVED_0_28[name])
    if name in _REMOVED_0_37:
        raise AttributeError(_REMOVED_0_37[name])
    if name in _LAZY_NAMESPACES:
        module = importlib.import_module(_LAZY_NAMESPACES[name])
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
