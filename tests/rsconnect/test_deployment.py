from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence
from typing import Any

import pytest
from etlantic_rsconnect import (
    DeploymentOutcomeUnknown,
    RsconnectPythonDeployer,
    build_trigger_bundle,
)
from etlantic_rsconnect.bundle import TriggerBundle
from etlantic_rsconnect.deployment import DeploymentIntent

from etlantic.outbound import OutboundPolicy
from etlantic.secrets import SecretRef


class Journal:
    def __init__(self) -> None:
        self.events: list[tuple[object, ...]] = []

    def begin(self, intent: DeploymentIntent) -> None:
        self.events.append(("begin", intent))

    def complete(
        self, intent: DeploymentIntent, *, content_guid: str, result: str
    ) -> None:
        self.events.append(("complete", intent, content_guid, result))

    def uncertain(self, intent: DeploymentIntent, *, result: str) -> None:
        self.events.append(("uncertain", intent, result))


def _refs() -> tuple[SecretRef, SecretRef]:
    return (
        SecretRef("env", "connect", "api-key"),
        SecretRef("env", "receiver", "token"),
    )


def _bundle(trigger_ref: SecretRef) -> TriggerBundle:
    return build_trigger_bundle(
        schedule_id="schedule-1",
        schedule_revision_id="revision-1",
        timer_owner_generation=1,
        endpoint_url="https://receiver.example.com/trigger",
        credential_ref=trigger_ref,
        credential_env="ETLANTIC_TRIGGER_TOKEN",
        outbound_policy=OutboundPolicy(
            allowed_hosts=("receiver.example.com",),
            max_response_bytes=65_536,
        ),
    )


def test_deployer_keeps_credentials_out_of_arguments_and_records_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deployment_ref, trigger_ref = _refs()
    journal = Journal()
    observed: dict[str, object] = {}
    guid = "01234567-89ab-cdef-0123-456789abcdef"
    monkeypatch.setenv("CONNECT_INSECURE", "true")

    def run(
        command: Sequence[str], *, env: Mapping[str, str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        observed["command"] = tuple(command)
        observed["env"] = dict(env)
        observed["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=f"https://connect.example.com/content/{guid}\n",
            stderr="",
        )

    deployer = RsconnectPythonDeployer(
        server_url="https://connect.example.com",
        deployment_credential_ref=deployment_ref,
        trigger_credential_ref=trigger_ref,
        resolve_secret=lambda ref: (
            "connect-api-secret" if ref == deployment_ref else "runtime-trigger-secret"
        ),
        journal=journal,
        run=run,
    )

    result = deployer.deploy(
        _bundle(trigger_ref),
        schedule_id="schedule-1",
        operation_id="operation-1",
        title="ETLantic schedule",
    )

    command = observed["command"]
    assert isinstance(command, tuple)
    assert "--new" in command
    assert "--environment" in command
    assert "ETLANTIC_TRIGGER_TOKEN" in command
    assert "ETLANTIC_TRIGGER_ARMED" in command
    assert "connect-api-secret" not in command
    assert "runtime-trigger-secret" not in command
    captured_env = observed["env"]
    assert isinstance(captured_env, dict)
    assert captured_env["CONNECT_API_KEY"] == "connect-api-secret"
    assert captured_env["CONNECT_INSECURE"] == "false"
    assert captured_env["ETLANTIC_TRIGGER_TOKEN"] == "runtime-trigger-secret"
    assert captured_env["ETLANTIC_TRIGGER_ARMED"] == "false"
    assert result.content_guid == guid
    assert result.state == "deployed"
    assert [event[0] for event in journal.events] == ["begin", "complete"]
    assert journal.events[-1][2] == guid


def test_deployer_reserves_the_tls_verification_environment_control() -> None:
    deployment_ref, trigger_ref = _refs()

    with pytest.raises(ValueError, match="environment variable name"):
        RsconnectPythonDeployer(
            server_url="https://connect.example.com",
            deployment_credential_ref=deployment_ref,
            trigger_credential_ref=trigger_ref,
            trigger_credential_env="CONNECT_INSECURE",
            resolve_secret=lambda _ref: "synthetic-secret",
            journal=Journal(),
        )


def test_deployer_redacts_vendor_output_on_uncertain_publish() -> None:
    deployment_ref, trigger_ref = _refs()
    journal = Journal()

    def run(command: Sequence[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command,
            2,
            stdout="runtime-trigger-secret leaked by vendor",
            stderr="connect-api-secret diagnostic",
        )

    deployer = RsconnectPythonDeployer(
        server_url="https://connect.example.com",
        deployment_credential_ref=deployment_ref,
        trigger_credential_ref=trigger_ref,
        resolve_secret=lambda ref: (
            "connect-api-secret" if ref == deployment_ref else "runtime-trigger-secret"
        ),
        journal=journal,
        run=run,
    )

    with pytest.raises(DeploymentOutcomeUnknown) as error:
        deployer.deploy(
            _bundle(trigger_ref),
            schedule_id="schedule-1",
            operation_id="operation-1",
            title="ETLantic schedule",
        )
    assert "runtime-trigger-secret" not in str(error.value)
    assert "connect-api-secret" not in str(error.value)
    assert journal.events[-1][0] == "uncertain"
