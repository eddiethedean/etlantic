"""Bounded, read-only Confluent-compatible schema registry lookup."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, cast
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from etlantic.streaming.registry import SchemaFormat, schema_fingerprint


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        del req, fp, code, msg, headers, newurl
        return None


@dataclass(slots=True)
class ConfluentHttpRegistry:
    """Fetch schema documents without registering or retaining them in artifacts."""

    base_url: str = field(repr=False)
    authorization: str | None = field(default=None, repr=False)
    allowed_hosts: tuple[str, ...] = ()
    max_bytes: int = 4 * 1024 * 1024
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        parsed = urlsplit(self.base_url)
        if parsed.scheme != "https" and not (
            parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
        ):
            raise ValueError("Schema registry requires HTTPS or local HTTP")
        if parsed.username or parsed.password or not parsed.hostname:
            raise ValueError("Schema registry URL must not contain credentials")
        if parsed.scheme == "https" and parsed.hostname not in self.allowed_hosts:
            raise ValueError("Schema registry host is not allowlisted")
        if parsed.query or parsed.fragment:
            raise ValueError("Schema registry URL must not contain query or fragment")
        if self.max_bytes < 1 or self.timeout_seconds <= 0:
            raise ValueError("Schema registry budgets must be positive")
        self.base_url = self.base_url.rstrip("/")

    def fetch_schema(self, subject: str, version: int | None = None) -> dict[str, Any]:
        """Return one bounded subject version; the caller may discard the document."""
        if not subject or (version is not None and version < 1):
            raise ValueError("Schema registry subject or version is invalid")
        version_text = "latest" if version is None else str(version)
        url = (
            f"{self.base_url}/subjects/{quote(subject, safe='')}/versions/"
            f"{version_text}"
        )
        headers = {"Accept": "application/vnd.schemaregistry.v1+json"}
        if self.authorization is not None:
            headers["Authorization"] = self.authorization
        request = Request(url, headers=headers, method="GET")
        try:
            opener = build_opener(_RejectRedirects())
            with opener.open(request, timeout=self.timeout_seconds) as response:
                payload_bytes = response.read(self.max_bytes + 1)
        except Exception as exc:
            raise ValueError("Schema registry lookup failed") from exc
        if len(payload_bytes) > self.max_bytes:
            raise ValueError("Schema registry response exceeds the byte limit")
        try:
            parsed: Any = json.loads(payload_bytes)
            if not isinstance(parsed, dict):
                raise ValueError("response is not an object")
            payload = cast(dict[str, Any], parsed)
            document = payload["schema"]
            observed_version = payload["version"]
            observed_subject = payload.get("subject", subject)
            raw_format = payload.get("schemaType", "AVRO")
            if (
                not isinstance(document, str)
                or type(observed_version) is not int
                or observed_subject != subject
            ):
                raise ValueError("schema or version is invalid")
            if version is not None and observed_version != version:
                raise ValueError("schema version changed")
            schema_format = {
                "AVRO": SchemaFormat.AVRO,
                "JSON": SchemaFormat.JSON_SCHEMA,
                "PROTOBUF": SchemaFormat.PROTOBUF,
            }.get(raw_format)
            if schema_format is None:
                raise ValueError("schema format is unsupported")
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Schema registry response is malformed") from exc
        return {
            "subject": subject,
            "version": observed_version,
            "format": schema_format.value,
            "document": document,
            "fingerprint": schema_fingerprint(document, format=schema_format),
        }
