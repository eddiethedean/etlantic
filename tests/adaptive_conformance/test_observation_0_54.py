# pyright: reportMissingParameterType=false, reportUnknownParameterType=false
"""Observation status handling must not retain provider or failure payloads."""

from types import SimpleNamespace

import pytest
from scripts.check_adaptive_0_54 import Outcomes


@pytest.mark.parametrize("outcome", ["failed", "skipped", "xfail", "xpass"])
def test_nonpassing_phase_never_qualifies(outcome):
    plugin = Outcomes()
    plugin.collected = ["tests/frozen.py::test_case[nullable-duplicate]"]
    for phase in ("setup", "call", "teardown"):
        report = SimpleNamespace(
            nodeid=plugin.collected[0],
            when=phase,
            outcome=outcome if phase == "call" else "passed",
            passed=outcome == "xpass",
            longrepr="row-secret-canary",
        )
        if outcome in {"xfail", "xpass"} and phase == "call":
            report.wasxfail = "provider-secret"
        plugin.pytest_runtest_logreport(report)
    assert plugin.records() == [{"id": plugin.collected[0], "status": "not-passed"}]
    assert "secret" not in repr(plugin.results)


def test_full_parameter_identity_and_three_phases_required():
    plugin = Outcomes()
    plugin.collected = ["tests/frozen.py::test_case[nullable-duplicate]"]
    for phase in ("setup", "call"):
        plugin.pytest_runtest_logreport(
            SimpleNamespace(nodeid=plugin.collected[0], when=phase, outcome="passed")
        )
    assert plugin.records()[0]["status"] == "not-passed"
    plugin.pytest_runtest_logreport(
        SimpleNamespace(nodeid=plugin.collected[0], when="teardown", outcome="passed")
    )
    assert plugin.records() == [{"id": plugin.collected[0], "status": "pass"}]


def test_collection_failure_is_retained_without_exception():
    plugin = Outcomes()
    plugin.pytest_collectreport(SimpleNamespace(failed=True, longrepr="secret"))
    assert plugin.collection_failed
    assert plugin.records() == []
