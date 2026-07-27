"""Deterministic microbenchmarks for modeling, discovery, and planning."""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etlantic import PipelineRuntime  # noqa: E402
from etlantic.registry import PlanningContext  # noqa: E402
from tests.fixtures.sample_pipeline import SamplePipeline  # noqa: E402


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    name: str
    seconds: float
    iterations: int


def _median_seconds(fn, *, iterations: int = 5) -> float:
    samples = []
    for _ in range(iterations):
        started = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - started)
    samples.sort()
    return samples[len(samples) // 2]


def bench_plan_small(*, iterations: int = 5) -> ScenarioResult:
    runtime = PipelineRuntime()
    context = PlanningContext.create(profile="development", registry=runtime.registry)

    def _once() -> None:
        SamplePipeline.plan(profile="development", context=context)

    seconds = _median_seconds(_once, iterations=iterations)
    return ScenarioResult("modeling.plan_small", seconds, iterations)


def bench_validate_small(*, iterations: int = 5) -> ScenarioResult:
    def _once() -> None:
        SamplePipeline.validate(profile="development")

    seconds = _median_seconds(_once, iterations=iterations)
    return ScenarioResult("modeling.validate_small", seconds, iterations)


def run_all() -> dict[str, float]:
    return {
        bench_plan_small().name: bench_plan_small().seconds,
        bench_validate_small().name: bench_validate_small().seconds,
    }


if __name__ == "__main__":
    payload = run_all()
    print(json.dumps(payload, indent=2, sort_keys=True))
