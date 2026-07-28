#!/usr/bin/env python3
"""CI gate: Plugin SDK /1 freeze record matches surface inventory."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "src" / "etlantic" / "schemas" / "surface-inventory.json"
PROTOCOL_DOC = ROOT / "docs" / "07_PLUGIN_SDK" / "PROTOCOL_EVOLUTION.md"
FEEDBACK_DOC = ROOT / "docs" / "11_DEVELOPMENT" / "EXTERNAL_PLUGIN_FEEDBACK.md"

# Shipped /1 families on the 1.0 path — must be stable once frozen.
CORE_FROZEN_PROTOCOLS = (
    "etlantic.dataframe/1",
    "etlantic.sql/1",
    "etlantic.spark/1",
    "etlantic.orchestration/1",
    "etlantic.transform-compiler/1",
)

# Not on the 1.0 freeze path (may remain provisional post-freeze).
PROVISIONAL_ALLOWED = frozenset({"etlantic.scheduler/1"})


def main() -> int:
    payload = json.loads(INVENTORY.read_text(encoding="utf-8"))
    protocols: dict[str, str] = payload.get("protocols", {})
    errors: list[str] = []

    for protocol_id in CORE_FROZEN_PROTOCOLS:
        status = protocols.get(protocol_id)
        if status != "stable":
            errors.append(
                f"{protocol_id} must be stable after /1 freeze (got {status!r})"
            )

    for protocol_id, status in protocols.items():
        if status == "provisional" and protocol_id not in PROVISIONAL_ALLOWED:
            errors.append(
                f"unexpected provisional protocol on freeze path: {protocol_id}"
            )

    doc = PROTOCOL_DOC.read_text(encoding="utf-8")
    if "**frozen in 0.28.0**" not in doc and "frozen in 0.28.0" not in doc:
        errors.append(
            f"{PROTOCOL_DOC.relative_to(ROOT)} missing frozen-in-0.28.0 marker"
        )

    if not FEEDBACK_DOC.is_file():
        errors.append(f"missing external feedback record: {FEEDBACK_DOC.name}")
    else:
        feedback = FEEDBACK_DOC.read_text(encoding="utf-8")
        if "etlantic-plugin-echo" not in feedback:
            errors.append(
                f"{FEEDBACK_DOC.relative_to(ROOT)} must document etlantic-plugin-echo"
            )

    if errors:
        print("Protocol freeze gate FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(
        "Protocol freeze gate passed "
        f"({len(CORE_FROZEN_PROTOCOLS)} core /1 families stable)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
