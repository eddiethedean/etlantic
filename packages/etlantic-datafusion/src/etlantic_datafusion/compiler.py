"""Experimental DataFusion portable transform compiler (kernel claim set later)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from etlantic.transform.compiler import (
    CompiledTransform,
    TransformCapabilities,
    TransformCompileContext,
    TransformCompilerInfo,
    TransformExecutionContext,
    TransformOutputBundle,
    TransformPlanningContext,
    TransformSupportReport,
)

__version__ = "0.21.0"


class DataFusionTransformCompiler:
    """Experimental compiler — advertise no graduated claims until conformance."""

    info = TransformCompilerInfo(
        name="etlantic-datafusion",
        version=__version__,
        engine="datafusion",
        capabilities=TransformCapabilities(
            profiles=frozenset(),
            actions=frozenset(),
            functions=frozenset(),
            lazy=True,
            eager=False,
        ),
    )

    def analyze(
        self,
        definition: Mapping[str, Any],
        *,
        context: TransformPlanningContext,
        requirements: Mapping[str, Sequence[str]] | None = None,
    ) -> TransformSupportReport:
        raise NotImplementedError(
            "etlantic-datafusion portable compiler is experimental; no claims "
            "experimental as of 0.20.0"
        )

    def compile(
        self,
        definition: Mapping[str, Any],
        *,
        context: TransformCompileContext,
        requirements: Mapping[str, Sequence[str]] | None = None,
    ) -> CompiledTransform:
        raise NotImplementedError(
            "etlantic-datafusion portable compile is experimental/ungraduated"
        )

    async def execute(
        self,
        compiled: CompiledTransform,
        *,
        inputs: Mapping[str, Any],
        parameters: Mapping[str, Any],
        context: TransformExecutionContext,
    ) -> TransformOutputBundle:
        raise NotImplementedError(
            "etlantic-datafusion portable execute is experimental/ungraduated"
        )
