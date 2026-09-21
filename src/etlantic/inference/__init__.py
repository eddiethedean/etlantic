"""Optional, data first schema and model inference."""

from .facade import model_from_schema
from .records import infer_csv, infer_json, infer_records
from .sources import infer_source, infer_source_async
from .targets import (
    backfill_schema,
    check_write_compatibility,
    infer_records_for_target,
    infer_records_for_target_async,
    inspect_target,
    inspect_target_async,
    solve_backward_constraints,
)
from .transfer import forward_schema, infer_expression, infer_frame_schema
from .types import (
    FieldConstraint,
    InferenceLimits,
    InferenceObservation,
    InferenceResult,
    OutputProposal,
    ReplayHandle,
    SchemaEvidence,
    TargetObservation,
    WriteCompatibility,
)

__all__ = [
    "FieldConstraint",
    "InferenceLimits",
    "InferenceObservation",
    "InferenceResult",
    "OutputProposal",
    "ReplayHandle",
    "SchemaEvidence",
    "TargetObservation",
    "WriteCompatibility",
    "backfill_schema",
    "check_write_compatibility",
    "forward_schema",
    "infer_csv",
    "infer_expression",
    "infer_frame_schema",
    "infer_json",
    "infer_records",
    "infer_records_for_target",
    "infer_records_for_target_async",
    "infer_source",
    "infer_source_async",
    "inspect_target",
    "inspect_target_async",
    "model_from_schema",
    "solve_backward_constraints",
]
