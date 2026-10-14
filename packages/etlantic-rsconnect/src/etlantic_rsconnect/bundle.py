"""Build deterministic, dependency-free Python/Quarto trigger bundles."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import math
import re
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

from etlantic.control_plane.trigger import TRIGGER_ENVELOPE_SCHEMA
from etlantic.outbound import OutboundPolicy
from etlantic.secrets import SecretRef
from etlantic_rsconnect.limits import (
    MAX_DELIVERY_ATTEMPTS,
    MAX_DELIVERY_ELAPSED_SECONDS,
    MAX_REQUEST_TIMEOUT_SECONDS,
    MAX_RESPONSE_BYTES,
    MAX_RETRY_AFTER_SECONDS,
)
from etlantic_rsconnect.runner import RUNNER_SOURCE

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
    }
)
_BUNDLE_MANIFEST = "etlantic-trigger-manifest.json"
_BUNDLE_MANIFEST_SCHEMA = "etlantic.rsconnect.trigger_bundle/1"
_BUNDLE_FILES = (
    "_quarto.yml",
    "etlantic-trigger.json",
    "etlantic-trigger.py",
    _BUNDLE_MANIFEST,
    "index.qmd",
    "requirements.txt",
)
_QUARTO_CONFIG = (
    b"project:\n"
    b"  type: default\n"
    b"  render:\n"
    b"    - index.qmd\n"
    b"  pre-render: python etlantic-trigger.py\n"
    b"execute:\n"
    b"  freeze: false\n"
    b"  cache: false\n"
)
_INDEX_DOCUMENT = (
    b"---\n"
    b"title: ETLantic schedule trigger\n"
    b"format: html\n"
    b"---\n\n"
    b"This content submits schedule occurrences to the configured "
    b"ETLantic receiver. Its render status does not indicate ETL "
    b"completion.\n"
)
_REQUIREMENTS = b"# Standard-library-only trigger content.\n"


@dataclass(frozen=True, slots=True)
class TriggerBundle:
    archive: bytes
    sha256: str
    files: tuple[str, ...]
    schema: str
    schedule_id: str
    schedule_revision_id: str
    timer_owner_generation: int
    endpoint_url: str
    credential_ref: SecretRef
    credential_env: str

    def write_to(self, directory: str | Path) -> Path:
        """Write the known bundle files to an empty directory for rsconnect."""
        if hashlib.sha256(self.archive).hexdigest() != self.sha256:
            raise ValueError("trigger archive hash does not match its manifest")
        if self.files != _BUNDLE_FILES or len(self.archive) > 2_097_152:
            raise ValueError("trigger archive manifest or size is unsupported")
        contents: dict[str, bytes] = {}
        try:
            with tarfile.open(fileobj=io.BytesIO(self.archive), mode="r:gz") as archive:
                members = archive.getmembers()
                if len(members) != len(_BUNDLE_FILES):
                    raise ValueError("trigger archive does not match its file manifest")
                for member in members:
                    if (
                        not member.isfile()
                        or member.name not in _BUNDLE_FILES
                        or Path(member.name).name != member.name
                        or member.name in contents
                        or member.size < 0
                        or member.size > 1_048_576
                    ):
                        raise ValueError("trigger archive contains an unexpected entry")
                    content = archive.extractfile(member)
                    if content is None:
                        raise ValueError("trigger archive contains an unreadable entry")
                    body = content.read(1_048_577)
                    if len(body) != member.size:
                        raise ValueError("trigger archive contains a truncated entry")
                    contents[member.name] = body
        except (tarfile.TarError, OSError, EOFError):
            raise ValueError("trigger archive is malformed") from None
        if set(contents) != set(_BUNDLE_FILES):
            raise ValueError("trigger archive does not match its file manifest")
        manifest = _decode_bundle_config(contents[_BUNDLE_MANIFEST])
        _validate_source_manifest(manifest, contents)
        if (
            contents["_quarto.yml"] != _QUARTO_CONFIG
            or contents["index.qmd"] != _INDEX_DOCUMENT
            or contents["etlantic-trigger.py"] != RUNNER_SOURCE.encode("utf-8")
            or contents["requirements.txt"] != _REQUIREMENTS
        ):
            raise ValueError(
                "trigger archive contains modified runner or Quarto source"
            )
        config = _decode_bundle_config(contents["etlantic-trigger.json"])
        _validate_bundle_config(self, config)
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=False)
        for name, content in contents.items():
            (root / name).write_bytes(content)
        return root


def build_trigger_bundle(
    *,
    schedule_id: str,
    schedule_revision_id: str,
    timer_owner_generation: int,
    endpoint_url: str,
    credential_ref: SecretRef,
    credential_env: str,
    outbound_policy: OutboundPolicy,
    max_attempts: int = 3,
    timeout_seconds: float = 10,
    max_elapsed_seconds: float = 30,
    max_response_bytes: int = 65_536,
    max_retry_after_seconds: float = 5,
) -> TriggerBundle:
    """Create a reproducible archive with no ETLantic or provider dependency.

    Connect currently does not provide the required nominal-slot and retry
    identifiers in a documented scheduled invocation. The generated content
    therefore requires an external trusted context injector and fails closed
    when the three ETLANTIC_* context variables are absent.
    """
    for name, raw_value in (
        ("schedule_id", schedule_id),
        ("schedule_revision_id", schedule_revision_id),
    ):
        value: object = cast(object, raw_value)
        if not isinstance(value, str) or not value.strip() or len(value) > 512:
            raise ValueError(f"{name} must contain 1 to 512 characters")
    raw_policy: object = cast(object, outbound_policy)
    if not isinstance(raw_policy, OutboundPolicy):
        raise ValueError("outbound_policy must be an OutboundPolicy")
    outbound_policy = raw_policy
    raw_allowed_hosts: object = cast(object, outbound_policy.allowed_hosts)
    raw_allowed_schemes: object = cast(object, outbound_policy.allowed_schemes)
    if (
        not isinstance(raw_allowed_hosts, (tuple, list))
        or any(
            not isinstance(host, str) or not host or host != host.strip()
            for host in cast(tuple[object, ...] | list[object], raw_allowed_hosts)
        )
        or not isinstance(raw_allowed_schemes, (tuple, list))
        or any(
            not isinstance(scheme, str)
            for scheme in cast(tuple[object, ...] | list[object], raw_allowed_schemes)
        )
        or type(outbound_policy.timeout_seconds) not in (int, float)
        or not math.isfinite(outbound_policy.timeout_seconds)
        or outbound_policy.timeout_seconds <= 0
        or type(outbound_policy.max_response_bytes) is not int
        or not 1 <= outbound_policy.max_response_bytes <= MAX_RESPONSE_BYTES
        or not all(
            type(value) is bool
            for value in (
                outbound_policy.allow_private,
                outbound_policy.allow_loopback,
                outbound_policy.allow_link_local,
                outbound_policy.allow_redirects,
                outbound_policy.forward_ambient_credentials,
                outbound_policy.default_deny,
            )
        )
    ):
        raise ValueError("outbound policy bounds or flags are invalid")
    if not outbound_policy.default_deny:
        raise ValueError("trigger delivery requires a default-deny outbound policy")
    if outbound_policy.allow_redirects:
        raise ValueError("trigger delivery does not allow redirects")
    if outbound_policy.forward_ambient_credentials:
        raise ValueError("ambient credential forwarding is prohibited")
    if type(timer_owner_generation) is not int or timer_owner_generation < 1:
        raise ValueError("timer_owner_generation must be a positive integer")
    if not _ENV_NAME.fullmatch(credential_env) or credential_env in _RESERVED_ENV:
        raise ValueError("credential_env must be a bounded environment variable name")
    parsed = urlsplit(endpoint_url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "endpoint_url must be HTTPS without user info, query, or fragment"
        )
    try:
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            raise ValueError("endpoint_url port is invalid")
    except ValueError as exc:
        raise ValueError("endpoint_url port is invalid") from exc
    allowed_hosts = {host.lower() for host in outbound_policy.allowed_hosts}
    if parsed.hostname.lower() in {
        "metadata",
        "metadata.google.internal",
        "169.254.169.254",
    }:
        raise ValueError("endpoint host is blocked by outbound policy")
    if parsed.hostname.lower() not in allowed_hosts:
        raise ValueError(
            "endpoint host must be explicitly present in outbound allowlist"
        )
    if "https" not in {scheme.lower() for scheme in outbound_policy.allowed_schemes}:
        raise ValueError("outbound policy must allow HTTPS")
    if (
        type(max_attempts) is not int
        or not 1 <= max_attempts <= MAX_DELIVERY_ATTEMPTS
        or type(timeout_seconds) not in (int, float)
        or type(max_elapsed_seconds) not in (int, float)
        or not math.isfinite(timeout_seconds)
        or not math.isfinite(max_elapsed_seconds)
        or timeout_seconds <= 0
        or max_elapsed_seconds <= 0
        or timeout_seconds > MAX_REQUEST_TIMEOUT_SECONDS
        or max_elapsed_seconds > MAX_DELIVERY_ELAPSED_SECONDS
    ):
        raise ValueError("delivery attempt and timeout bounds are unsupported")
    if (
        type(max_retry_after_seconds) not in (int, float)
        or not math.isfinite(max_retry_after_seconds)
        or max_retry_after_seconds < 0
        or max_retry_after_seconds > MAX_RETRY_AFTER_SECONDS
    ):
        raise ValueError("max_retry_after_seconds is outside the supported bounds")
    if type(max_response_bytes) is not int or not 1 <= max_response_bytes <= min(
        MAX_RESPONSE_BYTES, outbound_policy.max_response_bytes
    ):
        raise ValueError(
            f"max_response_bytes must be between 1 and {MAX_RESPONSE_BYTES}"
        )
    if timeout_seconds > outbound_policy.timeout_seconds:
        raise ValueError("timeout exceeds the outbound policy")
    if not credential_ref.provider or not credential_ref.name or not credential_ref.key:
        raise ValueError("credential_ref must be a complete secret reference")

    config = {
        "schema": TRIGGER_ENVELOPE_SCHEMA,
        "schedule_id": schedule_id,
        "schedule_revision_id": schedule_revision_id,
        "timer_owner_generation": timer_owner_generation,
        "endpoint_url": endpoint_url,
        "allowed_hosts": sorted(allowed_hosts),
        "allow_private": outbound_policy.allow_private,
        "allow_loopback": outbound_policy.allow_loopback,
        "allow_link_local": outbound_policy.allow_link_local,
        "credential_ref": credential_ref.to_dict(),
        "credential_env": credential_env,
        "occurrence_context_provider": None,
        "max_attempts": max_attempts,
        "timeout_seconds": timeout_seconds,
        "max_elapsed_seconds": max_elapsed_seconds,
        "max_response_bytes": max_response_bytes,
        "max_retry_after_seconds": max_retry_after_seconds,
    }
    files = {
        "_quarto.yml": _QUARTO_CONFIG,
        "index.qmd": _INDEX_DOCUMENT,
        "etlantic-trigger.py": RUNNER_SOURCE.encode("utf-8"),
        "requirements.txt": _REQUIREMENTS,
        "etlantic-trigger.json": (
            json.dumps(config, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode("utf-8"),
    }
    source_manifest = {
        "schema": _BUNDLE_MANIFEST_SCHEMA,
        "files": {
            name: hashlib.sha256(contents).hexdigest()
            for name, contents in sorted(files.items())
        },
    }
    files[_BUNDLE_MANIFEST] = (
        json.dumps(source_manifest, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    raw = io.BytesIO()
    with (
        gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as compressed,
        tarfile.open(
            fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT
        ) as archive,
    ):
        for name, contents in sorted(files.items()):
            entry = tarfile.TarInfo(name)
            entry.size = len(contents)
            entry.mode = 0o644
            entry.mtime = 0
            archive.addfile(entry, io.BytesIO(contents))
    archive_bytes = raw.getvalue()
    return TriggerBundle(
        archive=archive_bytes,
        sha256=hashlib.sha256(archive_bytes).hexdigest(),
        files=_BUNDLE_FILES,
        schema=TRIGGER_ENVELOPE_SCHEMA,
        schedule_id=schedule_id,
        schedule_revision_id=schedule_revision_id,
        timer_owner_generation=timer_owner_generation,
        endpoint_url=endpoint_url,
        credential_ref=credential_ref,
        credential_env=credential_env,
    )


def _decode_bundle_config(body: bytes) -> dict[str, object]:
    def unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("trigger bundle config contains duplicate fields")
            result[key] = value
        return result

    try:
        value = json.loads(body.decode("utf-8"), object_pairs_hook=unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
        raise ValueError("trigger bundle config is malformed") from None
    if not isinstance(value, dict):
        raise ValueError("trigger bundle config must be a JSON object")
    return cast(dict[str, object], value)


def _validate_source_manifest(
    manifest: dict[str, object], contents: dict[str, bytes]
) -> None:
    if set(manifest) != {"schema", "files"}:
        raise ValueError("trigger source manifest has unsupported fields")
    if manifest["schema"] != _BUNDLE_MANIFEST_SCHEMA:
        raise ValueError("trigger source manifest version is unsupported")
    raw_files = manifest["files"]
    if not isinstance(raw_files, dict):
        raise ValueError("trigger source manifest file map is invalid")
    file_hashes = cast(dict[object, object], raw_files)
    expected_names = set(_BUNDLE_FILES) - {_BUNDLE_MANIFEST}
    if set(file_hashes) != expected_names:
        raise ValueError("trigger source manifest file list is invalid")
    for name in expected_names:
        expected_hash = file_hashes[name]
        if (
            not isinstance(expected_hash, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected_hash)
            or hashlib.sha256(contents[name]).hexdigest() != expected_hash
        ):
            raise ValueError("trigger source manifest digest does not match content")


def _validate_bundle_config(bundle: TriggerBundle, config: dict[str, object]) -> None:
    expected_fields = {
        "schema",
        "schedule_id",
        "schedule_revision_id",
        "timer_owner_generation",
        "endpoint_url",
        "allowed_hosts",
        "allow_private",
        "allow_loopback",
        "allow_link_local",
        "credential_ref",
        "credential_env",
        "max_attempts",
        "timeout_seconds",
        "max_elapsed_seconds",
        "max_response_bytes",
        "max_retry_after_seconds",
        "occurrence_context_provider",
    }
    if set(config) != expected_fields:
        raise ValueError("trigger bundle config has missing or unsupported fields")
    if (
        config["schema"] != bundle.schema
        or config["schema"] != TRIGGER_ENVELOPE_SCHEMA
        or config["schedule_id"] != bundle.schedule_id
        or config["schedule_revision_id"] != bundle.schedule_revision_id
        or config["timer_owner_generation"] != bundle.timer_owner_generation
        or config["endpoint_url"] != bundle.endpoint_url
        or config["credential_env"] != bundle.credential_env
        or config["credential_ref"] != bundle.credential_ref.to_dict()
        or config["occurrence_context_provider"] is not None
    ):
        raise ValueError("trigger bundle config does not match its manifest")
    parsed = urlsplit(bundle.endpoint_url)
    raw_hosts = config["allowed_hosts"]
    if not isinstance(raw_hosts, list):
        raise ValueError("trigger bundle host policy is invalid")
    host_values = cast(list[object], raw_hosts)
    if any(not isinstance(host, str) for host in host_values):
        raise ValueError("trigger bundle host policy is invalid")
    allowed_hosts = [cast(str, host) for host in host_values]
    if parsed.hostname is None:
        raise ValueError("trigger bundle endpoint host is invalid")
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.hostname.lower() not in allowed_hosts
        or parsed.hostname.lower()
        in {"metadata", "metadata.google.internal", "169.254.169.254"}
    ):
        raise ValueError("trigger bundle host policy is invalid")
    try:
        port = parsed.port
    except ValueError:
        raise ValueError("trigger bundle endpoint port is invalid") from None
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("trigger bundle endpoint port is invalid")
    if any(
        type(config[key]) is not bool
        for key in ("allow_private", "allow_loopback", "allow_link_local")
    ):
        raise ValueError("trigger bundle host policy flags are invalid")
    raw_attempts = config["max_attempts"]
    if type(raw_attempts) is not int or not 1 <= raw_attempts <= MAX_DELIVERY_ATTEMPTS:
        raise ValueError("trigger bundle retry bounds are invalid")
    raw_response_bytes = config["max_response_bytes"]
    if (
        type(raw_response_bytes) is not int
        or not 1 <= raw_response_bytes <= MAX_RESPONSE_BYTES
    ):
        raise ValueError("trigger bundle response bound is invalid")
    numeric_values: list[float | int] = []
    for name in ("timeout_seconds", "max_elapsed_seconds", "max_retry_after_seconds"):
        value = config[name]
        if type(value) not in (int, float):
            raise ValueError("trigger bundle time bounds are invalid")
        number = cast(float | int, value)
        if not math.isfinite(number):
            raise ValueError("trigger bundle time bounds are invalid")
        numeric_values.append(number)
    timeout_value, elapsed_value, retry_after_value = numeric_values
    if (
        timeout_value <= 0
        or timeout_value > MAX_REQUEST_TIMEOUT_SECONDS
        or elapsed_value <= 0
        or elapsed_value > MAX_DELIVERY_ELAPSED_SECONDS
        or retry_after_value < 0
        or retry_after_value > MAX_RETRY_AFTER_SECONDS
    ):
        raise ValueError("trigger bundle time bounds are invalid")
    credential_env = config["credential_env"]
    if (
        not isinstance(credential_env, str)
        or not _ENV_NAME.fullmatch(credential_env)
        or credential_env in _RESERVED_ENV
    ):
        raise ValueError("trigger bundle host policy is invalid")
