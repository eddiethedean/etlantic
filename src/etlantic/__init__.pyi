"""Typed stub for the curated ``import etlantic as etl`` facade (0.22).

Lazy namespaces (``etl.sql``, ``etl.testing``, …) resolve to the real
subpackages on the filesystem; they are intentionally omitted here so
static analyzers do not shadow ``etlantic.<ns>`` modules.
"""

from __future__ import annotations

from typing import Any

from etlantic.contracts import Data as Data
from etlantic.diagnostics import ValidationReport as ValidationReport
from etlantic.inference import (
    FieldConstraint as FieldConstraint,
)
from etlantic.inference import (
    InferenceLimits as InferenceLimits,
)
from etlantic.inference import (
    InferenceObservation as InferenceObservation,
)
from etlantic.inference import (
    InferenceResult as InferenceResult,
)
from etlantic.inference import (
    OutputProposal as OutputProposal,
)
from etlantic.inference import (
    ReplayHandle as ReplayHandle,
)
from etlantic.inference import (
    ResolvedFileSource as ResolvedFileSource,
)
from etlantic.inference import (
    SchemaEvidence as SchemaEvidence,
)
from etlantic.inference import (
    TargetObservation as TargetObservation,
)
from etlantic.inference import (
    WriteCompatibility as WriteCompatibility,
)
from etlantic.inference import (
    backfill_schema as backfill_schema,
)
from etlantic.inference import (
    check_write_compatibility as check_write_compatibility,
)
from etlantic.inference import (
    forward_schema as forward_schema,
)
from etlantic.inference import (
    infer_csv as infer_csv,
)
from etlantic.inference import (
    infer_expression as infer_expression,
)
from etlantic.inference import (
    infer_frame_schema as infer_frame_schema,
)
from etlantic.inference import (
    infer_json as infer_json,
)
from etlantic.inference import (
    infer_records as infer_records,
)
from etlantic.inference import (
    infer_records_for_target as infer_records_for_target,
)
from etlantic.inference import (
    infer_records_for_target_async as infer_records_for_target_async,
)
from etlantic.inference import (
    infer_source as infer_source,
)
from etlantic.inference import (
    infer_source_async as infer_source_async,
)
from etlantic.inference import (
    inspect_target as inspect_target,
)
from etlantic.inference import (
    inspect_target_async as inspect_target_async,
)
from etlantic.inference import (
    model_from_schema as model_from_schema,
)
from etlantic.inference import (
    rebind_definition as rebind_definition,
)
from etlantic.inference import (
    register_source_factory as register_source_factory,
)
from etlantic.inference import (
    reopen_source_binding as reopen_source_binding,
)
from etlantic.inference import (
    resolve_source_binding as resolve_source_binding,
)
from etlantic.inference import (
    solve_backward_constraints as solve_backward_constraints,
)
from etlantic.inference import (
    unregister_file_source as unregister_file_source,
)
from etlantic.inference import (
    unregister_source_factory as unregister_source_factory,
)
from etlantic.inference import (
    validate_source_binding as validate_source_binding,
)
from etlantic.inference import (
    validate_target_binding as validate_target_binding,
)
from etlantic.inference.facade import (
    InferredDataset as InferredDataset,
)
from etlantic.inference.facade import (
    from_pandas as from_pandas,
)
from etlantic.inference.facade import (
    from_polars as from_polars,
)
from etlantic.inference.facade import (
    from_records as from_records,
)
from etlantic.inference.facade import (
    from_records_for_target as from_records_for_target,
)
from etlantic.inference.facade import (
    read_csv as read_csv,
)
from etlantic.inference.facade import (
    read_json as read_json,
)
from etlantic.lifecycle import PipelineRuntime as PipelineRuntime
from etlantic.orchestration import compile_plan as compile_plan
from etlantic.pipeline import Extract as Extract
from etlantic.pipeline import Load as Load
from etlantic.pipeline import Pipeline as Pipeline
from etlantic.plan import AdaptivePipelinePlan as AdaptivePipelinePlan
from etlantic.plan import PipelinePlan as PipelinePlan
from etlantic.plan import explain_plan as explain_plan
from etlantic.plan import plan_pipeline as plan_pipeline
from etlantic.ports import Input as Input
from etlantic.ports import Output as Output
from etlantic.ports import Parameter as Parameter
from etlantic.profile import PlacementTarget as PlacementTarget
from etlantic.profile import Profile as Profile
from etlantic.reports import PipelineRunReport as PipelineRunReport
from etlantic.secrets import SecretRef as SecretRef
from etlantic.transformation import Transformation as Transformation

__version__: str

def __getattr__(name: str) -> Any: ...
def __dir__() -> list[str]: ...

__all__: list[str]
