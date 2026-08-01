#!/usr/bin/env python3
"""CI/local gate: DurableWorkStore conformance (memory + optional SQLModel)."""

from __future__ import annotations

import argparse
import json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fake",
        action="store_true",
        help="Run against MemoryDurableWorkStore (default).",
    )
    parser.add_argument(
        "--sqlmodel",
        action="store_true",
        help="Also run against SQLModelDurableWorkStore on SQLite.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON results.")
    args = parser.parse_args(argv)

    from etlantic.control_plane import MemoryDurableWorkStore
    from etlantic.testing import run_durable_work_conformance_suite

    results: list[dict[str, object]] = []
    try:
        run_durable_work_conformance_suite(MemoryDurableWorkStore())
        results.append({"provider": "memory", "status": "pass"})
    except Exception as exc:
        results.append({"provider": "memory", "status": "fail", "error": str(exc)})

    if args.sqlmodel:
        try:
            from etlantic_sqlmodel.control_plane import (
                SQLModelDurableWorkStore,
                create_sqlite_engine,
            )
            from etlantic_sqlmodel.migrations import apply_migrations

            engine = create_sqlite_engine("sqlite://")
            apply_migrations(engine)
            run_durable_work_conformance_suite(SQLModelDurableWorkStore(engine))
            results.append({"provider": "sqlmodel", "status": "pass"})
        except Exception as exc:
            results.append(
                {"provider": "sqlmodel", "status": "fail", "error": str(exc)}
            )

    failed = [r for r in results if r["status"] != "pass"]
    if args.json:
        print(json.dumps({"results": results}, indent=2))
    else:
        for row in results:
            print(f"{row['provider']}: {row['status']}")
            if "error" in row:
                print(f"  error: {row['error']}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
