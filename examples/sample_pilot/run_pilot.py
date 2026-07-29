"""Validate (SARIF), plan, and run the production-shaped pilot."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from etlantic.profile import load_profile

from pipeline import PilotPipeline  # noqa: E402


def main() -> None:
    os.chdir(_ROOT)
    profile = load_profile(_ROOT / "profiles" / "prod.json")
    report = PilotPipeline.validate(profile=profile)
    report.raise_for_errors()
    PilotPipeline.plan(profile=profile)
    run = PilotPipeline.run(profile=profile)
    print(run.status.value)


if __name__ == "__main__":
    main()
