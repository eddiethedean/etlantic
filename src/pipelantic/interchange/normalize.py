"""Normalize code-first and contract-first inputs to comparable graphs."""

from __future__ import annotations

from typing import Any

from pipelantic.interchange.dpcs import graph_fingerprint
from pipelantic.interchange.provenance import ArtifactProvenance, ProvenanceKind
from pipelantic.model import LogicalGraph


def normalize_pipeline(
    pipeline_cls: type[Any],
) -> tuple[LogicalGraph, ArtifactProvenance]:
    """Return the logical graph and provenance for a pipeline class."""
    graph = pipeline_cls.build_graph()
    provenance = getattr(pipeline_cls, "__provenance__", None)
    if not isinstance(provenance, ArtifactProvenance):
        provenance = ArtifactProvenance(
            kind=ProvenanceKind.PYTHON,
            identity=getattr(pipeline_cls, "__published_id__", None),
            version=getattr(pipeline_cls, "__published_version__", None),
        )
    return graph, provenance


def graphs_equivalent(left: LogicalGraph, right: LogicalGraph) -> bool:
    """Return True when two logical graphs match by fingerprint."""
    return graph_fingerprint(left) == graph_fingerprint(right)
