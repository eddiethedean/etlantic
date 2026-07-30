"""Regression tests for the next-20 0.34 fail-closed hardening pass."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from etlantic.cli import exit_codes as ec
from etlantic.exceptions import PipelineExecutionError
from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.orchestration.protocol import ScheduleIntent
from etlantic.profile import Profile, production_profile
from etlantic.reports.model import PipelineRunReport
from etlantic.runtime.incremental import FileStateStore
from etlantic.runtime.logging import redact_message, redact_value
from etlantic.storage.memory import MemoryStorage


def test_normalize_assets_map_rejects_userinfo() -> None:
    from etlantic.bindings import normalize_assets_map, parse_asset_descriptor

    with pytest.raises(ValueError, match="userinfo"):
        normalize_assets_map({"db": "postgresql://admin:hunter2@db.example/app"})
    with pytest.raises(ValueError, match="userinfo"):
        parse_asset_descriptor(
            {"provider": "postgresql", "location": "admin:hunter2@db.example/app"}
        )
    with pytest.raises(ValueError, match="userinfo"):
        Profile(
            name="dev",
            assets={"db": "postgresql://admin:hunter2@db.example/app"},
        )


def test_profile_snapshot_rejects_credential_assets() -> None:
    with pytest.raises(ValueError, match="userinfo"):
        Profile(
            name="dev",
            assets={"leak": "postgres://u:p@host/db"},
        ).to_plan_snapshot()


def test_binding_descriptor_rejects_userinfo_location() -> None:
    from etlantic.registry import BindingDescriptor

    with pytest.raises(ValueError, match="userinfo"):
        BindingDescriptor.from_dict(
            {
                "binding": "db",
                "provider": "postgresql",
                "location": "postgresql://u:secret@host/db",
            }
        )


def test_extension_rejects_dsn_key_and_url_value() -> None:
    from etlantic.extensions import validate_extension_metadata

    with pytest.raises(ValueError, match="secret-like key"):
        validate_extension_metadata({"dsn": "postgres://u:p@h/db"})
    with pytest.raises(ValueError, match="secret-like key"):
        validate_extension_metadata({"db_password": "x"})
    with pytest.raises(ValueError, match="userinfo"):
        validate_extension_metadata({"endpoint": "https://u:p@api.example/v1"})


def test_report_nested_metadata_rejects_secrets() -> None:
    base = {
        "schema": "etlantic.run_report/1",
        "pipeline_id": "p",
        "plan_id": "plan",
        "run_id": "run",
        "intent": "standard",
        "profile": "dev",
        "status": "succeeded",
        "started_at": datetime.now(UTC).isoformat(),
        "summary": {},
        "metadata": {},
    }
    with pytest.raises(ValueError, match="secret-like key"):
        PipelineRunReport.from_dict(
            {
                **base,
                "artifacts": [
                    {
                        "identity": "a",
                        "logical_output": "o",
                        "strategy": "external",
                        "status": "available",
                        "metadata": {"password": "x"},
                    }
                ],
            }
        )


def test_register_storage_gated_under_production() -> None:
    runtime = PipelineRuntime()
    profile = production_profile(plugin_allowlist={"etlantic-polars": "==0.35.0"})
    runtime.ensure_plugins_for_profile(profile)
    with pytest.raises(PipelineExecutionError) as exc:
        runtime.register_storage("evil-store", MemoryStorage())
    assert exc.value.code in {"PMPLUG402", "PMPLUG401"}


def test_schedule_intent_missing_timezone_unset() -> None:
    intent = ScheduleIntent.from_mapping({"type": "cron", "expression": "0 * * * *"})
    assert intent.timezone is None
    empty = ScheduleIntent.from_mapping({})
    assert empty.timezone is None


def test_memory_merge_fails_closed() -> None:
    store = MemoryStorage()

    async def _run() -> None:
        with pytest.raises(PipelineExecutionError) as exc:
            await store.write(
                binding="t",
                location=None,
                data=[{"id": 1}],
                contract_type=None,
                context={"write_mode": "merge"},
            )
        assert exc.value.code == "PMEXEC456"

    import asyncio

    asyncio.run(_run())


def test_csv_write_modes(tmp_path: Path) -> None:
    import asyncio

    from etlantic.storage.csv_binding import CsvStorage

    async def _run() -> None:
        store = CsvStorage()
        path = tmp_path / "out.csv"
        await store.write(
            binding="t",
            location=str(path),
            data=[{"id": 1, "name": "a"}],
            contract_type=None,
            context={"write_mode": "overwrite"},
        )
        await store.write(
            binding="t",
            location=str(path),
            data=[{"id": 2, "name": "b"}],
            contract_type=None,
            context={"write_mode": "append"},
        )
        text = path.read_text(encoding="utf-8")
        assert "a" in text and "b" in text
        with pytest.raises(PipelineExecutionError) as exc:
            await store.write(
                binding="t",
                location=str(path),
                data=[{"id": 3}],
                contract_type=None,
                context={"write_mode": "upsert"},
            )
        assert exc.value.code == "PMEXEC455"

    asyncio.run(_run())


def test_file_state_store_commit_reads_previous_inside_rmw(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    store = FileStateStore(path)
    first = store.commit("s1", "v1")
    assert first.from_status == ""
    second = store.commit("s1", "v2")
    assert second.from_status == "v1"
    assert second.to_status == "v2"


def test_redact_full_userinfo_and_dsn_keys() -> None:
    msg = redact_message("postgresql://admin:hunter2@db.example/app")
    assert "hunter2" not in msg
    assert "admin:hunter2@" not in msg
    assert "***@" in msg
    assert redact_value({"dsn": "postgres://u:p@h/db"}) == {"dsn": "***"}
    assert redact_value({"connection_string": "x"}) == {"connection_string": "***"}


def test_pmexec353_is_security_hard_failure() -> None:
    from etlantic.runtime.orchestrator import LocalOrchestrator

    err = PipelineExecutionError(
        "trusted sql mismatch", code="PMEXEC353", stage="security"
    )
    assert LocalOrchestrator._is_security_hard_failure(err)


def test_run_maps_raised_pmplug_to_trust_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from typer.testing import CliRunner

    import etlantic.cli.globals as globals_mod
    from etlantic.cli import app
    from etlantic.cli.context import CliContext

    class _BoomPipeline:
        @classmethod
        def run(cls, **_kwargs: object) -> object:
            raise PipelineExecutionError("plugin denied", code="PMPLUG402")

    monkeypatch.setattr(globals_mod, "load_target", lambda target: _BoomPipeline)
    monkeypatch.setattr(
        CliContext,
        "ensure_plugins",
        lambda self, profile, **kwargs: [],
    )
    runner = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb"})
    result = runner.invoke(
        app,
        ["run", "dummy:Boom", "--profile", "development", "--format", "text"],
    )
    assert result.exit_code == ec.TRUST_FAILURE, result.stdout + result.stderr


def test_durable_audit_consumer_fail_closed() -> None:
    from etlantic.runtime.events import EventBus, LifecycleEvent
    from etlantic.runtime.observability_bridge import ObservabilityBridge

    class _BadConsumer:
        def consume(self, event: object) -> None:
            raise RuntimeError("consumer boom password=hunter2")

        def flush(self) -> None:
            return None

    profile = Profile(
        name="prod",
        security_mode="production",
        plugin_allowlist={"etlantic-polars": "==0.35.0"},
        observability_delivery="durable_audit",
    )
    bridge = ObservabilityBridge(events=EventBus())
    bridge.configure_for_profile(profile)
    bridge.event_consumers["bad"] = _BadConsumer()
    with pytest.raises(RuntimeError, match="durable_audit"):
        bridge._on_event(
            LifecycleEvent(kind="run_started", run_id="r1", pipeline_id="p")
        )
    assert bridge._provider_errors
    assert "hunter2" not in bridge._provider_errors[-1]
