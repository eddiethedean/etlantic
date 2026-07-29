"""Delta storage capability extras (domain-neutral; no Delta dependency).

Maintenance and time-travel operations are **not** generic writes. Plugins
advertise them as ``storage.delta.*`` extras under the ``spark_delta`` family.
"""

from __future__ import annotations

from enum import StrEnum

# Capability extras engines advertise for Delta Lake storage operations.
STORAGE_DELTA_CAPABILITY_EXTRAS: frozenset[str] = frozenset(
    {
        "storage.delta.merge",
        "storage.delta.optimize",
        "storage.delta.vacuum",
        "storage.delta.history",
        "storage.delta.time_travel",
        "storage.delta.schema_evolution",
    }
)

# Claiming any storage.delta.* extra implies these boolean family flags.
STORAGE_DELTA_EXTRA_IMPLIES: frozenset[str] = frozenset({"spark_delta", "spark"})


class DeltaStorageOp(StrEnum):
    """Declared Delta storage operations (not portable write modes)."""

    MERGE = "merge"
    OPTIMIZE = "optimize"
    VACUUM = "vacuum"
    HISTORY = "history"
    TIME_TRAVEL = "time_travel"
    SCHEMA_EVOLUTION = "schema_evolution"


DELTA_OP_CAPABILITY: dict[str, str] = {
    DeltaStorageOp.MERGE.value: "storage.delta.merge",
    DeltaStorageOp.OPTIMIZE.value: "storage.delta.optimize",
    DeltaStorageOp.VACUUM.value: "storage.delta.vacuum",
    DeltaStorageOp.HISTORY.value: "storage.delta.history",
    DeltaStorageOp.TIME_TRAVEL.value: "storage.delta.time_travel",
    DeltaStorageOp.SCHEMA_EVOLUTION.value: "storage.delta.schema_evolution",
}


def storage_capability_for_delta_op(op: str | DeltaStorageOp) -> str:
    """Return the capability extra required for a Delta storage operation."""
    key = op.value if isinstance(op, DeltaStorageOp) else str(op).strip().lower()
    if key not in DELTA_OP_CAPABILITY:
        raise ValueError(f"Unknown Delta storage operation: {op!r}")
    return DELTA_OP_CAPABILITY[key]
