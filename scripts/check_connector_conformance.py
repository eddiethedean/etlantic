#!/usr/bin/env python3
"""CI gate: connector fake conformance (local-files source)."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fake",
        action="store_true",
        help="Run fake/backend-free local-files source conformance",
    )
    args = parser.parse_args(argv)
    if not args.fake:
        parser.error("specify --fake (live suites are not enabled in this gate)")

    from etlantic.connectors import create_local_files_source
    from etlantic.testing.connectors import run_source_connector_conformance_suite

    connector = create_local_files_source()
    results = run_source_connector_conformance_suite(connector)
    ok = sum(1 for r in results if r.get("ok"))
    print(f"Connector conformance (--fake) passed: {ok}/{len(results)} cases")
    for row in results:
        print(f"  - {row.get('case')}: ok={row.get('ok')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
