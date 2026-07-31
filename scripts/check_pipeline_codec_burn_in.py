#!/usr/bin/env python3
"""CI gate: etlantic.pipeline/1 burn-in fixtures must stay loadable.

Fails when golden fixtures drift (fingerprint mismatch) or cannot be verified
by the current codec — without an updated fixture or migration helper.

Checks ``v0_24``-``v0_27`` (0.24→…→0.28 proof) and ``v0_34``-``v0_37``
(joint compatibility burn-in through stable foundation).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BURN_IN = ROOT / "tests" / "fixtures" / "burn_in" / "pipeline"
VERSIONS = (
    "v0_24",
    "v0_25",
    "v0_26",
    "v0_27",
    "v0_34",
    "v0_35",
    "v0_36",
    "v0_37",
)


def _check_version(version: str) -> dict[str, str]:
    sys.path.insert(0, str(ROOT / "src"))
    from etlantic.authoring import PIPELINE_SCHEMA, pipeline_from_dict, pipeline_to_dict
    from etlantic.authoring.definition import PIPELINE_SCHEMA as SCHEMA

    if SCHEMA != "etlantic.pipeline/1":
        raise SystemExit(
            f"Unexpected PIPELINE_SCHEMA {SCHEMA!r}; wire-schema reset is out of "
            "scope for burn-in"
        )

    fixture_dir = BURN_IN / version
    manifest = fixture_dir / "manifest.json"
    paths = sorted(fixture_dir.glob("*.json"))
    paths = [p for p in paths if p.name != "manifest.json"]
    if not paths:
        raise SystemExit(f"No pipeline burn-in fixtures under {fixture_dir}")

    fingerprints: dict[str, str] = {}
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema") != PIPELINE_SCHEMA:
            raise SystemExit(
                f"{version}/{path.name}: expected schema {PIPELINE_SCHEMA!r}, "
                f"got {data.get('schema')!r}"
            )
        loaded = pipeline_from_dict(data, verify=True)
        rewritten = pipeline_to_dict(loaded, with_fingerprint=True)
        if rewritten["fingerprint"] != data["fingerprint"]:
            raise SystemExit(
                f"{version}/{path.name}: fingerprint drift "
                f"{data['fingerprint']!r} → {rewritten['fingerprint']!r}. "
                "Update the golden fixture and Migration notes if this is "
                "an intentional codec change (no silent field drops)."
            )
        fingerprints[path.name] = data["fingerprint"]
        print(f"ok {version}/{path.name} {data['fingerprint'][:16]}…")

    if manifest.exists():
        expected = json.loads(manifest.read_text(encoding="utf-8"))
        if expected.get("schema") != PIPELINE_SCHEMA:
            raise SystemExit(f"{version}/manifest.json schema mismatch")
        if expected.get("fingerprints") != fingerprints:
            raise SystemExit(
                f"{version}/manifest.json fingerprints drifted from fixtures:\n"
                f"  expected={expected.get('fingerprints')}\n"
                f"  actual={fingerprints}\n"
                f"Update tests/fixtures/burn_in/pipeline/{version}/manifest.json "
                "together with fixtures and document the change."
            )
    else:
        manifest.write_text(
            json.dumps(
                {"schema": PIPELINE_SCHEMA, "fingerprints": fingerprints},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"wrote {manifest.relative_to(ROOT)}")

    return fingerprints


def main() -> None:
    total = 0
    for version in VERSIONS:
        fps = _check_version(version)
        total += len(fps)
    print(
        f"Pipeline codec burn-in gate passed ({total} fixtures across {len(VERSIONS)} versions)."
    )


if __name__ == "__main__":
    raise SystemExit(main())
