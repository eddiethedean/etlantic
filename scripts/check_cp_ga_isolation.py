#!/usr/bin/env python3
"""CI/local gate: CP-GA isolation campaign (043-I)."""

from __future__ import annotations

from _cp_ga_check_lib import run_campaign_check


def main(argv: list[str] | None = None) -> int:
    from etlantic.testing.cp_ga_campaigns import run_isolation_campaign

    return run_campaign_check(
        campaign=run_isolation_campaign,
        matrix_filename="cp_ga_isolation_matrix_0_43.json",
        argv=argv,
    )


if __name__ == "__main__":
    raise SystemExit(main())
