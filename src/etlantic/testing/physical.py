"""Conformance smoke checks for the adaptive physical-unit protocol."""

from __future__ import annotations

from typing import Any

import anyio

from etlantic.plan.physical import PhysicalUnit
from etlantic.runtime.physical_protocol import (
    PhysicalUnitContext,
    PhysicalUnitExecutor,
    PhysicalUnitResult,
    validate_unit_result,
)


def run_physical_unit_conformance_smoke(
    executor: PhysicalUnitExecutor,
    unit: PhysicalUnit,
    *,
    plan: Any | None = None,
    run_id: str = "conformance-run",
) -> PhysicalUnitResult:
    """Exercise protocol identity, analysis, execution, and cleanup hooks.

    The helper deliberately passes an empty, data-only context. Plugin suites
    can provide a plan when their analyzer needs one, while process-local
    values remain outside the serialized protocol result.
    """
    info = executor.info
    if unit.kind.value not in info.unit_kinds:
        raise AssertionError(
            f"executor does not advertise unit kind {unit.kind.value!r}"
        )
    support = executor.analyze(plan, unit)
    if not support.supported:
        raise AssertionError(
            "physical executor rejected conformance unit: "
            f"{[finding.code for finding in support.findings]}"
        )
    context = PhysicalUnitContext(
        plan=plan,
        unit=unit,
        run_id=run_id,
        unit_attempt=1,
    )

    async def exercise() -> PhysicalUnitResult:
        result = await executor.execute(context)
        validate_unit_result(result, unit)
        await executor.cancel(context)
        await executor.cleanup(context, result)
        return result

    return anyio.run(exercise)


__all__ = ["run_physical_unit_conformance_smoke"]
