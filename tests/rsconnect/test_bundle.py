from __future__ import annotations

import hashlib
import io
import json
import runpy
import subprocess
import sys
import tarfile
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from etlantic_rsconnect import (
    OccurrenceContext,
    build_trigger_bundle,
    build_trigger_envelope,
)
from etlantic_rsconnect.bundle import TriggerBundle

from etlantic.control_plane import ControlPlaneError, TriggerReceipt
from etlantic.outbound import OutboundPolicy
from etlantic.secrets import SecretRef


def _bundle() -> TriggerBundle:
    return build_trigger_bundle(
        schedule_id="schedule-1",
        schedule_revision_id="revision-1",
        timer_owner_generation=2,
        endpoint_url="https://receiver.example.com/base",
        credential_ref=SecretRef("env", "trigger", "token"),
        credential_env="ETLANTIC_TRIGGER_TOKEN",
        outbound_policy=OutboundPolicy(
            allowed_hosts=("receiver.example.com",),
            max_response_bytes=65_536,
        ),
    )


def _contents(bundle: TriggerBundle) -> dict[str, bytes]:
    with tarfile.open(fileobj=io.BytesIO(bundle.archive), mode="r:gz") as archive:
        contents: dict[str, bytes] = {}
        for member in archive.getmembers():
            extracted = archive.extractfile(member)
            if extracted is not None:
                contents[member.name] = extracted.read()
        return contents


def test_bundle_is_reproducible_and_manifest_covers_all_sources(
    tmp_path: Path,
) -> None:
    first = _bundle()
    second = _bundle()

    assert first.archive == second.archive
    assert first.sha256 == second.sha256
    contents = _contents(first)
    manifest = json.loads(contents["etlantic-trigger-manifest.json"])
    assert manifest["schema"] == "etlantic.rsconnect.trigger_bundle/1"
    assert set(manifest["files"]) == set(contents) - {"etlantic-trigger-manifest.json"}
    assert manifest["files"] == {
        name: hashlib.sha256(body).hexdigest()
        for name, body in contents.items()
        if name != "etlantic-trigger-manifest.json"
    }
    assert b"trigger-token-value" not in first.archive

    target = first.write_to(tmp_path / "content")
    assert (target / "etlantic-trigger-manifest.json").is_file()
    assert (target / "requirements.txt").read_text() == (
        "# Standard-library-only trigger content.\n"
    )


def test_bundle_rejects_source_that_no_longer_matches_manifest(tmp_path: Path) -> None:
    bundle = _bundle()
    contents = _contents(bundle)
    contents["index.qmd"] += b"\nmanual edit\n"
    raw = io.BytesIO()
    with (
        tarfile.open(fileobj=raw, mode="w:gz") as archive,
    ):
        for name, body in sorted(contents.items()):
            info = tarfile.TarInfo(name)
            info.size = len(body)
            archive.addfile(info, io.BytesIO(body))
    tampered = replace(
        bundle,
        archive=raw.getvalue(),
        sha256=hashlib.sha256(raw.getvalue()).hexdigest(),
    )

    with pytest.raises(ValueError, match="digest does not match"):
        tampered.write_to(tmp_path / "content")
    assert not (tmp_path / "content").exists()


