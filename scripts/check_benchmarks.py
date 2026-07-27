#!/usr/bin/env python3
"""Compare stable microbenchmarks against committed baselines (0.23)."""

from __future__ import annotations

import importlib.util
import json
import os
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "benchmarks" / "baselines" / "core.json"

BENCH_MODULES = (
    ROOT / "benchmarks" / "modeling" / "microbench.py",
    ROOT / "benchmarks" / "discovery" / "microbench.py",
    ROOT / "benchmarks" / "interchange" / "microbench.py",
)


def _load_run_all(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load benchmark module {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    sys.path.insert(0, str(ROOT))
    spec.loader.exec_module(module)
    return module.run_all


def _collect_results() -> dict[str, float]:
    merged: dict[str, float] = {}
    for path in BENCH_MODULES:
        merged.update(_load_run_all(path)())
    return merged


def _compare(
    observed: dict[str, float], baseline: dict[str, object]
) -> list[str]:
    errors: list[str] = []
    scenarios = baseline.get("scenarios") or {}
    if not isinstance(scenarios, dict):
        return ["baseline scenarios must be an object"]
    for name, spec in scenarios.items():
        if not isinstance(spec, dict):
            errors.append(f"{name}: invalid scenario spec")
            continue
        if name not in observed:
            errors.append(f"missing benchmark result for {name!r}")
            continue
        limit = float(spec.get("p95_seconds") or spec.get("median_seconds") or 0)
        tolerance = float(spec.get("tolerance_ratio") or 0.15)
        ceiling = limit * (1.0 + tolerance)
        if observed[name] > ceiling:
            errors.append(
                f"{name}: observed {observed[name]:.6f}s exceeds ceiling "
                f"{ceiling:.6f}s (baseline p95={limit}, tolerance={tolerance})"
            )
    return errors


def main() -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    observed = _collect_results()
    if os.environ.get("ETLANTIC_BENCHMARK_UPDATE") == "1":
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        scenarios = baseline.setdefault("scenarios", {})
        for name, seconds in sorted(observed.items()):
            entry = scenarios.setdefault(name, {})
            if isinstance(entry, dict):
                entry["median_seconds"] = seconds
                entry["p95_seconds"] = max(seconds * 1.5, seconds + 1e-5)
                entry.setdefault("tolerance_ratio", 0.15)
        baseline["env_fingerprint"] = {
            "python": platform.python_version(),
            "platform": platform.platform(),
        }
        BASELINE_PATH.write_text(
            json.dumps(baseline, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Updated baseline at {BASELINE_PATH}")
        return 0

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    if baseline.get("schema") != "etlantic.benchmark_baseline/1":
        print("Unexpected baseline schema", file=sys.stderr)
        return 1

    errors = _compare(observed, baseline)
    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        print(
            "Benchmark regression detected. Refresh baselines with reviewed "
            "ETLANTIC_BENCHMARK_UPDATE=1 if intentional.",
            file=sys.stderr,
        )
        return 1

    print("Benchmark gate passed:", ", ".join(f"{k}={v:.6f}s" for k, v in observed.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
