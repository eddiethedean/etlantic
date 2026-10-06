"""Foundry dataset file connectors using Palantir's REST API v2."""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import re
import urllib.parse
from collections.abc import (
    AsyncGenerator,
    AsyncIterator,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
)
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, cast

import httpx2

from etlantic.connectors.capabilities import (
    IDEMPOTENCY,
    PUBLICATION_ATOMIC,
    RECONCILIATION,
    SOURCE_BATCH_SNAPSHOT,
    SOURCE_SCHEMA_DISCOVERY,
    TRANSACTIONS,
    WRITE_APPEND,
    WRITE_OVERWRITE,
)
from etlantic.connectors.errors import (
    ConnectorConfigError,
    ConnectorReadError,
    ConnectorWriteError,
)
from etlantic.connectors.maturity import ConnectorMaturity
from etlantic.connectors.models import (
    SINK_PROTOCOL,
    SOURCE_PROTOCOL,
    STORAGE_PROTOCOL,
    CleanupReceipt,
    CommitReceipt,
    ConnectorInfo,
    CursorProposal,
    LandingFileIdentity,
    LandingReadManifest,
    ReadBatch,
    ReconciliationResult,
    SchemaInspection,
    SinkPlan,
    SourcePlan,
    WriteSession,
    fingerprint_public_config,
)
from etlantic.secrets import SecretValue
from etlantic_foundry.schemas import (
    SINK_CONFIG_SCHEMA,
    SOURCE_CONFIG_SCHEMA,
    STORAGE_CONFIG_SCHEMA,
)

PROVIDER = "foundry"
PACKAGE_VERSION = "0.56.0"
DEFAULT_TIMEOUT = 20
MAX_TIMEOUT = 60
DEFAULT_PAGE_SIZE = 200
MAX_PAGE_SIZE = 500
DEFAULT_MAX_FILES = 1000
MAX_FILES = 10_000
DEFAULT_FILE_BYTES = 32 * 1024 * 1024
MAX_FILE_BYTES = 128 * 1024 * 1024
DEFAULT_TOTAL_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
DEFAULT_MAX_ROWS = 100_000
MAX_ROWS = 1_000_000
DEFAULT_BATCH_SIZE = 1000
MAX_BATCH_SIZE = 10_000

_BASE_KEYS = {"base_url", "dataset_rid", "branch_name", "timeout_seconds"}
_SOURCE_KEYS = _BASE_KEYS | {
    "transaction_rid",
    "mode",
    "path_prefix",
    "format",
    "encoding",
    "delimiter",
    "max_files",
    "max_file_bytes",
    "max_total_bytes",
    "max_rows",
    "batch_size",
    "allow_empty",
}
_SINK_KEYS = _BASE_KEYS | {
    "mode",
    "file_path",
    "path_prefix",
    "format",
    "encoding",
    "delimiter",
    "max_rows",
    "max_bytes",
}
_STORAGE_KEYS = _BASE_KEYS | {
    "path_prefix",
    "format",
    "encoding",
    "delimiter",
    "max_file_bytes",
}
_FORMAT_EXT = {"csv": "csv", "json": "json", "jsonl": "jsonl"}


def _config(binding: Mapping[str, Any], allowed: set[str]) -> dict[str, Any]:
    raw = binding.get("config")
    if raw is not None and not isinstance(raw, Mapping):
        raise ConnectorConfigError(
            "Foundry config must be an object", code="PMFND001", provider=PROVIDER
        )
    cfg: dict[str, Any] = dict(cast(Mapping[str, Any], raw) if raw is not None else {})
    unknown = set(cfg).difference(allowed)
    if unknown:
        raise ConnectorConfigError(
            "unsupported Foundry options: " + ", ".join(sorted(unknown)),
            code="PMFND002",
            provider=PROVIDER,
        )
    # Format may be declared in the common asset format field. Promote it into
    # config before computing fingerprints so plan and runtime agree.
    binding_format = binding.get("format")
    if binding_format is not None:
        if "format" in cfg and cfg["format"] != binding_format:
            raise ConnectorConfigError(
                "Foundry format conflicts between binding and config",
                code="PMFND003",
                provider=PROVIDER,
            )
        cfg["format"] = binding_format
    return cfg


def _secret_ref_names(binding: Mapping[str, Any]) -> tuple[str, ...]:
    raw = binding.get("secret_refs")
    if not isinstance(raw, Mapping):
        return ()
    secret_refs = cast(Mapping[str, Any], raw)
    return tuple(sorted(str(key) for key in secret_refs))


