"""Artifact provenance for code-first and contract-first models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProvenanceKind(StrEnum):
    """How a logical artifact was obtained."""

    PYTHON = "python"
    ODCS = "odcs"
    DTCS = "dtcs"
    DPCS = "dpcs"


@dataclass(frozen=True, slots=True)
class ArtifactProvenance:
    """Origin metadata for a loaded or generated artifact."""

    kind: ProvenanceKind
    path: str | None = None
    identity: str | None = None
    version: str | None = None
