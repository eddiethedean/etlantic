#!/usr/bin/env python3
"""CI gate: etlantic.pipeline/1 burn-in fixtures must stay loadable.

Fails when golden 0.24 fixtures drift (fingerprint mismatch) or cannot be
verified by the current codec — without an updated fixture or migration helper.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "burn_in" / "pipeline" / "v0_24"
MANIFEST = FIXTURE_DIR / "manifest.json"


def main() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from etlantic.authoring import PIPELINE_SCHEMA, pipeline_from_dict, pipeline_to_dict
    from etlantic.authoring.definition import PIPELINE_SCHEMA as SCHEMA

    if SCHEMA != "etlantic.pipeline/1":
        raise SystemExit(
            f"Unexpected PIPELINE_SCHEMA {SCHEMA!r}; wire-schema reset is out of "
            "scope for 0.25 burn-in"
        )

    paths = sorted(FIXTURE_DIR.glob("*.json"))
    paths = [p for p in paths if p.name != "manifest.json"]
    if not paths:
        raise SystemExit(f"No pipeline burn-in fixtures under {FIXTURE_DIR}")

    fingerprints: dict[str, str] = {}
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema") != PIPELINE_SCHEMA:
            raise SystemExit(
                f"{path.name}: expected schema {PIPELINE_SCHEMA!r}, "
                f"got {data.get('schema')!r}"
            )
        loaded = pipeline_from_dict(data, verify=True)
        rewritten = pipeline_to_dict(loaded, with_fingerprint=True)
        if rewritten["fingerprint"] != data["fingerprint"]:
            raise SystemExit(
                f"{path.name}: fingerprint drift "
                f"{data['fingerprint']!r} → {rewritten['fingerprint']!r}. "
                "Update the golden fixture and Migration 0.24→0.25 if this is "
                "an intentional codec change (no silent field drops)."
            )
        fingerprints[path.name] = data["fingerprint"]
        print(f"ok {path.name} {data['fingerprint'][:16]}…")

    if MANIFEST.exists():
        expected = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if expected.get("schema") != PIPELINE_SCHEMA:
            raise SystemExit("manifest.json schema mismatch")
        if expected.get("fingerprints") != fingerprints:
            raise SystemExit(
                "manifest.json fingerprints drifted from fixtures:\n"
                f"  expected={expected.get('fingerprints')}\n"
                f"  actual={fingerprints}\n"
                "Update tests/fixtures/burn_in/pipeline/v0_24/manifest.json "
                "together with fixtures and document the change."
            )
    else:
        MANIFEST.write_text(
            json.dumps(
                {"schema": PIPELINE_SCHEMA, "fingerprints": fingerprints},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"wrote {MANIFEST.relative_to(ROOT)}")

    print(f"Pipeline codec burn-in gate passed ({len(fingerprints)} fixtures).")


if __name__ == "__main__":
    main()
