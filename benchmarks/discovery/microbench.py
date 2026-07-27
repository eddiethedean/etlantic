"""Plugin discovery microbenchmark (metadata-only vs runtime groups)."""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etlantic import PipelineRuntime, Profile  # noqa: E402
from etlantic.plugins.coordinator import PluginDiscoveryCoordinator  # noqa: E402


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    name: str
    seconds: float


def _median_seconds(fn, *, iterations: int = 3) -> float:
    samples = []
    for _ in range(iterations):
        started = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - started)
    samples.sort()
    return samples[len(samples) // 2]


def bench_discovery_metadata_only() -> ScenarioResult:
    runtime = PipelineRuntime()
    profile = Profile(name="bench")
    coordinator = PluginDiscoveryCoordinator()

    def _once() -> None:
        coordinator.discover_for_profile(
            profile,
            registry=runtime.registry,
            register_to_registry=False,
            include_runtime_groups=False,
        )

    return ScenarioResult("discovery.disabled", _median_seconds(_once))


def bench_discovery_with_runtime_groups() -> ScenarioResult:
    runtime = PipelineRuntime()
    profile = Profile(name="bench")
    coordinator = PluginDiscoveryCoordinator()

    def _once() -> None:
        coordinator.discover_for_profile(
            profile,
            registry=runtime.registry,
            register_to_registry=False,
            include_runtime_groups=True,
        )

    return ScenarioResult("discovery.enabled", _median_seconds(_once))


def run_all() -> dict[str, float]:
    return {
        bench_discovery_metadata_only().name: bench_discovery_metadata_only().seconds,
        bench_discovery_with_runtime_groups().name: bench_discovery_with_runtime_groups().seconds,
    }


if __name__ == "__main__":
    print(json.dumps(run_all(), indent=2, sort_keys=True))
