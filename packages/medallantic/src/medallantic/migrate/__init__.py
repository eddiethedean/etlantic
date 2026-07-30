"""Migration bridges from legacy builders into Medallantic."""

from __future__ import annotations

from medallantic.migrate import sparkforge as sparkforge
from medallantic.migrate import sql as sql
from medallantic.migrate.generate import (
    GENERATOR_ID,
    GenerationResult,
    generate_from_artifact,
    generate_from_ir,
    generate_from_path,
)
from medallantic.migrate.inventory import (
    InventoryArtifact,
    MigrationInventoryReport,
    scan_project,
)

__all__ = [
    "GENERATOR_ID",
    "GenerationResult",
    "InventoryArtifact",
    "MigrationInventoryReport",
    "generate_from_artifact",
    "generate_from_ir",
    "generate_from_path",
    "scan_project",
    "sparkforge",
    "sql",
]
