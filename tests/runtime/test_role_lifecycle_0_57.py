"""Release acceptance tests for public worker supervision facts."""

from __future__ import annotations

from etlantic.runtime.role import RuntimeRoleLifecycle


def test_role_status_reports_unknown_then_usable_and_redacts_reason() -> None:
    role = RuntimeRoleLifecycle(
        "run_worker", capabilities=("read_status", "cooperative_drain")
    )

    initial = role.status()
    assert initial.role == "run_worker"
    assert initial.activity == "idle"
    assert initial.admission == "accepting"
    assert initial.prerequisites == "unknown"
    assert initial.reason_code == "not_yet_observed"
    assert not initial.ready

    role.observe_prerequisites("usable", reason_code="database password is secret")
    observed = role.status()
    assert observed.prerequisites == "usable"
    assert observed.reason_code == "external_condition"
    assert observed.ready
    assert "secret" not in str(observed.to_dict())


def test_drain_is_idempotent_nonblocking_and_keeps_inflight_work_truthful() -> None:
    role = RuntimeRoleLifecycle("action_worker", capabilities=("read_status",))
    assert role.begin_tick()
    assert role.begin_dispatch()

    draining = role.request_drain()
    assert draining.activity == "active"
    assert draining.admission == "draining"
    assert draining.in_flight == 2
    assert not role.begin_tick()
    assert not role.begin_dispatch()

    repeated = role.request_drain()
    assert repeated.admission == "draining"
    assert repeated.in_flight == 2

    role.end_dispatch()
    assert role.status().in_flight == 1
    role.end_tick()
    stopped = role.status()
    assert stopped.activity == "idle"
    assert stopped.admission == "stopped"
    assert stopped.in_flight == 0


def test_standby_and_concurrent_tick_reservation_are_distinct_from_failure() -> None:
    role = RuntimeRoleLifecycle("scheduler", capabilities=("leader_standby",))
    role.observe_prerequisites("usable")
    role.observe_standby()
    standby = role.status()
    assert standby.activity == "standby"
    assert standby.prerequisites == "usable"
    assert standby.reason_code == "leader_lease_held"

    assert role.begin_tick()
    assert not role.begin_tick()
    assert role.status().in_flight == 1
    role.end_tick()
