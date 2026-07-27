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
``secrets``, and ``testing`` (for example ``etl.sql`` after
``import etlantic as etl``).

``from etlantic import Data, Pipeline`` and public submodule imports remain
supported. Specialist root exports demoted in 0.22 remain available as
pre-1.0 compatibility aliases (warn once) — prefer the owning namespace.

Optional plugins live in separate packages (``etlantic-polars``,
``etlantic-sql``, ``etlantic-pyspark``, ``etlantic-airflow``, …). Install only
the engines you need and pin matching minors while ETLantic is pre-1.0.
"""

from __future__ import annotations

import importlib
import warnings
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
# Lazy namespaces and demoted aliases are resolved in __getattr__.

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
    "orchestration": "etlantic.orchestration",
    "viz": "etlantic.viz",
    "secrets": "etlantic.secrets",
    "testing": "etlantic.testing",
    "service": "etlantic.service",
}

# Pre-1.0 compatibility aliases for symbols demoted off the curated root.
# Values are (module, attribute). Access warns once per process.
_DEMOTED_ALIASES: dict[str, tuple[str, str]] = {
    "DATAFRAME_PROTOCOL_VERSION": ("etlantic.dataframe", "DATAFRAME_PROTOCOL_VERSION"),
    "ORCHESTRATION_PROTOCOL_VERSION": (
        "etlantic.orchestration",
        "ORCHESTRATION_PROTOCOL_VERSION",
    ),
    "PLUGIN_MANIFEST_SCHEMA": ("etlantic.plugin_manifest", "PLUGIN_MANIFEST_SCHEMA"),
    "SPARK_PROTOCOL_VERSION": ("etlantic.spark", "SPARK_PROTOCOL_VERSION"),
    "SQL_PROTOCOL_VERSION": ("etlantic.sql", "SQL_PROTOCOL_VERSION"),
    "STREAMING_STABILITY": ("etlantic.spark", "STREAMING_STABILITY"),
    "ArtifactOwnership": ("etlantic.dataframe", "ArtifactOwnership"),
    "ArtifactProvenance": ("etlantic.interchange", "ArtifactProvenance"),
    "ArtifactRef": ("etlantic.plan", "ArtifactRef"),
    "ArtifactStrategy": ("etlantic.plan", "ArtifactStrategy"),
    "BackfillDeclaration": ("etlantic.reliability", "BackfillDeclaration"),
    "BackfillRequest": ("etlantic.reliability_runtime", "BackfillRequest"),
    "BindingDescriptor": ("etlantic.registry", "BindingDescriptor"),
    "CallableStorage": ("etlantic.storage", "CallableStorage"),
    "CapabilityDecision": ("etlantic.capabilities", "CapabilityDecision"),
    "ContractBundle": ("etlantic.interchange", "ContractBundle"),
    "CsvStorage": ("etlantic.storage", "CsvStorage"),
    "DataValidationError": ("etlantic.exceptions", "DataValidationError"),
    "DataframeValidationOutcome": (
        "etlantic.dataframe",
        "DataframeValidationOutcome",
    ),
    "DataframeValidationPolicy": ("etlantic.dataframe", "DataframeValidationPolicy"),
    "DatasetRef": ("etlantic.spark", "DatasetRef"),
    "DebugSession": ("etlantic.runtime", "DebugSession"),
    "Diagnostic": ("etlantic.diagnostics", "Diagnostic"),
    "DiagnosticAction": ("etlantic.diagnostics", "DiagnosticAction"),
    "DriftAction": ("etlantic.schema_policy", "DriftAction"),
    "DriftImpact": ("etlantic.schema_drift", "DriftImpact"),
    "ETLanticError": ("etlantic.exceptions", "ETLanticError"),
    "Edge": ("etlantic.model", "Edge"),
    "Emit": ("etlantic.lifecycle", "Emit"),
    "FailureAction": ("etlantic.lifecycle", "FailureAction"),
    "FreshnessExpectation": ("etlantic.reliability", "FreshnessExpectation"),
    "IdempotencyDeclaration": ("etlantic.reliability", "IdempotencyDeclaration"),
    "ImplementationDescriptor": ("etlantic.registry", "ImplementationDescriptor"),
    "ImplementationRecord": ("etlantic.transformation", "ImplementationRecord"),
    "Inject": ("etlantic.lifecycle", "Inject"),
    "JsonStorage": ("etlantic.storage", "JsonStorage"),
    "LogicalGraph": ("etlantic.model", "LogicalGraph"),
    "MaterializationIntent": ("etlantic.reliability", "MaterializationIntent"),
    "MaterializationMode": ("etlantic.reliability", "MaterializationMode"),
    "MaterializationPolicy": ("etlantic.runtime", "MaterializationPolicy"),
    "MemoryStorage": ("etlantic.storage", "MemoryStorage"),
    "ModelDefinitionError": ("etlantic.exceptions", "ModelDefinitionError"),
    "Node": ("etlantic.model", "Node"),
    "NodeExecutionError": ("etlantic.exceptions", "NodeExecutionError"),
    "NodeKind": ("etlantic.model", "NodeKind"),
    "NormalizedSchema": ("etlantic.schema_drift", "NormalizedSchema"),
    "NullStorage": ("etlantic.storage", "NullStorage"),
    "OutboundEvent": ("etlantic.lifecycle", "OutboundEvent"),
    "OutboundPolicy": ("etlantic.outbound", "OutboundPolicy"),
    "OutputRef": ("etlantic.refs", "OutputRef"),
    "PartitionCompletenessExpectation": (
        "etlantic.reliability",
        "PartitionCompletenessExpectation",
    ),
    "PipelineCancelledError": ("etlantic.exceptions", "PipelineCancelledError"),
    "PipelineExecutionError": ("etlantic.exceptions", "PipelineExecutionError"),
    "PipelineTimeoutError": ("etlantic.exceptions", "PipelineTimeoutError"),
    "PipelineValidationError": ("etlantic.exceptions", "PipelineValidationError"),
    "PlanningContext": ("etlantic.registry", "PlanningContext"),
    "PluginCapabilities": ("etlantic.capabilities", "PluginCapabilities"),
    "PluginDescriptor": ("etlantic.registry", "PluginDescriptor"),
    "PluginManifest": ("etlantic.plugin_manifest", "PluginManifest"),
    "ProvenanceKind": ("etlantic.interchange", "ProvenanceKind"),
    "ReconciliationDeclaration": (
        "etlantic.reliability",
        "ReconciliationDeclaration",
    ),
    "RegistryBundle": ("etlantic.registry", "RegistryBundle"),
    "RelationRef": ("etlantic.sql", "RelationRef"),
    "ReliabilityEvidence": ("etlantic.reliability", "ReliabilityEvidence"),
    "RepairDeclaration": ("etlantic.reliability", "RepairDeclaration"),
    "ReportStore": ("etlantic.reports", "ReportStore"),
    "RetrySafetyDeclaration": ("etlantic.reliability", "RetrySafetyDeclaration"),
    "RunIntent": ("etlantic.runtime", "RunIntent"),
    "RunRequest": ("etlantic.runtime", "RunRequest"),
    "RunSelection": ("etlantic.runtime", "RunSelection"),
    "RunStatus": ("etlantic.runtime", "RunStatus"),
    "SafeIoPolicy": ("etlantic.io_policy", "SafeIoPolicy"),
    "SchemaChange": ("etlantic.schema_drift", "SchemaChange"),
    "SchemaChangeSet": ("etlantic.schema_drift", "SchemaChangeSet"),
    "SchemaDriftPolicy": ("etlantic.schema_policy", "SchemaDriftPolicy"),
    "SchemaObservation": ("etlantic.schema_drift", "SchemaObservation"),
    "SecretValue": ("etlantic.secrets", "SecretValue"),
    "Severity": ("etlantic.diagnostics", "Severity"),
    "SourceLocation": ("etlantic.diagnostics", "SourceLocation"),
    "SparkUdfPolicy": ("etlantic.spark", "SparkUdfPolicy"),
    "SqlQuery": ("etlantic.sql", "SqlQuery"),
    "Step": ("etlantic.transformation", "Step"),
    "StepFailureContext": ("etlantic.lifecycle", "StepFailureContext"),
    "SubpipelineInstance": ("etlantic.pipeline", "SubpipelineInstance"),
    "UnsafeSerializationError": (
        "etlantic.serialization_policy",
        "UnsafeSerializationError",
    ),
    "ValidationPolicy": ("etlantic.policy", "ValidationPolicy"),
    "WriteIntent": ("etlantic.reliability", "WriteIntent"),
    "WriteMode": ("etlantic.reliability", "WriteMode"),
    "builtin_stub_registry": ("etlantic.registry", "builtin_stub_registry"),
    "col": ("etlantic.sql", "col"),
    "concat": ("etlantic.sql", "concat"),
    "development_profile": ("etlantic.profile", "development_profile"),
    "diff_contract_schemas": ("etlantic.schema_drift", "diff_contract_schemas"),
    "diff_data_contracts": ("etlantic.interchange", "diff_data_contracts"),
    "diff_normalized_schemas": ("etlantic.schema_drift", "diff_normalized_schemas"),
    "diff_pipelines": ("etlantic.interchange", "diff_pipelines"),
    "diff_transformations": ("etlantic.interchange", "diff_transformations"),
    "discover_dataframe_plugins": (
        "etlantic.dataframe",
        "discover_dataframe_plugins",
    ),
    "discover_orchestrator_plugins": (
        "etlantic.orchestration",
        "discover_orchestrator_plugins",
    ),
    "discover_spark_plugins": ("etlantic.spark", "discover_spark_plugins"),
    "discover_spark_providers": ("etlantic.spark", "discover_spark_providers"),
    "discover_sql_plugins": ("etlantic.sql", "discover_sql_plugins"),
    "generate_contracts": ("etlantic.interchange", "generate_contracts"),
    "graphs_equivalent": ("etlantic.interchange", "graphs_equivalent"),
    "load_bundle": ("etlantic.interchange", "load_bundle"),
    "load_data_contract": ("etlantic.contracts", "load_data_contract"),
    "load_profile": ("etlantic.profile", "load_profile"),
    "normalize_pipeline": ("etlantic.interchange", "normalize_pipeline"),
    "normalize_schema_from_model": (
        "etlantic.schema_drift",
        "normalize_schema_from_model",
    ),
    "production_profile": ("etlantic.profile", "production_profile"),
    "resolve_profile": ("etlantic.profile", "resolve_profile"),
    "select": ("etlantic.sql", "select"),
    "test_profile": ("etlantic.profile", "test_profile"),
    "write_contracts": ("etlantic.interchange", "write_contracts"),
    "write_odcs": ("etlantic.contracts", "write_odcs"),
    "write_profile": ("etlantic.profile", "write_profile"),
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

_warned_demoted: set[str] = set()

__all__ = [
    *list(_CURATED.keys()),
]


def __dir__() -> list[str]:
    return sorted(
        set(__all__) | set(_DEMOTED_ALIASES) | {"DataContractModel"} | set(globals())
    )


def __getattr__(name: str) -> Any:
    if name == "DataContractModel":
        warnings.warn(
            "DataContractModel is deprecated; use etlantic.Data instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return Data
    if name in _REMOVED_AUTHORING:
        raise AttributeError(_REMOVED_AUTHORING[name])
    if name in _LAZY_NAMESPACES:
        module = importlib.import_module(_LAZY_NAMESPACES[name])
        globals()[name] = module
        return module
    if name in _DEMOTED_ALIASES:
        module_name, attr = _DEMOTED_ALIASES[name]
        if name not in _warned_demoted:
            _warned_demoted.add(name)
            warnings.warn(
                f"etlantic.{name} is a pre-1.0 compatibility alias; "
                f"prefer importing from {module_name} "
                f"(or use the owning lazy namespace). "
                "See docs/11_DEVELOPMENT/MIGRATION_0_21_TO_0_22.md.",
                DeprecationWarning,
                stacklevel=2,
            )
        value = getattr(importlib.import_module(module_name), attr)
        # Cache without re-warning on subsequent attribute access.
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
