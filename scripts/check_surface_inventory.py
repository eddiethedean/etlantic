#!/usr/bin/env python3
"""Bidirectional drift check for public surface inventory vs etlantic facade."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "src" / "etlantic" / "schemas" / "surface-inventory.json"


def main() -> int:
    sys.path.insert(0, str(ROOT / "src"))
    import etlantic
    from etlantic.agents import PUBLIC_CLI_COMMANDS

    payload = json.loads(INVENTORY.read_text(encoding="utf-8"))
    stable = set(payload.get("sdk_root_stable", []))
    namespaces = set(payload.get("sdk_root_namespaces", []))
    provisional = set(payload.get("sdk_root_provisional", []))
    experimental = set(payload.get("sdk_root_experimental", []))
    documented = stable | provisional | experimental
    exported = set(etlantic.__all__) - {"__version__"}

    missing_from_export = sorted(documented - exported - provisional)
    # Provisional symbols may be inventoried before they appear in __all__.
    # Removed aliases (e.g. DataContractModel) must not be listed as provisional.
    extra_stable_required = sorted(stable - exported)
    if missing_from_export or extra_stable_required:
        print("Surface inventory lists symbols missing from etlantic.__all__:")
        for name in sorted(set(missing_from_export) | set(extra_stable_required)):
            print(f"  - {name}")
        return 1

    # Bidirectional for curated ownership: every root export must be inventoried
    # as stable (namespaces are lazy attributes, not __all__ entries).
    unexpected = sorted(exported - stable)
    if unexpected:
        print("etlantic.__all__ contains symbols not in surface inventory:")
        for name in unexpected:
            print(f"  - {name}")
        return 1

    ownership = payload.get("namespace_ownership") or {}
    cli_stable = list(payload.get("cli_stable") or [])
    if sorted(cli_stable) != sorted(PUBLIC_CLI_COMMANDS):
        missing = sorted(set(PUBLIC_CLI_COMMANDS) - set(cli_stable))
        extra = sorted(set(cli_stable) - set(PUBLIC_CLI_COMMANDS))
        if missing:
            print("surface-inventory cli_stable missing PUBLIC_CLI_COMMANDS:")
            for cmd in missing:
                print(f"  - {cmd}")
        if extra:
            print("surface-inventory cli_stable has undeclared commands:")
            for cmd in extra:
                print(f"  - {cmd}")
        return 1

    protocols: dict[str, str] = payload.get("protocols") or {}
    wire: dict[str, str] = payload.get("wire_schemas") or {}
    foundations: dict[str, str] = payload.get("foundations") or {}
    locked = {
        "etlantic.scheduler/1": ("protocols", protocols, "stable"),
        "etlantic.quality/1": ("wire_schemas", wire, "provisional"),
        "etlantic.testing": ("foundations", foundations, "stable"),
    }
    for key, (section, table, expected) in locked.items():
        got = table.get(key)
        if got != expected:
            print(
                f"surface-inventory {section}[{key!r}] must be {expected!r} "
                f"(got {got!r})"
            )
            return 1

    for ns in sorted(namespaces):
        expected = ownership.get(ns)
        if not expected:
            print(f"Namespace {ns!r} missing from namespace_ownership table.")
            return 1
        module = getattr(etlantic, ns)
        if module.__name__ != expected:
            print(
                f"Namespace {ns!r} resolved to {module.__name__!r}, "
                f"expected {expected!r}."
            )
            return 1

    print(
        f"Surface inventory OK: {len(stable)} stable in __all__ + "
        f"{len(namespaces)} lazy namespaces verified "
        f"({len(exported)} curated exports)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