def _base(cfg: Mapping[str, Any]) -> tuple[str, str]:
    raw = cfg.get("base_url")
    rid = cfg.get("dataset_rid")
    branch = cfg.get("branch_name")
    if not isinstance(raw, str) or not raw:
        raise ConnectorConfigError(
            "Foundry requires base_url", code="PMFND004", provider=PROVIDER
        )
    try:
        parsed = urllib.parse.urlsplit(raw)
    except ValueError as exc:
        raise ConnectorConfigError(
            "invalid Foundry base_url", code="PMFND004", provider=PROVIDER
        ) from exc
    local_http = parsed.scheme == "http" and parsed.hostname in {
        "localhost",
        "127.0.0.1",
        "::1",
    }
    if (
        (parsed.scheme != "https" and not local_http)
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ConnectorConfigError(
            "Foundry base_url must be an HTTPS origin without credentials or path",
            code="PMFND005",
            provider=PROVIDER,
        )
    if not isinstance(rid, str) or not rid or "/" in rid or "?" in rid:
        raise ConnectorConfigError(
            "Foundry dataset_rid is required", code="PMFND006", provider=PROVIDER
        )
    if not isinstance(branch, str) or not branch.strip():
        raise ConnectorConfigError(
            "Foundry branch_name is required", code="PMFND007", provider=PROVIDER
        )
    return raw.rstrip("/"), rid


def _int_option(
    value: Any, *, name: str, default: int, maximum: int, minimum: int = 1
) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ConnectorConfigError(
            f"{name} must be an integer of at least {minimum}",
            code="PMFND008",
            provider=PROVIDER,
        )
    if value > maximum:
        raise ConnectorConfigError(
            f"{name} exceeds the maximum of {maximum}",
            code="PMFND009",
            provider=PROVIDER,
        )
    return value


def _encoding(cfg: Mapping[str, Any]) -> str:
    value = cfg.get("encoding", "utf-8")
    if value not in {"utf-8", "utf-8-sig", "latin-1"}:
        raise ConnectorConfigError(
            "Foundry encoding must be utf-8, utf-8-sig or latin-1",
            code="PMFND010",
            provider=PROVIDER,
        )
    return str(value)


def _format(cfg: Mapping[str, Any], binding: Mapping[str, Any]) -> str:
    value = cfg.get("format") or binding.get("format") or "csv"
    if value not in _FORMAT_EXT:
        raise ConnectorConfigError(
            "Foundry format must be csv, json or jsonl",
            code="PMFND011",
            provider=PROVIDER,
        )
    return str(value)


def _delimiter(cfg: Mapping[str, Any]) -> str:
    value = cfg.get("delimiter", ",")
    if not isinstance(value, str) or len(value) != 1 or value in {"\r", "\n", "\0"}:
        raise ConnectorConfigError(
            "Foundry delimiter must be one non-newline character",
            code="PMFND012",
            provider=PROVIDER,
        )
    return value


def _safe_path(value: Any, *, prefix: bool = False) -> str:
    if not isinstance(value, str) or not value or value.startswith("/"):
        raise ConnectorConfigError(
            "Foundry file paths must be nonempty relative paths",
            code="PMFND013",
            provider=PROVIDER,
        )
    if "\\" in value or "\0" in value or "?" in value or "#" in value:
        raise ConnectorConfigError(
            "Foundry file path contains an unsupported character",
            code="PMFND014",
            provider=PROVIDER,
        )
    parts = value.rstrip("/").split("/")
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ConnectorConfigError(
            "Foundry file path contains an unsafe segment",
            code="PMFND015",
            provider=PROVIDER,
        )
    if not prefix and value.endswith("/"):
        raise ConnectorConfigError(
            "Foundry file_path must name a file", code="PMFND016", provider=PROVIDER
        )
    return value


def _token(context: Mapping[str, Any]) -> str:
    value = context.get("secret")
    if not isinstance(value, SecretValue):
        raise ConnectorConfigError(
            "Foundry requires a runtime SecretValue token",
            code="PMFND017",
            provider=PROVIDER,
        )
    token = value.value
    if not isinstance(token, str) or not token:
        raise ConnectorConfigError(
            "Foundry runtime token is empty or invalid",
            code="PMFND018",
            provider=PROVIDER,
        )
    return token


def _rid_path(rid: str) -> str:
    return urllib.parse.quote(rid, safe="")


def _path_path(path: str) -> str:
    return urllib.parse.quote(path, safe="/")


def _resource_identity(
    *, base_url: str, dataset_rid: str, branch_name: str, file_path: str
) -> str:
    """Return a stable opaque identity for one dataset-branch file."""
    parsed = urllib.parse.urlsplit(base_url)
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        host = "loopback"
    scheme = parsed.scheme.lower()
    port = parsed.port or (443 if scheme == "https" else 80)
    origin = f"{scheme}://{host}:{port}"
    payload = "\0".join((origin, dataset_rid, branch_name, file_path))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"foundry_file_resource/1:{digest}"


def _dataset_branch_identity(
    *, base_url: str, dataset_rid: str, branch_name: str
) -> str:
    """Return the stable mutation identity for a whole dataset branch view."""
    parsed = urllib.parse.urlsplit(base_url)
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        host = "loopback"
    scheme = parsed.scheme.lower()
    port = parsed.port or (443 if scheme == "https" else 80)
    origin = f"{scheme}://{host}:{port}"
    payload = "\0".join((origin, dataset_rid, branch_name, "dataset-branch"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"foundry_dataset_branch/1:{digest}"


@dataclass
class _FoundryClient:
    """Scoped HTTP requests; diagnostics never include credentials or bodies."""

    transport: Any | None = field(default=None, repr=False)

    @asynccontextmanager
    async def _client(
        self, cfg: Mapping[str, Any], context: Mapping[str, Any]
    ) -> AsyncGenerator[httpx2.AsyncClient, None]:
        base_url, _ = _base(cfg)
        timeout = _int_option(
            cfg.get("timeout_seconds"),
            name="timeout_seconds",
            default=DEFAULT_TIMEOUT,
            maximum=MAX_TIMEOUT,
        )
        headers = {"Authorization": f"Bearer {_token(context)}"}
        async with httpx2.AsyncClient(
            base_url=base_url,
            headers=headers,
            timeout=httpx2.Timeout(timeout),
            follow_redirects=False,
            transport=self.transport,
        ) as client:
            yield client

    async def _request(
        self,
        *,
        cfg: Mapping[str, Any],
        context: Mapping[str, Any],
        method: str,
        path: str,
        write: bool,
        params: Mapping[str, Any] | None = None,
        json_body: Any | None = None,
        content: bytes | None = None,
    ) -> httpx2.Response:
        try:
            async with self._client(cfg, context) as client:
                response = await client.request(
                    method,
                    path,
                    params=params,
                    json=json_body,
                    content=content,
                    headers=(
                        {"Content-Type": "application/octet-stream"}
                        if content is not None
                        else None
                    ),
                )
        except httpx2.TimeoutException as exc:
            error_type = ConnectorWriteError if write else ConnectorReadError
            raise error_type(
                "Foundry request timed out; operation outcome may require reconciliation",
                code="PMFND019",
                provider=PROVIDER,
                details={"effect_unknown": bool(write)},
            ) from exc
        except httpx2.HTTPError as exc:
            error_type = ConnectorWriteError if write else ConnectorReadError
            raise error_type(
                "Foundry request failed; response details were redacted",
                code="PMFND020",
                provider=PROVIDER,
                details={"effect_unknown": bool(write)},
            ) from exc
        if response.status_code >= 400:
            error_type = ConnectorWriteError if write else ConnectorReadError
            raise error_type(
                f"Foundry rejected the request (HTTP {response.status_code})",
                code=f"PMFND_HTTP_{response.status_code}",
                provider=PROVIDER,
                details={"status_code": response.status_code},
            )
        return response

    async def _list_files(
        self,
        *,
        cfg: Mapping[str, Any],
        context: Mapping[str, Any],
        transaction_rid: str | None = None,
        path_prefix: str | None = None,
        branch: bool = False,
        max_files: int = DEFAULT_MAX_FILES,
        first_page_only: bool = False,
    ) -> list[dict[str, Any]]:
        _, dataset_rid = _base(cfg)
        page_size = min(DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE)
        params: dict[str, Any] = {"pageSize": page_size}
        if transaction_rid:
            params["endTransactionRid"] = transaction_rid
        elif branch:
            params["branchName"] = cfg["branch_name"]
        if path_prefix:
            params["pathPrefix"] = path_prefix
        files: list[dict[str, Any]] = []
        token: str | None = None
        seen_tokens: set[str] = set()
        pages = 0
        while True:
            pages += 1
            if pages > (max_files // page_size) + 2:
                raise ConnectorReadError(
                    "Foundry file listing exceeded its page bound",
                    code="PMFND021",
                    provider=PROVIDER,
                )
            if token:
                params["pageToken"] = token
            response = await self._request(
                cfg=cfg,
                context=context,
                method="GET",
                path=f"/api/v2/datasets/{_rid_path(dataset_rid)}/files",
                write=False,
                params=params,
            )
            try:
                body: Any = response.json()
            except ValueError as exc:
                raise ConnectorReadError(
                    "Foundry file listing returned invalid JSON",
                    code="PMFND022",
                    provider=PROVIDER,
                ) from exc
            body_map: Mapping[str, Any] = (
                cast(Mapping[str, Any], body)
                if isinstance(body, Mapping)
                else cast(Mapping[str, Any], {})
            )
            raw_page: Any = body_map.get("data")
            if not isinstance(raw_page, list):
                raise ConnectorReadError(
                    "Foundry file listing omitted its data array",
                    code="PMFND023",
                    provider=PROVIDER,
                )
            page: list[Any] = cast(list[Any], raw_page)
            for item in page:
                if not isinstance(item, Mapping):
                    raise ConnectorReadError(
                        "Foundry file listing contained an invalid entry",
                        code="PMFND024",
                        provider=PROVIDER,
                    )
                file_entry = cast(Mapping[str, Any], item)
                if not isinstance(file_entry.get("path"), str):
                    raise ConnectorReadError(
                        "Foundry file listing contained an invalid entry",
                        code="PMFND024",
                        provider=PROVIDER,
                    )
                _safe_path(str(file_entry["path"]))
                files.append(dict(file_entry))
                if first_page_only:
                    return files
                if len(files) > max_files:
                    raise ConnectorReadError(
                        f"Foundry listing exceeds max_files ({max_files})",
                        code="PMFND025",
                        provider=PROVIDER,
                    )
            token_raw: Any = body_map.get("nextPageToken")
            token = str(token_raw) if token_raw else None
            if token is None:
                return files
            if token in seen_tokens:
                raise ConnectorReadError(
                    "Foundry returned a repeated pagination token",
                    code="PMFND026",
                    provider=PROVIDER,
                )
            seen_tokens.add(token)

    async def _file_content(
        self,
        *,
        cfg: Mapping[str, Any],
        context: Mapping[str, Any],
        path: str,
        transaction_rid: str | None = None,
        branch: bool = False,
        max_bytes: int,
    ) -> bytes:
        _, dataset_rid = _base(cfg)
        params: dict[str, Any] = {}
        if transaction_rid:
            params["endTransactionRid"] = transaction_rid
        elif branch:
            params["branchName"] = cfg["branch_name"]
        request_path = (
            f"/api/v2/datasets/{_rid_path(dataset_rid)}/files/"
            f"{_path_path(path)}/content"
        )
        if type(max_bytes) is not int or max_bytes < 1:
            raise ValueError("max_bytes must be a positive integer")
        try:
            async with (
                self._client(cfg, context) as client,
                client.stream("GET", request_path, params=params) as response,
            ):
                if response.status_code >= 400:
                    raise ConnectorReadError(
                        f"Foundry rejected the request (HTTP {response.status_code})",
                        code=f"PMFND_HTTP_{response.status_code}",
                        provider=PROVIDER,
                        details={"status_code": response.status_code},
                    )
                chunks: list[bytes] = []
                total_bytes = 0
                async for chunk in response.aiter_bytes():
                    total_bytes += len(chunk)
                    if total_bytes > max_bytes:
                        raise ConnectorReadError(
                            "Foundry file content exceeds max_bytes",
                            code="PMFND032",
                            provider=PROVIDER,
                        )
                    chunks.append(chunk)
                return b"".join(chunks)
        except httpx2.TimeoutException as exc:
            raise ConnectorReadError(
                "Foundry request timed out; operation outcome may require reconciliation",
                code="PMFND019",
                provider=PROVIDER,
                details={"effect_unknown": False},
            ) from exc
        except httpx2.HTTPError as exc:
            raise ConnectorReadError(
                "Foundry request failed; response details were redacted",
                code="PMFND020",
                provider=PROVIDER,
                details={"effect_unknown": False},
            ) from exc


@dataclass
class FoundrySourceConnector(_FoundryClient):
    """Read a bounded dataset view at a pinned transaction RID."""

    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name=PROVIDER,
            protocol=SOURCE_PROTOCOL,
            version=PACKAGE_VERSION,
            provider=PROVIDER,
            capabilities=(SOURCE_BATCH_SNAPSHOT, SOURCE_SCHEMA_DISCOVERY, IDEMPOTENCY),
            maturity=ConnectorMaturity.EXPERIMENTAL,
            metadata={"api": "foundry-datasets-v2", "snapshot": "pinned-transaction"},
            configuration_schema=deepcopy(SOURCE_CONFIG_SCHEMA),
        )

    async def resource_identities(
        self, *, binding: Mapping[str, Any], context: Mapping[str, Any]
    ) -> tuple[str, ...]:
        """Resolve the exact pinned files consumed by this source binding."""
        plan = await self.plan_read(binding=binding, context=context)
        intent = dict(plan.listing_intent)
        cfg = _config(binding, _SOURCE_KEYS)
        _, dataset = _base(cfg)
        transaction = str(intent["transaction_rid"])
        files = await self._list_files(
            cfg=cfg,
            context=context,
            transaction_rid=transaction,
            path_prefix=(
                str(intent["path_prefix"]) if intent.get("path_prefix") else None
            ),
            max_files=int(intent["max_files"]),
        )
        identities = {
            _resource_identity(
                base_url=str(intent["base_url"]),
                dataset_rid=dataset,
                branch_name=str(intent["branch_name"]),
                file_path=_safe_path(item.get("path")),
            )
            for item in files
        }
        branch_identity = _dataset_branch_identity(
            base_url=str(intent["base_url"]),
            dataset_rid=dataset,
            branch_name=str(intent["branch_name"]),
        )
        if identities:
            return tuple(sorted({branch_identity, *identities}))
        # An empty, pinned snapshot still has a verifiable identity. It is
        # intentionally distinct from every file identity, while preserving
        # the runtime's fail-closed requirement that providers return proof.
        empty_digest = hashlib.sha256(
            "\0".join(
                (
                    str(intent["base_url"]),
                    dataset,
                    str(intent["branch_name"]),
                    transaction,
                    str(intent.get("path_prefix") or ""),
                    "empty-snapshot",
                )
            ).encode("utf-8")
        ).hexdigest()
        return (branch_identity, f"foundry_empty_snapshot/1:{empty_digest}")

    async def plan_read(
        self, *, binding: Mapping[str, Any], context: Mapping[str, Any]
    ) -> SourcePlan:
        cfg = _config(binding, _SOURCE_KEYS)
        base_url, dataset = _base(cfg)
        transaction = cfg.get("transaction_rid")
        if not isinstance(transaction, str) or not transaction:
            raise ConnectorConfigError(
                "Foundry source requires a pinned transaction_rid",
                code="PMFND027",
                provider=PROVIDER,
            )
        mode = cfg.get("mode") or binding.get("mode") or "snapshot"
        if mode != "snapshot":
            raise ConnectorConfigError(
                "Foundry source only supports snapshot reads",
                code="PMFND056",
                provider=PROVIDER,
            )
        path_prefix = cfg.get("path_prefix")
        if path_prefix is not None:
            _safe_path(path_prefix, prefix=True)
        source_format = _format(cfg, binding)
        _encoding(cfg)
        _delimiter(cfg)
        options = {
            "base_url": base_url,
            "dataset_rid": dataset,
            "branch_name": cfg["branch_name"],
            "transaction_rid": transaction,
            "path_prefix": path_prefix,
            "format": source_format,
            "encoding": cfg.get("encoding", "utf-8"),
            "delimiter": cfg.get("delimiter", ","),
            "max_files": _int_option(
                cfg.get("max_files"),
                name="max_files",
                default=DEFAULT_MAX_FILES,
                maximum=MAX_FILES,
            ),
            "max_file_bytes": _int_option(
                cfg.get("max_file_bytes"),
                name="max_file_bytes",
                default=DEFAULT_FILE_BYTES,
                maximum=MAX_FILE_BYTES,
            ),
            "max_total_bytes": _int_option(
                cfg.get("max_total_bytes"),
                name="max_total_bytes",
                default=DEFAULT_TOTAL_BYTES,
                maximum=MAX_TOTAL_BYTES,
            ),
            "max_rows": _int_option(
                cfg.get("max_rows"),
                name="max_rows",
                default=DEFAULT_MAX_ROWS,
                maximum=MAX_ROWS,
            ),
            "batch_size": _int_option(
                cfg.get("batch_size"),
                name="batch_size",
                default=DEFAULT_BATCH_SIZE,
                maximum=MAX_BATCH_SIZE,
            ),
            "allow_empty": cfg.get("allow_empty", False),
            "timeout_seconds": _int_option(
                cfg.get("timeout_seconds"),
                name="timeout_seconds",
                default=DEFAULT_TIMEOUT,
                maximum=MAX_TIMEOUT,
            ),
        }
        if not isinstance(options["allow_empty"], bool):
            raise ConnectorConfigError(
                "allow_empty must be boolean", code="PMFND028", provider=PROVIDER
            )
        return SourcePlan(
            provider=PROVIDER,
            protocol=SOURCE_PROTOCOL,
            mode="snapshot",
            identity_scheme="foundry_file_sha256/1",
            listing_intent=options,
            config_fingerprint=fingerprint_public_config(cfg),
            root_ref=f"{dataset}@{transaction}",
            secret_refs=_secret_ref_names(binding),
        )

    async def preview(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
        max_rows: int,
        max_bytes: int,
    ) -> dict[str, Any]:
        """Read a bounded CSV sample from one exact pinned file resource.

        This method is intended for isolated preview workers. It accepts only
        the already-resolved saved binding and runtime context; callers must
        resolve an opaque resource ID to an exact ``path_prefix`` and pinned
        transaction before invoking it.
        """
        if type(max_rows) is not int or not 1 <= max_rows <= 100:
            raise ValueError("Foundry preview max_rows must be between 1 and 100")
        if type(max_bytes) is not int or not 256 <= max_bytes <= 64 * 1024:
            raise ValueError("Foundry preview max_bytes must be between 256 and 65536")
        cfg = _config(binding, _SOURCE_KEYS)
        plan = await self.plan_read(binding=binding, context=context)
        intent = plan.listing_intent
        path_prefix = intent.get("path_prefix")
        if not isinstance(path_prefix, str) or not path_prefix:
            raise ConnectorConfigError(
                "Foundry preview requires an exact saved file path",
                code="PMFND057",
                provider=PROVIDER,
            )
        resource_path = _safe_path(path_prefix)
        if intent.get("format") != "csv":
            raise ConnectorConfigError(
                "Foundry preview currently supports CSV resources",
                code="PMFND058",
                provider=PROVIDER,
            )
        transaction = str(intent["transaction_rid"])
        _, dataset = _base(cfg)
        transaction_response = await self._request(
            cfg=cfg,
            context=context,
            method="GET",
            path=(
                f"/api/v2/datasets/{_rid_path(dataset)}/transactions/"
                f"{_rid_path(transaction)}"
            ),
            write=False,
        )
        try:
            transaction_status = transaction_response.json().get("status")
        except (AttributeError, ValueError) as exc:
            raise ConnectorReadError(
                "Foundry transaction lookup returned invalid JSON",
                code="PMFND053",
                provider=PROVIDER,
            ) from exc
        if transaction_status != "COMMITTED":
            raise ConnectorReadError(
                "Foundry preview transaction is not committed",
                code="PMFND054",
                provider=PROVIDER,
            )
        files = await self._list_files(
            cfg=cfg,
            context=context,
            transaction_rid=transaction,
            path_prefix=resource_path,
            max_files=2,
        )
        if len(files) != 1 or files[0].get("path") != resource_path:
            raise ConnectorReadError(
                "Foundry preview resource did not resolve to one exact file",
                code="PMFND059",
                provider=PROVIDER,
            )
        byte_limit = min(
            max_bytes,
            int(intent["max_file_bytes"]),
            int(intent["max_total_bytes"]),
        )
        announced_size = files[0].get("sizeBytes")
        if announced_size is not None:
            try:
                size = int(announced_size)
            except (TypeError, ValueError) as exc:
                raise ConnectorReadError(
                    "Foundry preview file metadata has invalid sizeBytes",
                    code="PMFND031",
                    provider=PROVIDER,
                ) from exc
            if size < 0 or size > byte_limit:
                raise ConnectorReadError(
                    "Foundry preview file exceeds its byte limit",
                    code="PMFND032",
                    provider=PROVIDER,
                )
        payload = await self._file_content(
            cfg=cfg,
            context=context,
            path=resource_path,
            transaction_rid=transaction,
            max_bytes=byte_limit,
        )
        if len(payload) > byte_limit or (
            announced_size is not None and int(announced_size) != len(payload)
        ):
            raise ConnectorReadError(
                "Foundry preview content exceeds its declared bound",
                code="PMFND032",
                provider=PROVIDER,
            )
        try:
            decoded = payload.decode(str(intent["encoding"]), errors="strict")
            reader = csv.reader(
                io.StringIO(decoded), delimiter=str(intent["delimiter"])
            )
            try:
                header = next(reader)
            except StopIteration:
                header = []
            if not header or len(header) != len(set(header)):
                raise ValueError("CSV preview requires unique column names")
            rows: list[dict[str, str | None]] = []
            truncated = False
            for values in reader:
                if len(values) != len(header):
                    raise ValueError("CSV preview row has an invalid width")
                if len(rows) == max_rows:
                    truncated = True
                    break
                rows.append(dict(zip(header, values, strict=True)))
        except (UnicodeDecodeError, csv.Error, ValueError) as exc:
            raise ConnectorReadError(
                "Foundry CSV preview could not be parsed",
                code="PMFND051",
                provider=PROVIDER,
            ) from exc
        sensitive_name = re.compile(
            r"(?:password|passwd|secret|token|credential|api[_-]?key|access[_-]?key)",
            re.IGNORECASE,
        )
        return {
            "columns": [
                {
                    "name": name,
                    "logical_type": "string",
                    "sensitive": bool(sensitive_name.search(name)),
                }
                for name in header
            ],
            "rows": rows,
            "truncated": truncated,
        }

    async def read_batches(
        self,
        *,
        plan: SourcePlan,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> AsyncIterator[ReadBatch]:
        cfg = _config(binding, _SOURCE_KEYS)
        expected = await self.plan_read(binding=binding, context=context)
        if plan.to_dict() != expected.to_dict():
            raise ConnectorReadError(
                "Foundry source plan does not match its binding",
                code="PMFND029",
                provider=PROVIDER,
            )
        intent = dict(plan.listing_intent)
        transaction = str(intent.get("transaction_rid") or "")
        _, dataset = _base(cfg)
        transaction_response = await self._request(
            cfg=cfg,
            context=context,
            method="GET",
            path=(
                f"/api/v2/datasets/{_rid_path(dataset)}/transactions/"
                f"{_rid_path(transaction)}"
            ),
            write=False,
        )
        try:
            transaction_status = transaction_response.json().get("status")
        except (AttributeError, ValueError) as exc:
            raise ConnectorReadError(
                "Foundry transaction lookup returned invalid JSON",
                code="PMFND053",
                provider=PROVIDER,
            ) from exc
        if transaction_status != "COMMITTED":
            raise ConnectorReadError(
                "Foundry source transaction is not committed",
                code="PMFND054",
                provider=PROVIDER,
            )
        max_files = _int_option(
            intent.get("max_files"),
            name="max_files",
            default=DEFAULT_MAX_FILES,
            maximum=MAX_FILES,
        )
        max_file_bytes = _int_option(
            intent.get("max_file_bytes"),
            name="max_file_bytes",
            default=DEFAULT_FILE_BYTES,
            maximum=MAX_FILE_BYTES,
        )
        max_total_bytes = _int_option(
            intent.get("max_total_bytes"),
            name="max_total_bytes",
            default=DEFAULT_TOTAL_BYTES,
            maximum=MAX_TOTAL_BYTES,
        )
        files = await self._list_files(
            cfg=cfg,
            context=context,
            transaction_rid=transaction,
            path_prefix=(
                str(intent["path_prefix"]) if intent.get("path_prefix") else None
            ),
            max_files=max_files,
        )
        if not files and not intent.get("allow_empty"):
            raise ConnectorReadError(
                "Foundry source matched no files", code="PMFND030", provider=PROVIDER
            )
        announced_bytes = 0
        for item in files:
            raw_size = item.get("sizeBytes")
            if raw_size is not None:
                try:
                    size = int(raw_size)
                except (TypeError, ValueError) as exc:
                    raise ConnectorReadError(
                        "Foundry file metadata has invalid sizeBytes",
                        code="PMFND031",
                        provider=PROVIDER,
                    ) from exc
                if size < 0 or size > max_file_bytes:
                    raise ConnectorReadError(
                        f"Foundry file exceeds max_file_bytes ({max_file_bytes})",
                        code="PMFND032",
                        provider=PROVIDER,
                    )
                announced_bytes += size
                if announced_bytes > max_total_bytes:
                    raise ConnectorReadError(
                        f"Foundry listing exceeds max_total_bytes ({max_total_bytes})",
                        code="PMFND033",
                        provider=PROVIDER,
                    )

        identities: list[LandingFileIdentity] = []
        batch_identities: list[LandingFileIdentity] = []
        batch_records: list[dict[str, Any]] = []
        pending_batch: ReadBatch | None = None
        batch_index = 0
        row_count = 0
        total_bytes = 0
        encoding = _encoding(intent)
        delimiter = _delimiter(intent)
        source_format = str(intent["format"])
        batch_size = int(intent["batch_size"])
        max_rows = int(intent["max_rows"])
        for item in files:
            relative_path = str(item["path"])
            remaining_total_bytes = max_total_bytes - total_bytes
            if remaining_total_bytes <= 0:
                raise ConnectorReadError(
                    f"Foundry source exceeds max_total_bytes ({max_total_bytes})",
                    code="PMFND033",
                    provider=PROVIDER,
                )
            try:
                payload = await self._file_content(
                    cfg=cfg,
                    context=context,
                    path=relative_path,
                    transaction_rid=transaction,
                    max_bytes=min(max_file_bytes, remaining_total_bytes),
                )
            except ConnectorReadError as exc:
                if remaining_total_bytes < max_file_bytes and exc.code == "PMFND032":
                    raise ConnectorReadError(
                        f"Foundry source exceeds max_total_bytes ({max_total_bytes})",
                        code="PMFND033",
                        provider=PROVIDER,
                    ) from exc
                raise
            if len(payload) > max_file_bytes:
                raise ConnectorReadError(
                    f"Foundry file exceeds max_file_bytes ({max_file_bytes})",
                    code="PMFND032",
                    provider=PROVIDER,
                )
            announced_size = item.get("sizeBytes")
            if announced_size is not None and int(announced_size) != len(payload):
                raise ConnectorReadError(
                    "Foundry file content length changed after listing",
                    code="PMFND055",
                    provider=PROVIDER,
                )
            total_bytes += len(payload)
            if total_bytes > max_total_bytes:
                raise ConnectorReadError(
                    f"Foundry source exceeds max_total_bytes ({max_total_bytes})",
                    code="PMFND033",
                    provider=PROVIDER,
                )
            digest = hashlib.sha256(payload).hexdigest()
            identity = LandingFileIdentity(
                root_ref=str(plan.root_ref),
                relative_path=relative_path,
                size=len(payload),
                content_sha256=digest,
            )
            identities.append(identity)
            batch_identities.append(identity)
            try:
                decoded = payload.decode(encoding, errors="strict")
                for row in _iter_records(
                    decoded, source_format=source_format, delimiter=delimiter
                ):
                    row_count += 1
                    if row_count > max_rows:
                        raise ConnectorReadError(
                            f"Foundry source exceeds max_rows ({max_rows})",
                            code="PMFND035",
                            provider=PROVIDER,
                        )
                    batch_records.append(row)
                    if len(batch_records) == batch_size:
                        current_batch = ReadBatch(
                            records=tuple(batch_records),
                            batch_index=batch_index,
                            identities=tuple(batch_identities),
                            metadata={
                                "dataset_rid": intent["dataset_rid"],
                                "transaction_rid": transaction,
                                "record_count": len(batch_records),
                            },
                        )
                        batch_index += 1
                        batch_records.clear()
                        batch_identities.clear()
                        if pending_batch is not None:
                            yield pending_batch
                        pending_batch = current_batch
            except ConnectorReadError:
                raise
            except (
                UnicodeDecodeError,
                csv.Error,
                json.JSONDecodeError,
                ValueError,
            ) as exc:
                raise ConnectorReadError(
                    f"Foundry file {relative_path!r} could not be parsed as {source_format}",
                    code="PMFND034",
                    provider=PROVIDER,
                ) from exc
        manifest = LandingReadManifest(
            root_ref=str(plan.root_ref),
            identities=tuple(identities),
            mode="snapshot",
            metadata={
                "provider": PROVIDER,
                "dataset_rid": intent["dataset_rid"],
                "transaction_rid": transaction,
            },
        )
        if isinstance(context, dict):
            context["landing_read_manifest"] = manifest
        if pending_batch is not None and not batch_records and not batch_identities:
            yield ReadBatch(
                records=pending_batch.records,
                batch_index=pending_batch.batch_index,
                exhausted=True,
                identities=pending_batch.identities,
                metadata=pending_batch.metadata,
            )
            return
        if pending_batch is not None:
            yield pending_batch
        yield ReadBatch(
            records=tuple(batch_records),
            batch_index=batch_index,
            exhausted=True,
            identities=tuple(batch_identities),
            metadata={
                "dataset_rid": intent["dataset_rid"],
                "transaction_rid": transaction,
                "record_count": len(batch_records),
            },
        )

    async def propose_cursor(
        self,
        *,
        plan: SourcePlan,
        manifest: LandingReadManifest,
        context: Mapping[str, Any],
    ) -> CursorProposal | None:
        return None


@dataclass
class FoundrySinkConnector(_FoundryClient):
    """Stage and commit bounded CSV/JSON files through dataset transactions."""

    _sessions: dict[str, dict[str, Any]] = field(
        default_factory=lambda: dict[str, dict[str, Any]](), repr=False
    )

    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name=PROVIDER,
            protocol=SINK_PROTOCOL,
            version=PACKAGE_VERSION,
            provider=PROVIDER,
            capabilities=(
                WRITE_APPEND,
                WRITE_OVERWRITE,
                PUBLICATION_ATOMIC,
                TRANSACTIONS,
                RECONCILIATION,
                IDEMPOTENCY,
            ),
            maturity=ConnectorMaturity.EXPERIMENTAL,
            metadata={
                "api": "foundry-datasets-v2",
                "modes": ["append", "replace", "snapshot"],
                "commit": "dataset-transaction",
            },
            configuration_schema=deepcopy(SINK_CONFIG_SCHEMA),
        )

    async def resource_identities(
        self, *, binding: Mapping[str, Any], context: Mapping[str, Any]
    ) -> tuple[str, ...]:
        """Resolve the exact branch file the sink will publish."""
        plan = await self.plan_write(binding=binding, context=context)
        metadata = plan.metadata
        if metadata["mode"] == "snapshot":
            return (
                _dataset_branch_identity(
                    base_url=str(metadata["base_url"]),
                    dataset_rid=str(metadata["dataset_rid"]),
                    branch_name=str(metadata["branch_name"]),
                ),
            )
        return (
            _resource_identity(
                base_url=str(metadata["base_url"]),
                dataset_rid=str(metadata["dataset_rid"]),
                branch_name=str(metadata["branch_name"]),
                file_path=str(metadata["file_path"]),
            ),
        )

    async def plan_write(
        self, *, binding: Mapping[str, Any], context: Mapping[str, Any]
    ) -> SinkPlan:
        cfg = _config(binding, _SINK_KEYS)
        base_url, dataset = _base(cfg)
        mode = str(
            cfg.get("mode")
            or binding.get("mode")
            or context.get("write_mode")
            or "append"
        )
        aliases = {"overwrite": "snapshot", "update": "replace"}
        mode = aliases.get(mode, mode)
        if mode not in {"append", "replace", "snapshot"}:
            raise ConnectorConfigError(
                f"unsupported Foundry write mode {mode!r}; supported: append, replace, snapshot",
                code="PMFND036",
                provider=PROVIDER,
            )
        source_format = _format(cfg, binding)
        _encoding(cfg)
        _delimiter(cfg)
        effect_id = _effect_id(context, dataset, str(cfg["branch_name"]))
        if mode == "replace":
            file_path = _safe_path(cfg.get("file_path"))
        else:
            prefix = _safe_path(cfg.get("path_prefix", "etlantic/effects"), prefix=True)
            file_path = f"{prefix}/{effect_id}.{_FORMAT_EXT[source_format]}"
        max_rows = _int_option(
            cfg.get("max_rows"),
            name="max_rows",
            default=DEFAULT_MAX_ROWS,
            maximum=MAX_ROWS,
        )
        max_bytes = _int_option(
            cfg.get("max_bytes"),
            name="max_bytes",
            default=DEFAULT_FILE_BYTES,
            maximum=MAX_FILE_BYTES,
        )
        meta = {
            "base_url": base_url,
            "dataset_rid": dataset,
            "branch_name": cfg["branch_name"],
            "mode": mode,
            "file_path": file_path,
            "format": source_format,
            "encoding": cfg.get("encoding", "utf-8"),
            "delimiter": cfg.get("delimiter", ","),
            "max_rows": max_rows,
            "max_bytes": max_bytes,
            "timeout_seconds": _int_option(
                cfg.get("timeout_seconds"),
                name="timeout_seconds",
                default=DEFAULT_TIMEOUT,
                maximum=MAX_TIMEOUT,
            ),
            "effect_id": effect_id,
        }
        return SinkPlan(
            provider=PROVIDER,
            protocol=SINK_PROTOCOL,
            write_mode=mode,
            config_fingerprint=fingerprint_public_config(cfg),
            root_ref=f"{dataset}@{cfg['branch_name']}:{file_path}",
            secret_refs=_secret_ref_names(binding),
            metadata=meta,
        )

    async def begin_write(
        self,
        *,
        plan: SinkPlan,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> WriteSession:
        expected = await self.plan_write(binding=binding, context=context)
        if plan.to_dict() != expected.to_dict():
            raise ConnectorWriteError(
                "Foundry sink plan does not match its binding",
                code="PMFND057",
                provider=PROVIDER,
            )
        meta = dict(plan.metadata)
        dataset = str(meta["dataset_rid"])
        branch = str(meta["branch_name"])
        transaction_type = {
            "append": "APPEND",
            "replace": "UPDATE",
            "snapshot": "SNAPSHOT",
        }[str(meta["mode"])]
        effect_id = str(meta["effect_id"])
        session_metadata = {
            **meta,
            "effect_id": effect_id,
            "transaction_type": transaction_type,
            "transaction_rid": None,
            "payload_sha256": None,
        }
        response = await self._request(
            cfg=meta,
            context=context,
            method="POST",
            path=f"/api/v2/datasets/{_rid_path(dataset)}/transactions",
            write=True,
            params={"branchName": branch},
            json_body={"transactionType": transaction_type},
        )
        try:
            transaction: Any = response.json()
        except ValueError as exc:
            raise ConnectorWriteError(
                "Foundry transaction creation returned invalid JSON",
                code="PMFND037",
                provider=PROVIDER,
                details={"effect_unknown": True},
            ) from exc
        transaction_body: Mapping[str, Any] = (
            cast(Mapping[str, Any], transaction)
            if isinstance(transaction, Mapping)
            else cast(Mapping[str, Any], {})
        )
        transaction_rid = transaction_body.get("rid")
        if not isinstance(transaction_rid, str) or not transaction_rid:
            raise ConnectorWriteError(
                "Foundry transaction creation omitted its RID",
                code="PMFND038",
                provider=PROVIDER,
                details={"effect_unknown": True},
            )
        if transaction_body.get("status") not in {None, "OPEN"}:
            raise ConnectorWriteError(
                "Foundry did not create an open transaction",
                code="PMFND039",
                provider=PROVIDER,
            )
        session_metadata["transaction_rid"] = transaction_rid
        self._sessions[effect_id] = {
            "plan": plan,
            "context": context,
            "rows": [],
            "payload_bytes": 0,
            "csv_columns": None,
            "csv_header_bytes": 0,
            "payload": None,
            "status": "open",
            "metadata": session_metadata,
        }
        return WriteSession(
            session_id=effect_id,
            provider=PROVIDER,
            protocol=SINK_PROTOCOL,
            metadata=session_metadata,
        )

    async def write_batch(
        self, session: WriteSession, batch: Any, *, context: Mapping[str, Any]
    ) -> None:
        state = self._require(session.session_id)
        if state["status"] != "open":
            raise ConnectorWriteError(
                "Foundry write session is not open", code="PMFND040", provider=PROVIDER
            )
        rows: list[dict[str, Any]] = state["rows"]
        new_rows: list[dict[str, Any]] = []
        if isinstance(batch, Mapping):
            new_rows = [dict(cast(Mapping[str, Any], batch))]
        elif isinstance(batch, (tuple, list)):
            batch_rows = cast(Sequence[Any], batch)
            if any(not isinstance(row, Mapping) for row in batch_rows):
                raise ConnectorWriteError(
                    "Foundry sinks accept records as mappings",
                    code="PMFND041",
                    provider=PROVIDER,
                )
            new_rows.extend(
                dict(cast(Mapping[str, Any], row))
                for row in batch_rows
                if isinstance(row, Mapping)
            )
        else:
            raise ConnectorWriteError(
                "Foundry sinks accept records as mappings",
                code="PMFND041",
                provider=PROVIDER,
            )
        if len(rows) + len(new_rows) > int(state["plan"].metadata["max_rows"]):
            raise ConnectorWriteError(
                "Foundry sink exceeds max_rows", code="PMFND042", provider=PROVIDER
            )
        if new_rows:
            meta = state["plan"].metadata
            fmt = str(meta["format"])
            encoding = str(meta["encoding"])
            delimiter = str(meta["delimiter"])
            batch_payload = _serialize_records(
                new_rows, fmt=fmt, encoding=encoding, delimiter=delimiter
            )
            new_csv_columns: tuple[str, ...] | None = None
            new_csv_header_bytes = 0
            if fmt == "csv":
                columns = tuple(sorted(new_rows[0]))
                if state["csv_columns"] is None:
                    header_bytes = _csv_header_bytes(
                        columns, encoding=encoding, delimiter=delimiter
                    )
                    next_bytes = len(batch_payload)
                    new_csv_columns = columns
                    new_csv_header_bytes = header_bytes
                else:
                    if any(
                        tuple(sorted(row)) != state["csv_columns"] for row in new_rows
                    ):
                        raise ConnectorWriteError(
                            "Foundry CSV rows must have identical columns",
                            code="PMFND052",
                            provider=PROVIDER,
                        )
                    next_bytes = (
                        state["payload_bytes"]
                        + len(batch_payload)
                        - int(state["csv_header_bytes"])
                    )
            elif fmt == "json":
                # The serialized batch includes its own brackets. The first
                # batch becomes the complete document; later batches replace
                # the previous closing bracket with a comma and append the
                # new batch's interior plus its closing bracket.
                next_bytes = state["payload_bytes"] + len(batch_payload)
                if rows:
                    # Each independently encoded UTF-8-sig batch carries a
                    # BOM, while the combined JSON document has only one.
                    next_bytes -= 1 + _repeated_bom_bytes(encoding)
            else:
                next_bytes = state["payload_bytes"] + len(batch_payload)
                if rows:
                    # JSONL batches concatenate directly, so discard only the
                    # BOM repeated at the start of this subsequent batch.
                    next_bytes -= _repeated_bom_bytes(encoding)
            if next_bytes > int(meta["max_bytes"]):
                raise ConnectorWriteError(
                    "Foundry sink exceeds max_bytes",
                    code="PMFND043",
                    provider=PROVIDER,
                )
            state["payload_bytes"] = next_bytes
            if new_csv_columns is not None:
                state["csv_columns"] = new_csv_columns
                state["csv_header_bytes"] = new_csv_header_bytes
        rows.extend(new_rows)

    async def prepare(
        self, session: WriteSession, *, context: Mapping[str, Any]
    ) -> None:
        state = self._require(session.session_id)
        if state["status"] != "open":
            return
        meta = dict(state["plan"].metadata)
        rows: list[dict[str, Any]] = state["rows"]
        payload = _serialize_records(
            rows,
            fmt=str(meta["format"]),
            encoding=str(meta["encoding"]),
            delimiter=str(meta["delimiter"]),
        )
        if len(payload) > int(meta["max_bytes"]):
            raise ConnectorWriteError(
                "Foundry sink exceeds max_bytes", code="PMFND043", provider=PROVIDER
            )
        if state["payload_bytes"] and len(payload) != state["payload_bytes"]:
            raise ConnectorWriteError(
                "Foundry staged payload size changed during preparation",
                code="PMFND058",
                provider=PROVIDER,
            )
        digest = hashlib.sha256(payload).hexdigest()
        session_meta = state["metadata"]
        session_meta["payload_sha256"] = digest
        existing = await self._list_files(
            cfg=meta,
            context=state["context"],
            path_prefix=str(meta["file_path"]),
            branch=True,
        )
        exact = [item for item in existing if item.get("path") == meta["file_path"]]
        if exact:
            # A stable effect path makes append/snapshot replays discoverable
            # after worker restart. Equal bytes prove this exact effect already
            # landed; different bytes are an idempotency collision.
            prior_content = await self._file_content(
                cfg=meta,
                context=state["context"],
                path=str(meta["file_path"]),
                branch=True,
                max_bytes=int(meta["max_bytes"]),
            )
            prior_digest = hashlib.sha256(prior_content).hexdigest()
            if prior_digest == digest:
                await self._abort_transaction(meta, state["context"], session_meta)
                state["status"] = "committed"
                state["receipt"] = CommitReceipt(
                    status="committed",
                    session_id=session.session_id,
                    provider=PROVIDER,
                    publication_id=str(exact[0].get("transactionRid") or ""),
                    message="Foundry effect recovered from the committed file",
                    metadata={**session_meta, "replayed": True},
                )
                return
            if meta["mode"] != "replace":
                await self._abort_transaction(meta, state["context"], session_meta)
                raise ConnectorWriteError(
                    "Foundry effect path is already bound to different content",
                    code="PMFND044",
                    provider=PROVIDER,
                )
        transaction = str(session_meta["transaction_rid"])
        dataset = str(meta["dataset_rid"])
        response = await self._request(
            cfg=meta,
            context=state["context"],
            method="POST",
            path=(
                f"/api/v2/datasets/{_rid_path(dataset)}/files/"
                f"{_path_path(str(meta['file_path']))}/upload"
            ),
            write=True,
            params={
                "branchName": str(meta["branch_name"]),
                "transactionRid": transaction,
            },
            content=payload,
        )
        try:
            upload: Any = response.json()
        except ValueError as exc:
            raise ConnectorWriteError(
                "Foundry file upload returned invalid JSON",
                code="PMFND045",
                provider=PROVIDER,
                details={"effect_unknown": True},
            ) from exc
        if (
            not isinstance(upload, Mapping)
            or cast(Mapping[str, Any], upload).get("path") != meta["file_path"]
        ):
            raise ConnectorWriteError(
                "Foundry upload response did not confirm the requested file",
                code="PMFND046",
                provider=PROVIDER,
                details={"effect_unknown": True},
            )
        state["payload"] = payload
        state["status"] = "prepared"

    async def commit(
        self, session: WriteSession, *, context: Mapping[str, Any]
    ) -> CommitReceipt:
        state = self._require(session.session_id)
        if state["status"] == "committed":
            return state["receipt"]
        if state["status"] != "prepared":
            raise ConnectorWriteError(
                "Foundry write must be uploaded before commit",
                code="PMFND047",
                provider=PROVIDER,
            )
        meta = dict(state["plan"].metadata)
        transaction = str(state["metadata"]["transaction_rid"])
        response = await self._request(
            cfg=meta,
            context=state["context"],
            method="POST",
            path=(
                f"/api/v2/datasets/{_rid_path(str(meta['dataset_rid']))}/"
                f"transactions/{_rid_path(transaction)}/commit"
            ),
            write=True,
        )
        try:
            result: Any = response.json()
        except ValueError:
            result = None
        if isinstance(result, Mapping) and cast(Mapping[str, Any], result).get(
            "status"
        ) not in {
            "COMMITTED",
            None,
        }:
            raise ConnectorWriteError(
                "Foundry transaction did not report a committed status",
                code="PMFND048",
                provider=PROVIDER,
                details={"effect_unknown": True},
            )
        state["status"] = "committed"
        state["receipt"] = CommitReceipt(
            status="committed",
            session_id=session.session_id,
            provider=PROVIDER,
            publication_id=transaction,
            message="Foundry dataset transaction committed",
            metadata=dict(state["metadata"]),
        )
        return state["receipt"]

    async def abort(
        self, session: WriteSession, *, context: Mapping[str, Any]
    ) -> CommitReceipt:
        state = self._require(session.session_id)
        if state["status"] == "committed":
            return state["receipt"]
        meta = dict(state["plan"].metadata)
        try:
            return await self._abort_transaction(
                meta, state["context"], state["metadata"]
            )
        except ConnectorWriteError:
            state["status"] = "unknown"
            return CommitReceipt(
                status="unknown",
                session_id=session.session_id,
                provider=PROVIDER,
                message="Foundry transaction abort could not be confirmed",
                metadata=dict(state["metadata"]),
            )

    async def _abort_transaction(
        self,
        meta: Mapping[str, Any],
        context: Mapping[str, Any],
        session_metadata: dict[str, Any],
    ) -> CommitReceipt:
        transaction = session_metadata.get("transaction_rid")
        if not transaction:
            return CommitReceipt(
                status="unknown",
                session_id=str(session_metadata.get("effect_id") or ""),
                provider=PROVIDER,
                message="Foundry transaction identity is unavailable for abort",
                metadata=dict(session_metadata),
            )
        await self._request(
            cfg=meta,
            context=context,
            method="POST",
            path=(
                f"/api/v2/datasets/{_rid_path(str(meta['dataset_rid']))}/"
                f"transactions/{_rid_path(str(transaction))}/abort"
            ),
            write=True,
        )
        session_metadata["status"] = "ABORTED"
        return CommitReceipt(
            status="rolled_back",
            session_id=str(session_metadata.get("effect_id") or ""),
            provider=PROVIDER,
            message="Foundry transaction aborted",
            metadata=dict(session_metadata),
        )

    async def reconcile(
        self, receipt: CommitReceipt, *, context: Mapping[str, Any]
    ) -> ReconciliationResult:
        meta = dict(receipt.metadata or {})
        dataset = meta.get("dataset_rid")
        if not dataset or not meta.get("base_url"):
            return ReconciliationResult(
                status="unknown", message="Foundry receipt lacks its dataset identity"
            )
        transaction = meta.get("transaction_rid")
        if transaction:
            try:
                response = await self._request(
                    cfg=meta,
                    context=context,
                    method="GET",
                    path=(
                        f"/api/v2/datasets/{_rid_path(str(dataset))}/transactions/"
                        f"{_rid_path(str(transaction))}"
                    ),
                    write=False,
                )
                tx: Any = response.json()
            except Exception:
                return ReconciliationResult(
                    status="unknown", message="Foundry transaction state is unavailable"
                )
            status = (
                cast(Mapping[str, Any], tx).get("status")
                if isinstance(tx, Mapping)
                else None
            )
            if status == "COMMITTED":
                return ReconciliationResult(
                    status="committed",
                    publication_id=str(transaction),
                    message="Foundry transaction is committed",
                    metadata={**meta, "status": status},
                )
            if status == "ABORTED":
                return ReconciliationResult(
                    status="rolled_back",
                    publication_id=str(transaction),
                    message="Foundry transaction is aborted",
                    metadata={**meta, "status": status},
                )
            return ReconciliationResult(
                status="unknown",
                publication_id=str(transaction),
                message="Foundry transaction remains open or has an unknown status",
                metadata={**meta, "status": status},
            )
        # If transaction creation's acknowledgement was lost, only a visible
        # matching stable effect file proves publication. Absence is unknown:
        # the remote transaction may still be open.
        effect_path = meta.get("file_path")
        if not effect_path or not meta.get("payload_sha256"):
            return ReconciliationResult(
                status="unknown", message="Foundry transaction identity is unavailable"
            )
        try:
            files = await self._list_files(
                cfg=meta,
                context=context,
                path_prefix=str(effect_path),
                branch=True,
                max_files=10,
            )
            matches = [item for item in files if item.get("path") == effect_path]
            if not matches:
                return ReconciliationResult(
                    status="unknown",
                    message="Foundry effect is not visible; an open transaction may remain",
                    metadata={"effect_id": meta.get("effect_id")},
                )
            payload = await self._file_content(
                cfg=meta,
                context=context,
                path=str(effect_path),
                branch=True,
                max_bytes=_int_option(
                    meta.get("max_bytes"),
                    name="max_bytes",
                    default=DEFAULT_FILE_BYTES,
                    maximum=MAX_FILE_BYTES,
                ),
            )
        except Exception:
            return ReconciliationResult(
                status="unknown",
                message="Foundry effect could not be read for reconciliation",
            )
        digest = hashlib.sha256(payload).hexdigest()
        if digest != meta["payload_sha256"]:
            return ReconciliationResult(
                status="unknown",
                message="Foundry effect path contains different content",
            )
        return ReconciliationResult(
            status="committed",
            publication_id=str(matches[0].get("transactionRid") or ""),
            message="Foundry effect file matches the submitted content",
            metadata={**meta, "reconciled_by": "effect_file"},
        )

    async def cleanup(
        self, receipt: CommitReceipt, *, context: Mapping[str, Any]
    ) -> CleanupReceipt:
        return CleanupReceipt(
            status="skipped", message="committed Foundry files are immutable"
        )

    def _require(self, effect_id: str) -> dict[str, Any]:
        state = self._sessions.get(effect_id)
        if state is None:
            raise ConnectorWriteError(
                "unknown Foundry write session", code="PMFND049", provider=PROVIDER
            )
        return state


@dataclass
class FoundryStorageConnector(_FoundryClient):
    """Read-only file listing and CSV header inspection for a dataset branch."""

    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name=PROVIDER,
            protocol=STORAGE_PROTOCOL,
            version=PACKAGE_VERSION,
            provider=PROVIDER,
            capabilities=(SOURCE_SCHEMA_DISCOVERY,),
            maturity=ConnectorMaturity.EXPERIMENTAL,
            metadata={"api": "foundry-datasets-v2", "read_only_inspection": True},
            configuration_schema=deepcopy(STORAGE_CONFIG_SCHEMA),
        )

    async def list_catalog(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """List a bounded page of files in the configured dataset branch."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        cfg = _config(binding, _STORAGE_KEYS)
        _, dataset = _base(cfg)
        provider_cursor = self._decode_catalog_cursor(cursor)
        files, next_provider_cursor = await self._list_catalog_page(
            cfg=cfg,
            context=context,
            limit=limit,
            cursor=provider_cursor,
            path_prefix=(
                _safe_path(cfg["path_prefix"], prefix=True)
                if cfg.get("path_prefix")
                else None
            ),
            branch=True,
        )
        has_more = next_provider_cursor is not None
        return {
            "schema": "etlantic.connector_resource_page/1",
            "provider": PROVIDER,
            "items": [
                {"resource_id": str(item["path"]), "kind": "file"} for item in files
            ],
            "next_cursor": (
                self._encode_catalog_cursor(next_provider_cursor)
                if next_provider_cursor is not None
                else None
            ),
            "has_more": has_more,
            "metadata": {"dataset_rid": dataset, "branch_name": cfg["branch_name"]},
        }

    async def _list_catalog_page(
        self,
        *,
        cfg: Mapping[str, Any],
        context: Mapping[str, Any],
        limit: int,
        cursor: str | None,
        path_prefix: str | None,
        branch: bool,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Fetch one provider page so catalog paging work stays page-bounded."""
        _, dataset_rid = _base(cfg)
        params: dict[str, Any] = {"pageSize": limit}
        if branch:
            params["branchName"] = cfg["branch_name"]
        if path_prefix:
            params["pathPrefix"] = path_prefix
        if cursor is not None:
            params["pageToken"] = cursor
        response = await self._request(
            cfg=cfg,
            context=context,
            method="GET",
            path=f"/api/v2/datasets/{_rid_path(dataset_rid)}/files",
            write=False,
            params=params,
        )
        try:
            body: Any = response.json()
        except ValueError as exc:
            raise ConnectorReadError(
                "Foundry file listing returned invalid JSON",
                code="PMFND022",
                provider=PROVIDER,
            ) from exc
        body_map: Mapping[str, Any] = (
            cast(Mapping[str, Any], body)
            if isinstance(body, Mapping)
            else cast(Mapping[str, Any], {})
        )
        raw_page: Any = body_map.get("data")
        if not isinstance(raw_page, list):
            raise ConnectorReadError(
                "Foundry file listing returned an invalid or oversized page",
                code="PMFND023",
                provider=PROVIDER,
            )
        page_value: list[Any] = cast(list[Any], raw_page)
        if len(page_value) > limit:
            raise ConnectorReadError(
                "Foundry file listing returned an invalid or oversized page",
                code="PMFND023",
                provider=PROVIDER,
            )
        page: list[dict[str, Any]] = []
        for raw_file in page_value:
            if not isinstance(raw_file, Mapping):
                raise ConnectorReadError(
                    "Foundry file listing contained an invalid entry",
                    code="PMFND024",
                    provider=PROVIDER,
                )
            file_entry = cast(Mapping[str, Any], raw_file)
            file_path = file_entry.get("path")
            if not isinstance(file_path, str):
                raise ConnectorReadError(
                    "Foundry file listing contained an invalid entry",
                    code="PMFND024",
                    provider=PROVIDER,
                )
            _safe_path(file_path)
            page.append(dict(file_entry))
        raw_cursor = body_map.get("nextPageToken")
        if raw_cursor is not None and not isinstance(raw_cursor, str):
            raise ConnectorReadError(
                "Foundry returned an invalid page cursor",
                code="PMFND027",
                provider=PROVIDER,
            )
        next_cursor = raw_cursor or None
        if next_cursor is not None and next_cursor == cursor:
            raise ConnectorReadError(
                "Foundry returned a repeated pagination token",
                code="PMFND026",
                provider=PROVIDER,
            )
        return page, next_cursor

    @staticmethod
    def _encode_catalog_cursor(cursor: str) -> str:
        encoded = base64.urlsafe_b64encode(cursor.encode("utf-8")).decode("ascii")
        encoded = encoded.rstrip("=")
        if not 1 <= len(encoded) <= 256:
            raise ConnectorReadError(
                "Foundry catalog cursor exceeds the supported bound",
                code="PMFND027",
                provider=PROVIDER,
            )
        return encoded

    @staticmethod
    def _decode_catalog_cursor(cursor: str | None) -> str | None:
        if cursor is None:
            return None
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", cursor):
            raise ValueError("catalog cursor is invalid")
        padded = cursor + "=" * (-len(cursor) % 4)
        try:
            return base64.b64decode(padded, altchars=b"-_", validate=True).decode(
                "utf-8"
            )
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError("catalog cursor is invalid") from exc

    async def inspect_schema(
        self, *, binding: Mapping[str, Any], context: Mapping[str, Any]
    ) -> SchemaInspection:
        cfg = _config(binding, _STORAGE_KEYS)
        _, dataset = _base(cfg)
        files = await self._list_files(
            cfg=cfg,
            context=context,
            path_prefix=(
                _safe_path(cfg["path_prefix"], prefix=True)
                if cfg.get("path_prefix")
                else None
            ),
            branch=True,
            first_page_only=True,
        )
        fields: tuple[dict[str, Any], ...] = ()
        if files:
            path = str(files[0]["path"])
            max_file_bytes = _int_option(
                cfg.get("max_file_bytes"),
                name="max_file_bytes",
                default=DEFAULT_FILE_BYTES,
                maximum=MAX_FILE_BYTES,
            )
            raw = await self._file_content(
                cfg=cfg,
                context=context,
                path=path,
                branch=True,
                max_bytes=max_file_bytes,
            )
            if _format(cfg, binding) == "csv":
                try:
                    decoded = raw.decode(_encoding(cfg), errors="strict")
                    reader = csv.reader(io.StringIO(decoded), delimiter=_delimiter(cfg))
                    first_row = next(reader, None)
                    headers: list[str] = first_row if first_row is not None else []
                except (UnicodeDecodeError, csv.Error) as exc:
                    raise ConnectorReadError(
                        "Foundry CSV header could not be inspected",
                        code="PMFND051",
                        provider=PROVIDER,
                    ) from exc
                fields = tuple(
                    {"name": header, "type": "string", "nullable": True}
                    for header in headers
                )
        return SchemaInspection(
            provider=PROVIDER,
            fields=fields,
            row_estimate=None,
            metadata={
                "dataset_rid": dataset,
                "branch_name": cfg["branch_name"],
                "sample_path": str(files[0]["path"]) if files else None,
                "inspection": "read_only",
            },
        )


def _effect_id(context: Mapping[str, Any], dataset: str, branch: str) -> str:
    supplied = context.get("effect_id")
    if supplied is not None:
        raw = str(supplied)
    else:
        raw = f"{context.get('run_id') or 'unscoped'}:{context.get('node') or 'sink'}:{dataset}:{branch}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _iter_records(
    text: str, *, source_format: str, delimiter: str
) -> Iterator[dict[str, Any]]:
    if source_format == "csv":
        reader: csv.DictReader[str] = csv.DictReader(
            io.StringIO(text, newline=""), delimiter=delimiter
        )
        header = reader.fieldnames
        if header is None:
            return
        if len(set(header)) != len(header) or any(not field for field in header):
            raise ValueError("CSV headers must be present and unique")
        for row in cast(Iterable[Mapping[str, Any]], reader):
            yield dict(row)
        return
    if source_format == "json":
        decoder = json.JSONDecoder()
        index = len(text) - len(text.lstrip())
        if index >= len(text) or text[index] != "[":
            raise ValueError("JSON file must contain an array of objects")
        index += 1
        while index < len(text) and text[index].isspace():
            index += 1
        if index < len(text) and text[index] == "]":
            index += 1
            if text[index:].strip():
                raise ValueError("JSON file must contain an array of objects")
            return
        while index < len(text):
            row, index = decoder.raw_decode(text, index)
            if not isinstance(row, Mapping):
                raise ValueError("JSON file must contain an array of objects")
            yield dict(cast(Mapping[str, Any], row))
            while index < len(text) and text[index].isspace():
                index += 1
            if index >= len(text):
                raise ValueError("JSON file must contain an array of objects")
            separator = text[index]
            index += 1
            if separator == "]":
                if text[index:].strip():
                    raise ValueError("JSON file must contain an array of objects")
                return
            if separator != ",":
                raise ValueError("JSON file must contain an array of objects")
            while index < len(text) and text[index].isspace():
                index += 1
        raise ValueError("JSON file must contain an array of objects")
    for line in io.StringIO(text):
        if not line.strip():
            continue
        decoded: Any = json.loads(line)
        if not isinstance(decoded, Mapping):
            raise ValueError("JSONL lines must contain objects")
        yield dict(cast(Mapping[str, Any], decoded))


def _serialize_records(
    rows: Sequence[Mapping[str, Any]], *, fmt: str, encoding: str, delimiter: str
) -> bytes:
    if fmt == "csv":
        if not rows:
            return b""
        if any(
            not isinstance(column, str) or not column
            for row in rows
            for column in cast(Iterable[Any], row)
        ):
            raise ConnectorWriteError(
                "Foundry CSV column names must be nonempty strings",
                code="PMFND052",
                provider=PROVIDER,
            )
        columns: list[str] = sorted({column for row in rows for column in row})
        if any(set(row) != set(columns) for row in rows):
            raise ConnectorWriteError(
                "Foundry CSV rows must have identical columns",
                code="PMFND052",
                provider=PROVIDER,
            )
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(
            stream, fieldnames=columns, delimiter=delimiter, lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    column: (
                        json.dumps(
                            row[column],
                            sort_keys=True,
                            separators=(",", ":"),
                            ensure_ascii=False,
                        )
                        if isinstance(row[column], (dict, list, tuple))
                        else row[column]
                    )
                    for column in columns
                }
            )
        return stream.getvalue().encode(encoding)
    if fmt == "json":
        value = json.dumps(
            list(rows), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
    else:
        value = "".join(
            json.dumps(
                dict(row), sort_keys=True, separators=(",", ":"), ensure_ascii=False
            )
            + "\n"
            for row in rows
        )
    return value.encode(encoding)


def _csv_header_bytes(columns: Sequence[str], *, encoding: str, delimiter: str) -> int:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter=delimiter, lineterminator="\n")
    writer.writerow(columns)
    return len(stream.getvalue().encode(encoding))


def _repeated_bom_bytes(encoding: str) -> int:
    normalized = encoding.lower().replace("_", "-")
    return len(b"\xef\xbb\xbf") if normalized == "utf-8-sig" else 0


def create_source() -> FoundrySourceConnector:
    return FoundrySourceConnector()


def create_sink() -> FoundrySinkConnector:
    return FoundrySinkConnector()


def create_storage() -> FoundryStorageConnector:
    return FoundryStorageConnector()


__all__ = [
    "FoundrySinkConnector",
    "FoundrySourceConnector",
    "FoundryStorageConnector",
    "create_sink",
    "create_source",
    "create_storage",
]
