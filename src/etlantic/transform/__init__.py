"""Portable PySpark-inspired transformation authoring (`etlantic.transform/1`)."""

from __future__ import annotations

from etlantic.transform import functions
from etlantic.transform.column import ColumnExpr, ParameterRef
from etlantic.transform.compiler import (
    COMPILER_PROTOCOL,
    OBLIGATIONS,
    SUPPORT_STATES,
    CompiledTransform,
    PortableTransformCompiler,
    TransformCapabilities,
    TransformCompileContext,
    TransformCompilerInfo,
    TransformExecutionContext,
    TransformOutputBundle,
    TransformPlanningContext,
    TransformPushdownFinding,
    TransformSupportFinding,
    TransformSupportReport,
)
from etlantic.transform.complex import array, create_map, element_at, size, struct
from etlantic.transform.dataframe import FrameExpr, GroupedData, input_frame
from etlantic.transform.dtcs_builder import build_portable_definition, invoke_portable
from etlantic.transform.lambda_expr import exists, forall, lambda_, transform
from etlantic.transform.portable_baseline import (
    BASELINE_ID,
    SUPPORT_PROTOCOL_ID,
    PortableRequirement,
    PortableSupportFinding,
    baseline_manifest,
    support_fingerprint,
)
from etlantic.transform.protocol import (
    AUTHORING_PROFILE,
    INVALID,
    MISSING,
    PLAN_PROTOCOL,
    PortableDefinition,
    TransformBudgets,
)
from etlantic.transform.window import Window, WindowSpec

__all__ = [
    "AUTHORING_PROFILE",
    "BASELINE_ID",
    "COMPILER_PROTOCOL",
    "INVALID",
    "MISSING",
    "OBLIGATIONS",
    "PLAN_PROTOCOL",
    "SUPPORT_PROTOCOL_ID",
    "SUPPORT_STATES",
    "ColumnExpr",
    "CompiledTransform",
    "FrameExpr",
    "GroupedData",
    "ParameterRef",
    "PortableDefinition",
    "PortableRequirement",
    "PortableSupportFinding",
    "PortableTransformCompiler",
    "TransformBudgets",
    "TransformCapabilities",
    "TransformCompileContext",
    "TransformCompilerInfo",
    "TransformExecutionContext",
    "TransformOutputBundle",
    "TransformPlanningContext",
    "TransformPushdownFinding",
    "TransformSupportFinding",
    "TransformSupportReport",
    "Window",
    "WindowSpec",
    "array",
    "baseline_manifest",
    "build_portable_definition",
    "create_map",
    "element_at",
    "exists",
    "forall",
    "functions",
    "input_frame",
    "invoke_portable",
    "lambda_",
    "size",
    "struct",
    "support_fingerprint",
    "transform",
]
