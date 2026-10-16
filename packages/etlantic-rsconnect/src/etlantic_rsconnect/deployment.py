"""Explicit-target rsconnect-python publishing with durable handoff hooks."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, cast
from urllib.parse import urlsplit

from etlantic.secrets import SecretRef, SecretValue
from etlantic_rsconnect.bundle import TriggerBundle

_GUID_VALUE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_GUID_IN_OUTPUT = re.compile(
    r"(?i)(?:/content/|content(?:_guid|_id)?[=: ]+)([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
)
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,119}$")
_ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]{0,127}$")
_RESERVED_ENV = frozenset(
    {
        "CONNECT_API_KEY",
        "CONNECT_INSECURE",
        "CONNECT_SERVER",
        "ETLANTIC_TRIGGER_ARMED",
        "ETLANTIC_SCHEDULED_AT",
        "ETLANTIC_DELIVERY_ATTEMPT_ID",
        "ETLANTIC_CORRELATION_ID",
        "ETLANTIC_TIMER_OWNER_GENERATION",
    }
)


class DeploymentError(RuntimeError):
    """A redacted publishing failure that is safe to show to an operator."""


class DeploymentOutcomeUnknown(DeploymentError):
    """Publishing may have committed; inspect the journal and Connect first."""


@dataclass(frozen=True, slots=True)
class DeploymentIntent:
    schedule_id: str
    operation_id: str
    bundle_sha256: str
    server_url: str
    existing_content_guid: str | None


class DeploymentJournal(Protocol):
    """Caller-owned durable operation journal; never stores credential values."""

    def begin(self, intent: DeploymentIntent) -> None: ...

    def complete(
        self, intent: DeploymentIntent, *, content_guid: str, result: str
    ) -> None: ...

    def uncertain(self, intent: DeploymentIntent, *, result: str) -> None: ...


@dataclass(frozen=True, slots=True)
class DeploymentResult:
    content_guid: str
    state: Literal["deployed", "updated"]
    bundle_sha256: str
    server_url: str
    operation_id: str


class RsconnectPythonDeployer:
    """Publish a generated bundle using the documented rsconnect CLI.

    The API key and runtime trigger secret are supplied only through the child
    process environment. CLI output is captured and discarded because a vendor
    tool may echo environment configuration in diagnostics.
    """

    def __init__(
        self,
        *,
        server_url: str,
        deployment_credential_ref: SecretRef,
        trigger_credential_ref: SecretRef,
        trigger_credential_env: str = "ETLANTIC_TRIGGER_TOKEN",
        rsconnect_binary: str = "rsconnect",
        resolve_secret: Callable[[SecretRef], str | SecretValue],
        journal: DeploymentJournal,
        run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self.server_url = _normalize_server_url(server_url)
        if (
            not _ENV_NAME.fullmatch(trigger_credential_env)
            or trigger_credential_env in _RESERVED_ENV
        ):
            raise ValueError(
                "trigger_credential_env must be an environment variable name"
            )
        if deployment_credential_ref == trigger_credential_ref:
            raise ValueError(
                "deployment and trigger credentials must be distinct references"
            )
        self.deployment_credential_ref = deployment_credential_ref
        self.trigger_credential_ref = trigger_credential_ref
        self.trigger_credential_env = trigger_credential_env
        self.rsconnect_binary = rsconnect_binary
        self.resolve_secret = resolve_secret
        self.journal = journal
        self.run = run

    def deploy(
        self,
        bundle: TriggerBundle,
        *,
        schedule_id: str,
        operation_id: str,
        title: str,
        existing_content_guid: str | None = None,
    ) -> DeploymentResult:
        self.validate_deployment(
            bundle,
            schedule_id=schedule_id,
            operation_id=operation_id,
            title=title,
            existing_content_guid=existing_content_guid,
        )
        intent = DeploymentIntent(
            schedule_id=schedule_id,
            operation_id=operation_id,
            bundle_sha256=bundle.sha256,
            server_url=self.server_url,
            existing_content_guid=existing_content_guid,
        )
        # The caller's journal must durably record intent before any remote create.
        self.journal.begin(intent)
        try:
            api_key = _secret_text(self.resolve_secret(self.deployment_credential_ref))
            trigger_token = _secret_text(
                self.resolve_secret(self.trigger_credential_ref)
            )
        except Exception:
            _mark_uncertain(self.journal, intent, "credential_resolution_failed")
            raise DeploymentError(
                "deployment credentials could not be resolved"
            ) from None

        child_env = os.environ.copy()
        child_env["CONNECT_SERVER"] = self.server_url
        child_env["CONNECT_API_KEY"] = api_key
        child_env[self.trigger_credential_env] = trigger_token
        # Posit Connect accepts CONNECT_INSECURE as an environment override.
        # Force certificate and hostname verification after credential injection
        # so a runtime credential name can never replace this control.
        child_env["CONNECT_INSECURE"] = "false"
        # Connect renders content as part of deployment. Keep the script inert
        # until the canonical timer binding has been reconciled and armed.
        child_env["ETLANTIC_TRIGGER_ARMED"] = "false"
        child_env["RSCONNECT_DISABLE_VERSION_CHECK"] = "1"
        command = [
            self.rsconnect_binary,
            "deploy",
            "quarto",
            "--server",
            self.server_url,
            "--title",
            title,
            "--environment",
            self.trigger_credential_env,
            "--environment",
            "ETLANTIC_TRIGGER_ARMED",
            "--quiet",
        ]
        if existing_content_guid is None:
            command.append("--new")
        else:
            command.extend(("--app-id", existing_content_guid))
        try:
            with tempfile.TemporaryDirectory(prefix="etlantic-rsconnect-") as temp:
                content_dir = Path(temp) / "content"
                bundle.write_to(content_dir)
                command.append(str(content_dir))
                completed = self.run(
                    command,
                    env=child_env,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=900,
                )
        except subprocess.TimeoutExpired:
            _mark_uncertain(self.journal, intent, "publish_timeout")
            raise DeploymentOutcomeUnknown(
                "Connect publishing timed out; inspect the deployment journal and remote content before retrying"
            ) from None
        except OSError:
            _mark_uncertain(self.journal, intent, "publish_process_failed")
            raise DeploymentError(
                "rsconnect-python could not be started; inspect the deployment journal"
            ) from None
        except Exception:
            _mark_uncertain(self.journal, intent, "publish_failed")
            raise DeploymentError(
                "Connect publishing failed; inspect the deployment journal"
            ) from None
        finally:
            child_env.pop("CONNECT_API_KEY", None)
            child_env.pop(self.trigger_credential_env, None)

        # Never surface vendor stdout/stderr: it is untrusted and may include
        # secrets. A nonzero exit is uncertain because the remote task may exist.
        if completed.returncode != 0:
            _mark_uncertain(self.journal, intent, "publish_nonzero_exit")
            raise DeploymentOutcomeUnknown(
                "Connect publishing did not return success; inspect owned content before retrying"
            )
        output = (completed.stdout or "") + "\n" + (completed.stderr or "")
        guids = {guid.lower() for guid in _GUID_IN_OUTPUT.findall(output)}
        if existing_content_guid is not None:
            content_guid = existing_content_guid
        elif len(guids) == 1:
            content_guid = next(iter(guids))
        else:
            _mark_uncertain(self.journal, intent, "content_guid_not_unambiguous")
            raise DeploymentOutcomeUnknown(
                "Connect deployment may have completed, but its content GUID is ambiguous; reconcile by owner and deployment journal before retrying"
            )
        result = DeploymentResult(
            content_guid=content_guid,
            state="updated" if existing_content_guid else "deployed",
            bundle_sha256=bundle.sha256,
            server_url=self.server_url,
            operation_id=operation_id,
        )
        try:
            self.journal.complete(
                intent, content_guid=content_guid, result=result.state
            )
        except Exception:
            _mark_uncertain(
                self.journal, intent, "deployment_succeeded_journal_commit_failed"
            )
            raise DeploymentOutcomeUnknown(
                "Connect publishing succeeded but its durable result could not be recorded; reconcile the deployment before retrying"
            ) from None
        return result

    def validate_deployment(
        self,
        bundle: TriggerBundle,
        *,
        schedule_id: str,
        operation_id: str,
        title: str,
        existing_content_guid: str | None = None,
    ) -> None:
        """Check deployment inputs without resolving secrets or causing effects.

        Coordinators can run this preflight before claiming another durable
        resource that must stay consistent with the deployment.
        """
        if not _NAME.fullmatch(title):
            raise ValueError("title must be a bounded Connect content name")
        schedule_id_value: object = cast(object, schedule_id)
        operation_id_value: object = cast(object, operation_id)
        if (
            not isinstance(schedule_id_value, str)
            or not schedule_id_value.strip()
            or len(schedule_id_value) > 512
            or not isinstance(operation_id_value, str)
            or not operation_id_value.strip()
            or len(operation_id_value) > 256
        ):
            raise ValueError("schedule_id and operation_id must be non-empty")
        if schedule_id != bundle.schedule_id:
            raise ValueError("deployment schedule_id does not match the trigger bundle")
        if self.trigger_credential_env != bundle.credential_env:
            raise ValueError(
                "deployment credential environment does not match the trigger bundle"
            )
        if self.trigger_credential_ref != bundle.credential_ref:
            raise ValueError(
                "runtime credential reference does not match the trigger bundle"
            )
        if existing_content_guid is not None and not _GUID_VALUE.fullmatch(
            existing_content_guid
        ):
            raise ValueError("existing_content_guid must be a Connect GUID")


def _secret_text(value: object) -> str:
    if isinstance(value, SecretValue):
        value = value.get_secret_value()
    if (
        not isinstance(value, str)
        or not value
        or any(char in value for char in "\r\n\x00")
    ):
        raise DeploymentError("deployment credentials could not be resolved")
    return value


def _normalize_server_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("server_url must be an explicit HTTPS URL")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("server_url port is invalid") from exc
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("server_url port is invalid")
    host = parsed.hostname.lower()
    port_text = f":{port}" if port is not None and port != 443 else ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return f"https://{host}{port_text}{parsed.path.rstrip('/')}"


def _mark_uncertain(
    journal: DeploymentJournal, intent: DeploymentIntent, result: str
) -> None:
    with suppress(Exception):
        journal.uncertain(intent, result=result)
