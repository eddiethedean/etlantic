"""CLI schedule / scheduler / worker commands."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from etlantic.cli import app

runner = CliRunner()


def test_schedule_create_list_inspect(tmp_path: Path) -> None:
    store = tmp_path / "schedules.json"
    durable = tmp_path / "schedules.durable.json"
    created = runner.invoke(
        app,
        [
            "schedule",
            "create",
            "--store",
            str(store),
            "--definition-id",
            "pipe-1",
            "--interval",
            "60",
        ],
    )
    assert created.exit_code == 0, created.output
    payload = json.loads(created.output)
    schedule_id = payload["schedule_id"]
    listed = runner.invoke(app, ["schedule", "list", "--store", str(store)])
    assert listed.exit_code == 0
    inspect = runner.invoke(
        app, ["schedule", "inspect", schedule_id, "--store", str(store)]
    )
    assert inspect.exit_code == 0
    preview = runner.invoke(
        app, ["schedule", "preview", schedule_id, "--store", str(store)]
    )
    assert preview.exit_code == 0
    state = json.loads(store.read_text(encoding="utf-8"))
    for rec in state.get("schedules", {}).values():
        rec["next_fire_at"] = "2020-01-01T00:00:00Z"
    store.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    serve = runner.invoke(
        app,
        [
            "scheduler",
            "serve",
            "--store",
            str(store),
            "--durable-store",
            str(durable),
            "--once",
        ],
    )
    assert serve.exit_code == 0
    worker = runner.invoke(
        app,
        ["worker", "serve", "--durable-store", str(durable), "--once"],
    )
    assert worker.exit_code == 0
    worker_payload = json.loads(worker.output)
    assert worker_payload["processed"] == 1
