"""``python -m medallantic`` CLI dispatcher (migration inventory, etc.)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _cmd_migrate_inventory(args: argparse.Namespace) -> int:
    from medallantic.migrate.inventory import scan_project

    report = scan_project(args.path)
    payload = report.to_dict()
    if args.output:
        Path(args.output).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    errors = [
        d
        for d in report.diagnostics
        if getattr(d.severity, "value", str(d.severity)) == "error"
    ]
    return 1 if errors else 0


def _cmd_migrate_generate(args: argparse.Namespace) -> int:
    from medallantic.migrate.generate import generate_from_path

    result = generate_from_path(args.path, require_auto=not args.allow_manual)
    payload = result.to_dict()
    if args.output:
        Path(args.output).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if result.definition is not None else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m medallantic")
    sub = parser.add_subparsers(dest="command", required=True)

    migrate = sub.add_parser("migrate", help="SparkForge migration helpers")
    migrate_sub = migrate.add_subparsers(dest="migrate_command", required=True)

    inv = migrate_sub.add_parser("inventory", help="Scan a project for legacy builders")
    inv.add_argument("path", help="Project root or IR file")
    inv.add_argument("-o", "--output", help="Write JSON report to path")
    inv.set_defaults(func=_cmd_migrate_inventory)

    gen = migrate_sub.add_parser(
        "generate", help="Generate native definition from SparkForge IR JSON"
    )
    gen.add_argument("path", help="Path to SparkForge IR JSON")
    gen.add_argument("-o", "--output", help="Write JSON result to path")
    gen.add_argument(
        "--allow-manual",
        action="store_true",
        help="Allow generation when convertibility is manual",
    )
    gen.set_defaults(func=_cmd_migrate_generate)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
