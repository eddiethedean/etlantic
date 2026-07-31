#!/usr/bin/env python3
"""Ensure every shipped diagnostic code family has a published stability tier."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "etlantic"
TIERS = ROOT / "src" / "etlantic" / "schemas" / "diagnostic-stability-tiers.json"

CODE_RE = re.compile(r'\bcode\s*=\s*["\']([A-Z]{2,}[A-Z0-9]*\d{3})["\']')
LITERAL_RE = re.compile(r'["\']((?:PM|ODCS|DTCS|DPCS)[A-Z0-9]*\d{3})["\']')
FAMILY_RE = re.compile(r"^([A-Z]+)\d+$")

ALLOWED_TIERS = frozenset({"stable", "provisional", "experimental"})


def collect_families() -> set[str]:
    found: set[str] = set()
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in CODE_RE.finditer(text):
            found.add(_family(match.group(1)))
        for match in LITERAL_RE.finditer(text):
            found.add(_family(match.group(1)))
    return {f for f in found if f}


def _family(code: str) -> str:
    match = FAMILY_RE.match(code)
    if match is None:
        return re.sub(r"\d+$", "", code)
    return match.group(1)


def main() -> int:
    if not TIERS.is_file():
        print(f"Missing diagnostic stability tiers inventory: {TIERS}")
        return 1

    payload = json.loads(TIERS.read_text(encoding="utf-8"))
    families: dict[str, str] = payload.get("families") or {}
    classes = set(payload.get("classes") or [])
    errors: list[str] = []

    if classes != ALLOWED_TIERS:
        errors.append(
            f"classes must be exactly {sorted(ALLOWED_TIERS)} (got {sorted(classes)})"
        )

    for family, tier in sorted(families.items()):
        if tier not in ALLOWED_TIERS:
            errors.append(f"{family}: unknown tier {tier!r}")

    shipped = collect_families()
    missing = sorted(shipped - set(families))
    if missing:
        errors.append(
            "shipped code families missing from diagnostic-stability-tiers.json:"
        )
        errors.extend(f"  - {name}" for name in missing)

    if errors:
        print("Diagnostic stability gate FAILED:")
        for err in errors:
            print(f"  - {err}" if not err.startswith("  - ") else err)
        return 1

    by_tier: dict[str, int] = {t: 0 for t in sorted(ALLOWED_TIERS)}
    for tier in families.values():
        by_tier[tier] = by_tier.get(tier, 0) + 1
    summary = ", ".join(f"{tier}={count}" for tier, count in by_tier.items())
    print(
        f"Diagnostic stability OK: {len(shipped)} shipped families tiered "
        f"({summary}; inventory={len(families)})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
