"""Validate, plan, and run the production-shaped pilot."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from etlantic import PipelineRuntime
from etlantic.profile import load_profile
from etlantic.registry import PlanningContext
from etlantic_polars import create_plugin

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline import PilotPipeline  # noqa: E402


def main() -> None:
    os.chdir(_ROOT)
    profile = load_profile(_ROOT / "profiles" / "prod.json")
    runtime = PipelineRuntime()
    runtime.register_dataframe_plugin("polars", create_plugin())
    context = PlanningContext.create(profile=profile, registry=runtime.registry)

    validation = PilotPipeline.validate(profile=profile, context=context)
    validation.raise_for_errors()
    print("validation: passed")

    plan = PilotPipeline.plan(profile=profile, context=context)
    print(f"plan: {plan.plan_id}")

    run = PilotPipeline.run(profile=profile, runtime=runtime, context=context)
    print(f"run: {run.status.value}")


if __name__ == "__main__":
    main()
