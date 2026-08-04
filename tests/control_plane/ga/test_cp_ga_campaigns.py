"""CP-GA qualification campaigns (0.43) — unit entrypoints."""

from __future__ import annotations

from etlantic.testing.cp_ga_campaigns import (
    run_all_campaigns,
    run_capacity_campaign,
    run_compat_campaign,
    run_gitops_campaign,
    run_isolation_campaign,
    run_ops_campaign,
    run_recovery_campaign,
    run_resilience_campaign,
    run_security_campaign,
)


def test_all_cp_ga_campaigns_pass() -> None:
    result = run_all_campaigns()
    assert result["pass"], result["failed"]


def test_compat_campaign() -> None:
    assert run_compat_campaign()["pass"]


def test_isolation_campaign() -> None:
    assert run_isolation_campaign()["pass"]


def test_resilience_campaign() -> None:
    assert run_resilience_campaign()["pass"]


def test_recovery_campaign() -> None:
    assert run_recovery_campaign()["pass"]


def test_capacity_campaign() -> None:
    assert run_capacity_campaign()["pass"]


def test_security_campaign() -> None:
    assert run_security_campaign()["pass"]


def test_ops_campaign() -> None:
    assert run_ops_campaign()["pass"]


def test_gitops_campaign() -> None:
    assert run_gitops_campaign()["pass"]
