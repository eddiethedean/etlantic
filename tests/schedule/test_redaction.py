"""Schedule JSON must never include payloads, secrets, or source rows."""

from __future__ import annotations

import pytest

from etlantic.control_plane import (
    FIRING_SCHEMA,
    SCHEDULE_SCHEMA,
    FiringRecord,
    ScheduleRecord,
    ScheduleSpec,
    assert_schedule_payload_clean,
)


def test_schedule_to_dict_schema_and_redaction() -> None:
    rec = ScheduleRecord(
        schedule_id="sch-1",
        definition_id="pipe-1",
        revision_id="rev-1",
        tenant_id="t",
        workspace_id="w",
        profile_name="test",
        policy_fingerprint="pol",
        spec=ScheduleSpec(kind="interval", interval_seconds=60),
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        secret_refs={"db": "vault://prod/db"},
        metadata={"note": "ok"},
    )
    payload = rec.to_dict()
    assert payload["schema"] == SCHEDULE_SCHEMA
    assert "payload" not in payload
    assert payload["secret_refs"]["db"] == "vault://prod/db"


def test_forbidden_keys_fail_closed() -> None:
    with pytest.raises(ValueError, match="PMFIRE150"):
        assert_schedule_payload_clean({"payload": {"row": 1}})
    with pytest.raises(ValueError, match="PMFIRE150"):
        FiringRecord(
            firing_id="f1",
            schedule_id="s",
            revision_id="r",
            nominal_fire_time="2026-01-01T00:00:00Z",
            tenant_id="t",
            workspace_id="w",
            created_at="2026-01-01T00:00:00Z",
            metadata={"secret": "hunter2"},
        ).to_dict()
    rec = FiringRecord(
        firing_id="f1",
        schedule_id="s",
        revision_id="r",
        nominal_fire_time="2026-01-01T00:00:00Z",
        tenant_id="t",
        workspace_id="w",
        created_at="2026-01-01T00:00:00Z",
    )
    dumped = rec.to_dict()
    assert dumped["schema"] == FIRING_SCHEMA
    assert dumped["logical_key"] == "s:r:2026-01-01T00:00:00Z"
