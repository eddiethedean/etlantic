"""Typed stub for the curated ``import etlantic as etl`` facade (0.22).

Lazy namespaces (``etl.sql``, ``etl.testing``, …) resolve to the real
subpackages on the filesystem; they are intentionally omitted here so
static analyzers do not shadow ``etlantic.<ns>`` modules.
"""

from __future__ import annotations

from typing import Any

from etlantic.contracts import Data as Data
from etlantic.diagnostics import ValidationReport as ValidationReport
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
