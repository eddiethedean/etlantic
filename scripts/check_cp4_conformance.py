#!/usr/bin/env python3
"""CI/local gate: CP4 policy + governance conformance."""

from __future__ import annotations

import argparse
import json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fake", action="store_true", help="Run memory providers.")
    parser.add_argument("--json", action="store_true", help="Emit JSON results.")
    args = parser.parse_args(argv)
    if not args.fake:
        args.fake = True

    from etlantic.testing import (
        run_cp4_governance_conformance_suite,
        run_policy_conformance_suite,
    )

    results: list[dict[str, object]] = []
    try:
        run_policy_conformance_suite()
        results.append({"suite": "policy", "status": "pass"})
    except Exception as exc:
        results.append({"suite": "policy", "status": "fail", "error": str(exc)})
    try:
        run_cp4_governance_conformance_suite()
        results.append({"suite": "governance", "status": "pass"})
    except Exception as exc:
        results.append({"suite": "governance", "status": "fail", "error": str(exc)})

    failed = any(r["status"] != "pass" for r in results)
    if args.json:
        print(json.dumps({"results": results}, indent=2))
    else:
        for row in results:
            print(f"{row['suite']}: {row['status']}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
