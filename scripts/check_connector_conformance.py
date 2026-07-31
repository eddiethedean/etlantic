#!/usr/bin/env python3
"""CI gate: connector fake conformance (local-files + optional cloud fakes)."""

from __future__ import annotations

import argparse
import importlib
import sys


def _print_results(label: str, results: list[dict]) -> int:
    ok = sum(1 for r in results if r.get("ok"))
    failed = [r for r in results if not r.get("ok")]
    print(f"Connector conformance ({label}): {ok}/{len(results)} cases")
    for row in results:
        print(f"  - {row.get('case')}: ok={row.get('ok')}")
    return 1 if failed else 0


def _try_sink_suite(module_path: str, factory_name: str = "create_sink") -> int:
    try:
        mod = importlib.import_module(module_path)
    except ImportError:
        print(f"  skip: {module_path} not importable")
        return 0
    factory = getattr(mod, factory_name, None)
    if factory is None:
        print(f"  skip: {module_path}.{factory_name} missing")
        return 0
    from etlantic.testing.connectors import run_sink_connector_conformance_suite

    results = run_sink_connector_conformance_suite(factory())
    return _print_results(module_path, results)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fake",
        action="store_true",
        help="Run fake/backend-free connector conformance",
    )
    args = parser.parse_args(argv)
    if not args.fake:
        parser.error("specify --fake (live suites are not enabled in this gate)")

    from etlantic.connectors import create_local_files_source
    from etlantic.testing.connectors import run_source_connector_conformance_suite

    exit_code = 0
    source_results = run_source_connector_conformance_suite(create_local_files_source())
    exit_code |= _print_results("local-files source", source_results)

    # Optional importable fake sinks (s3 / iceberg / snowflake / postgresql).
    for module in (
        "etlantic_s3",
        "etlantic_iceberg",
        "etlantic_snowflake",
        "etlantic_sql.connectors",
    ):
        exit_code |= _try_sink_suite(module)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