def test_generated_runner_refuses_unbound_armed_render(tmp_path: Path) -> None:
    target = _bundle().write_to(tmp_path / "content")
    result = subprocess.run(
        [sys.executable, str(target / "etlantic-trigger.py")],
        env={"ETLANTIC_TRIGGER_ARMED": "true"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "no qualified Connect occurrence provider" in result.stderr
    assert "Authorization" not in result.stdout + result.stderr


def test_generated_runner_matches_public_occurrence_and_receipt_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = _bundle().write_to(tmp_path / "content")
    config_path = target / "etlantic-trigger.json"
    config = json.loads(config_path.read_text())
    config["occurrence_context_provider"] = "test-fixture"
    config_path.write_text(json.dumps(config))
    monkeypatch.setenv("ETLANTIC_SCHEDULED_AT", "2026-10-13T12:00:00Z")
    monkeypatch.setenv("ETLANTIC_DELIVERY_ATTEMPT_ID", "attempt-1")
    monkeypatch.setenv("ETLANTIC_CORRELATION_ID", "correlation-1")
    runner = runpy.run_path(str(target / "etlantic-trigger.py"))

    expected = build_trigger_envelope(
        schedule_id="schedule-1",
        schedule_revision_id="revision-1",
        timer_owner_generation=3,
        occurrence=OccurrenceContext(
            scheduled_at="2026-10-13T12:00:00Z",
            delivery_attempt_id="attempt-1",
            correlation_id="correlation-1",
        ),
    ).to_dict()
    monkeypatch.setenv("ETLANTIC_TIMER_OWNER_GENERATION", "3")
    emitted = runner["occurrence"]()
    assert emitted == expected

    monkeypatch.setenv("ETLANTIC_TIMER_OWNER_GENERATION", "0")
    with pytest.raises(RuntimeError, match="timer owner generation is invalid"):
        runner["occurrence"]()

    status_reference = (
        "/v1/schedules/schedule-1/occurrences/" + expected["occurrence_id"]
    )
    accepted = TriggerReceipt(
        status="accepted",
        firing_status="accepted",
        schedule_id="schedule-1",
        schedule_revision_id="revision-1",
        occurrence_id=expected["occurrence_id"],
        submission_id="submission-1",
        status_reference=status_reference,
    )
    pending = TriggerReceipt(
        status="pending",
        firing_status="accepted",
        schedule_id="schedule-1",
        schedule_revision_id="revision-1",
        occurrence_id=expected["occurrence_id"],
        status_reference=status_reference,
    )
    safe_receipt = runner["safe_receipt"]
    assert callable(safe_receipt)
    assert safe_receipt(accepted.to_dict(), emitted, 200)
    assert safe_receipt(pending.to_dict(), emitted, 202)
    assert not safe_receipt(pending.to_dict(), emitted, 200)

    skipped_with_submission = TriggerReceipt(
        status="skipped",
        firing_status="skipped_overlap",
        schedule_id="schedule-1",
        schedule_revision_id="revision-1",
        occurrence_id=expected["occurrence_id"],
        submission_id="submission-1",
        status_reference=status_reference,
    )
    assert safe_receipt(skipped_with_submission.to_dict(), emitted, 200)
    assert safe_receipt(
        replace(accepted, status_reference=None).to_dict(), emitted, 200
    )

    for field, value in (
        ("submission_id", "   "),
        ("run_id", "   "),
        ("status_reference", "   "),
    ):
        malformed = accepted.to_dict()
        malformed[field] = value
        with pytest.raises(ControlPlaneError):
            TriggerReceipt.from_dict(malformed)
        assert not safe_receipt(malformed, emitted, 200)

    malformed_skipped = skipped_with_submission.to_dict()
    malformed_skipped["submission_id"] = "   "
    with pytest.raises(ControlPlaneError):
        TriggerReceipt.from_dict(malformed_skipped)
    assert not safe_receipt(malformed_skipped, emitted, 200)

    class NegativeLengthResponse:
        def getheaders(self) -> list[tuple[str, str]]:
            return [("Content-Length", "-1")]

    with pytest.raises(RuntimeError, match="invalid response length"):
        runner["read_bounded"](
            NegativeLengthResponse(),
            SimpleNamespace(transport_socket=None),
            runner["time"].monotonic() + 1,
        )


def test_bundle_rejects_time_budget_above_frozen_ceiling() -> None:
    with pytest.raises(ValueError, match="timeout bounds are unsupported"):
        build_trigger_bundle(
            schedule_id="schedule-1",
            schedule_revision_id="revision-1",
            timer_owner_generation=2,
            endpoint_url="https://receiver.example.com/base",
            credential_ref=SecretRef("env", "trigger", "token"),
            credential_env="ETLANTIC_TRIGGER_TOKEN",
            outbound_policy=OutboundPolicy(
                allowed_hosts=("receiver.example.com",),
                max_response_bytes=65_536,
            ),
            timeout_seconds=61,
        )


@pytest.mark.parametrize(
    "credential_env",
    ("CONNECT_INSECURE", "ETLANTIC_TIMER_OWNER_GENERATION"),
)
def test_bundle_reserves_runtime_environment_controls(
    credential_env: str,
) -> None:
    with pytest.raises(ValueError, match="credential_env"):
        build_trigger_bundle(
            schedule_id="schedule-1",
            schedule_revision_id="revision-1",
            timer_owner_generation=2,
            endpoint_url="https://receiver.example.com/base",
            credential_ref=SecretRef("env", "trigger", "token"),
            credential_env=credential_env,
            outbound_policy=OutboundPolicy(
                allowed_hosts=("receiver.example.com",),
                max_response_bytes=65_536,
            ),
        )


def test_archive_validation_reserves_timer_generation_environment(
    tmp_path: Path,
) -> None:
    bundle = _bundle()
    contents = _contents(bundle)
    config = json.loads(contents["etlantic-trigger.json"])
    config["credential_env"] = "ETLANTIC_TIMER_OWNER_GENERATION"
    contents["etlantic-trigger.json"] = (
        json.dumps(config, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    manifest = json.loads(contents["etlantic-trigger-manifest.json"])
    manifest["files"]["etlantic-trigger.json"] = hashlib.sha256(
        contents["etlantic-trigger.json"]
    ).hexdigest()
    contents["etlantic-trigger-manifest.json"] = (
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w:gz", format=tarfile.PAX_FORMAT) as archive:
        for name, body in sorted(contents.items()):
            entry = tarfile.TarInfo(name)
            entry.size = len(body)
            entry.mode = 0o644
            entry.mtime = 0
            archive.addfile(entry, io.BytesIO(body))
    tampered = replace(
        bundle,
        archive=raw.getvalue(),
        sha256=hashlib.sha256(raw.getvalue()).hexdigest(),
        credential_env="ETLANTIC_TIMER_OWNER_GENERATION",
    )

    with pytest.raises(ValueError, match="host policy"):
        tampered.write_to(tmp_path / "invalid")
