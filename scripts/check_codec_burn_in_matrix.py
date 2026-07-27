#!/usr/bin/env python3
"""CI gate: sibling burn-in fixtures stay loadable with locked content hashes.

Covers plan, run_report, profile, capabilities, and interchange goldens under
``tests/fixtures/burn_in/*/v0_24/`` (pipeline fixtures remain under
``check_pipeline_codec_burn_in.py``).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BURN_IN = ROOT / "tests" / "fixtures" / "burn_in"
MANIFEST = BURN_IN / "sibling_manifest.json"

SIBLINGS: tuple[tuple[str, str], ...] = (
    ("plan", "etlantic.plan/1"),
    ("run_report", "etlantic.run_report/1"),
    ("profile", None),
    ("capabilities", None),
    ("interchange", "etlantic.interchange/1"),
)


def _content_hash(data: dict) -> str:
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def main() -> None:
    sys.path.insert(0, str(ROOT / "src"))

    from etlantic.capabilities import PluginCapabilities
    from etlantic.interchange.tabular.descriptor import InterchangeDescriptor
    from etlantic.interchange.tabular.select import select_mechanism
    from etlantic.plan.model import PipelinePlan
    from etlantic.profile import Profile
    from etlantic.reports.model import PipelineRunReport

    digests: dict[str, str] = {}
    for family, expected_schema in SIBLINGS:
        directory = BURN_IN / family / "v0_24"
        paths = sorted(p for p in directory.glob("*.json") if p.name != "manifest.json")
        if not paths:
            raise SystemExit(f"No {family} burn-in fixtures under {directory}")
        for path in paths:
            data = json.loads(path.read_text(encoding="utf-8"))
            key = f"{family}/{path.name}"
            if expected_schema is not None and data.get("schema") != expected_schema:
                raise SystemExit(
                    f"{key}: expected schema {expected_schema!r}, "
                    f"got {data.get('schema')!r}"
                )
            if family == "plan":
                plan = PipelinePlan.from_dict(data)
                if plan.to_dict()["fingerprint"] != data.get("fingerprint"):
                    raise SystemExit(f"{key}: plan fingerprint drift on rewrite")
            elif family == "run_report":
                report = PipelineRunReport.from_dict(data)
                if report.run_id != data.get("run_id"):
                    raise SystemExit(f"{key}: run_report identity drift")
            elif family == "profile":
                profile = Profile.from_dict(data)
                if profile.name != data.get("name"):
                    raise SystemExit(f"{key}: profile name drift")
            elif family == "capabilities":
                caps = PluginCapabilities.from_dict(data)
                if caps.engine != data.get("engine"):
                    raise SystemExit(f"{key}: capabilities engine drift")
            elif family == "interchange":
                desc = InterchangeDescriptor.from_dict(data)
                if desc.mechanism.value != data["mechanism"]:
                    raise SystemExit(f"{key}: interchange mechanism drift")
                selected, _ = select_mechanism(
                    set(data["producer_caps"]),
                    set(data["consumer_caps"]),
                    durable=False,
                    already_collecting=True,
                    pyarrow_available=True,
                )
                if selected.value != data["mechanism"]:
                    raise SystemExit(
                        f"{key}: select_mechanism={selected.value!r} "
                        f"!= fixture mechanism={data['mechanism']!r}"
                    )
            digests[key] = _content_hash(data)
            print(f"ok {key} {digests[key][7:23]}…")

    if MANIFEST.exists():
        expected = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if expected.get("digests") != digests:
            raise SystemExit(
                "sibling_manifest.json digests drifted from fixtures:\n"
                f"  expected={expected.get('digests')}\n"
                f"  actual={digests}\n"
                "Update tests/fixtures/burn_in/sibling_manifest.json together "
                "with fixtures and document the change."
            )
    else:
        MANIFEST.write_text(
            json.dumps({"digests": digests}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {MANIFEST.relative_to(ROOT)}")

    print(f"Sibling codec burn-in gate passed ({len(digests)} fixtures).")


if __name__ == "__main__":
    main()
