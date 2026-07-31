"""Local landing-zone source connector (stdlib CSV directory/glob)."""

from __future__ import annotations

import csv
import fnmatch
import hashlib
import os
import unicodedata
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from etlantic.connectors.capabilities import LOCAL_FILES_CAPABILITIES
from etlantic.connectors.checkpoint import (
    advance_landing_checkpoint,
    checkpoint_path_for,
    empty_checkpoint,
    landing_checkpoint_lease,
    load_landing_checkpoint,
)
from etlantic.connectors.errors import (
    ConnectorCheckpointError,
    ConnectorConfigError,
    ConnectorReadError,
)
from etlantic.connectors.maturity import ConnectorMaturity
from etlantic.connectors.models import (
    SOURCE_PROTOCOL,
    CleanupReceipt,
    ConnectorInfo,
    CursorProposal,
    LandingCheckpoint,
    LandingFileIdentity,
    LandingReadManifest,
    ReadBatch,
    SourcePlan,
    fingerprint_public_config,
)
from etlantic.io_policy import SafeIoPolicy, resolve_under_policy
from etlantic.storage.protocol import as_records

PROVIDER_NAME = "local-files"
DEFAULT_MAX_FILES = 10_000
DEFAULT_MAX_FILE_BYTES = 64 * 1024 * 1024
DEFAULT_MAX_TOTAL_BYTES = 256 * 1024 * 1024
DEFAULT_MAX_ROWS = 1_000_000


@dataclass
class LocalFilesSourceConnector:
    """Directory/glob CSV landing-zone source (snapshot + incremental)."""

    name: str = PROVIDER_NAME
    allow_recursive_glob: bool = False
    max_files: int = DEFAULT_MAX_FILES
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES
    max_rows: int = DEFAULT_MAX_ROWS
    _last_manifest: LandingReadManifest | None = field(default=None, repr=False)
    _last_proposal: CursorProposal | None = field(default=None, repr=False)
    _lease_checkpoint: Path | None = field(default=None, repr=False)
    _lease_policy: SafeIoPolicy | None = field(default=None, repr=False)
    _lease_base: LandingCheckpoint | None = field(default=None, repr=False)
    _lease_cm: Any = field(default=None, repr=False)

    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name=self.name,
            protocol=SOURCE_PROTOCOL,
            version="0.38.0",
            provider=PROVIDER_NAME,
            capabilities=tuple(sorted(LOCAL_FILES_CAPABILITIES)),
            maturity=ConnectorMaturity.PREVIEW,
            metadata={"stdlib": True, "promotion": "preview"},
        )

    async def plan_read(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> SourcePlan:
        cfg = _public_config(binding)
        mode = str(cfg.get("mode") or binding.get("mode") or "snapshot")
        if mode not in {"snapshot", "incremental"}:
            raise ConnectorConfigError(
                f"Unsupported local-files mode {mode!r}",
                code="PMCONN701",
                provider=PROVIDER_NAME,
            )
        glob_pat = str(cfg.get("glob") or binding.get("glob") or "*.csv")
        _validate_glob(glob_pat, allow_recursive=self.allow_recursive_glob)
        root_ref = str(
            cfg.get("root_ref")
            or binding.get("root_ref")
            or binding.get("root")
            or "landing"
        )
        fmt = str(cfg.get("format") or binding.get("format") or "csv")
        if fmt != "csv":
            raise ConnectorConfigError(
                f"local-files supports format=csv only; got {fmt!r}",
                code="PMCONN702",
                provider=PROVIDER_NAME,
            )
        checkpoint = cfg.get("checkpoint") or binding.get("checkpoint")
        if mode == "incremental" and not checkpoint:
            raise ConnectorConfigError(
                "mode=incremental requires checkpoint",
                code="PMCONN703",
                provider=PROVIDER_NAME,
            )
        return SourcePlan(
            provider=PROVIDER_NAME,
            protocol=SOURCE_PROTOCOL,
            mode=mode,  # type: ignore[arg-type]
            identity_scheme="landing_file_sha256/1",
            listing_intent={
                "root_ref": root_ref,
                "root": cfg.get("root") or binding.get("root"),
                "glob": glob_pat,
                "format": fmt,
                "consume": cfg.get("consume") or binding.get("consume") or "none",
                "empty_match": cfg.get("empty_match")
                or binding.get("empty_match")
                or "fail",
            },
            required_capabilities=tuple(
                str(x)
                for x in (
                    binding.get("required_capabilities")
                    or cfg.get("required_capabilities")
                    or ()
                )
            ),
            config_fingerprint=fingerprint_public_config(cfg),
            checkpoint_ref=str(checkpoint) if checkpoint else None,
            root_ref=root_ref,
            secret_refs=tuple(
                sorted(str(k) for k in (binding.get("secret_refs") or {}))
            ),
        )

    async def read_batches(
        self,
        *,
        plan: SourcePlan,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> AsyncIterator[ReadBatch]:
        policy = _require_policy(context)
        cfg = _public_config(binding)
        intent = dict(plan.listing_intent)
        root_rel = str(
            intent.get("root") or cfg.get("root") or binding.get("root") or "."
        )
        glob_pat = str(intent.get("glob") or "*.csv")
        root_ref = str(plan.root_ref or intent.get("root_ref") or "landing")
        mode = str(plan.mode or "snapshot")
        empty_match = str(intent.get("empty_match") or "fail")
        physical_root = _resolve_root(root_rel, policy, context)

        identities = list_landing_files(
            physical_root,
            glob_pat,
            root_ref=root_ref,
            policy=policy,
            allow_recursive=self.allow_recursive_glob,
            max_files=self.max_files,
            max_file_bytes=self.max_file_bytes,
            max_total_bytes=self.max_total_bytes,
            run_id=str(context.get("run_id") or "local-files"),
        )

        checkpoint: LandingCheckpoint | None = None
        if mode == "incremental":
            checkpoint = await self._prepare_incremental(
                plan=plan,
                binding=binding,
                context=context,
                policy=policy,
                identities=identities,
            )
            committed = set(checkpoint.committed_identities)
            identities = [i for i in identities if i.identity_key not in committed]

        if not identities and empty_match == "fail":
            raise ConnectorReadError(
                "local-files empty match (no files selected)",
                code="PMCONN710",
                provider=PROVIDER_NAME,
            )

        manifest = LandingReadManifest(
            root_ref=root_ref,
            identities=tuple(identities),
            mode=mode,  # type: ignore[arg-type]
            metadata={"provider": PROVIDER_NAME},
        )
        self._last_manifest = manifest
        context_mut = context if isinstance(context, dict) else None
        if context_mut is not None:
            context_mut["landing_read_manifest"] = manifest

        records = read_csv_identities(
            physical_root,
            identities,
            policy=policy,
            contract_type=context.get("contract_type"),
            max_rows=self.max_rows,
            max_file_bytes=self.max_file_bytes,
            run_id=str(context.get("run_id") or "local-files"),
        )
        yield ReadBatch(
            records=tuple(records),
            batch_index=0,
            exhausted=True,
            identities=tuple(identities),
            metadata={"manifest_fingerprint": manifest.fingerprint},
        )

    async def propose_cursor(
        self,
        *,
        plan: SourcePlan,
        manifest: LandingReadManifest,
        context: Mapping[str, Any],
    ) -> CursorProposal | None:
        if plan.mode != "incremental":
            return None
        proposal = CursorProposal(
            subject_id=str(plan.checkpoint_ref or plan.root_ref or "landing"),
            candidate=manifest.fingerprint,
            identities=manifest.identities,
            generation=(
                self._lease_base.generation if self._lease_base is not None else None
            ),
            metadata={"provider": PROVIDER_NAME},
        )
        self._last_proposal = proposal
        return proposal

    async def commit_ledger(
        self,
        *,
        publication_id: str | None,
        context: Mapping[str, Any],
    ) -> LandingCheckpoint | None:
        """Advance ledger only after sink CommitReceipt.status == committed."""
        if self._lease_base is None or self._lease_checkpoint is None:
            return None
        if self._last_manifest is None or not self._last_manifest.identities:
            self._release_lease()
            return self._lease_base
        policy = self._lease_policy or _require_policy(context)
        keys = tuple(i.identity_key for i in self._last_manifest.identities)
        updated = advance_landing_checkpoint(
            self._lease_checkpoint,
            policy=policy,
            base=self._lease_base,
            new_identity_keys=keys,
            publication_id=publication_id,
            manifest_fingerprint=self._last_manifest.fingerprint,
            run_id=str(context.get("run_id") or "local-files"),
        )
        self._lease_base = updated
        return updated

    async def consume_after_commit(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> CleanupReceipt:
        """Apply consume policy after ledger advance."""
        cfg = _public_config(binding)
        consume = str(cfg.get("consume") or binding.get("consume") or "none").lower()
        if consume in {"none", "ledger"}:
            self._release_lease()
            return CleanupReceipt(status="skipped", consume=consume)  # type: ignore[arg-type]
        if consume != "rename_done":
            self._release_lease()
            raise ConnectorConfigError(
                f"Unsupported consume policy {consume!r}",
                code="PMCONN720",
                provider=PROVIDER_NAME,
            )
        if self._last_manifest is None or not self._last_manifest.identities:
            self._release_lease()
            return CleanupReceipt(status="skipped", consume="rename_done")
        policy = _require_policy(context)
        intent_root = str(cfg.get("root") or binding.get("root") or ".")
        physical_root = _resolve_root(intent_root, policy, context)
        archived: list[str] = []
        try:
            for identity in self._last_manifest.identities:
                src = physical_root / Path(identity.relative_path)
                dest_dir = physical_root / ".done"
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / Path(identity.relative_path).name
                if dest.exists():
                    raise ConnectorReadError(
                        f"Archive collision for {identity.relative_path}",
                        code="PMCONN721",
                        provider=PROVIDER_NAME,
                    )
                # Refuse cross-device claims: same parent tree only.
                if src.resolve().parent != physical_root.resolve() and not str(
                    src.resolve()
                ).startswith(str(physical_root.resolve()) + os.sep):
                    raise ConnectorReadError(
                        "Cross-filesystem archive refused",
                        code="PMCONN722",
                        provider=PROVIDER_NAME,
                    )
                os.replace(src, dest)
                archived.append(identity.relative_path)
        except ConnectorReadError:
            self._release_lease()
            raise
        except OSError as exc:
            self._release_lease()
            return CleanupReceipt(
                status="failed",
                consume="rename_done",
                archived=tuple(archived),
                message=str(exc),
            )
        self._release_lease()
        return CleanupReceipt(
            status="completed",
            consume="rename_done",
            archived=tuple(archived),
        )

    def discard_proposal(self) -> None:
        """Drop staged cursor / release lease without advancing ledger."""
        self._last_proposal = None
        self._release_lease()

    async def _prepare_incremental(
        self,
        *,
        plan: SourcePlan,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
        policy: SafeIoPolicy,
        identities: Sequence[LandingFileIdentity],
    ) -> LandingCheckpoint:
        del identities  # selection happens after load
        cfg = _public_config(binding)
        checkpoint_name = str(plan.checkpoint_ref or cfg.get("checkpoint") or "")
        root_rel = str(cfg.get("root") or binding.get("root") or ".")
        physical_root = _resolve_root(root_rel, policy, context)
        path = checkpoint_path_for(physical_root, checkpoint_name)
        self._lease_cm = landing_checkpoint_lease(
            path,
            policy=policy,
            run_id=str(context.get("run_id") or "local-files"),
        )
        leased = self._lease_cm.__enter__()
        self._lease_checkpoint = leased
        self._lease_policy = policy
        loaded = load_landing_checkpoint(
            leased, policy=policy, run_id=str(context.get("run_id") or "local-files")
        )
        fingerprint = plan.config_fingerprint or ""
        if loaded is None:
            base = empty_checkpoint(
                pipeline_id=str(context.get("pipeline_id") or ""),
                extract_id=str(context.get("node") or context.get("extract_id") or ""),
                binding_id=str(binding.get("binding") or binding.get("name") or ""),
                binding_fingerprint=fingerprint,
            )
            self._lease_base = base
            return base
        if (
            loaded.binding_fingerprint
            and fingerprint
            and loaded.binding_fingerprint != fingerprint
        ):
            self._release_lease()
            raise ConnectorCheckpointError(
                "Checkpoint binding fingerprint mismatch; reset required",
                code="PMCONN730",
                provider=PROVIDER_NAME,
            )
        self._lease_base = loaded
        return loaded

    def _release_lease(self) -> None:
        cm = self._lease_cm
        self._lease_cm = None
        self._lease_checkpoint = None
        self._lease_policy = None
        if cm is not None:
            with suppress(Exception):
                cm.__exit__(None, None, None)


def create_local_files_source() -> LocalFilesSourceConnector:
    """Entry-point factory for ``etlantic.source_connectors``."""
    return LocalFilesSourceConnector()


def _public_config(binding: Mapping[str, Any]) -> dict[str, Any]:
    raw = binding.get("config")
    if isinstance(raw, dict):
        return dict(raw)
    # Lift known top-level keys into public config.
    keys = (
        "format",
        "mode",
        "glob",
        "root",
        "root_ref",
        "consume",
        "checkpoint",
        "empty_match",
        "required_capabilities",
    )
    return {k: binding[k] for k in keys if k in binding and binding[k] is not None}


def _require_policy(context: Mapping[str, Any]) -> SafeIoPolicy:
    policy = context.get("safe_io")
    if isinstance(policy, SafeIoPolicy):
        return policy
    if isinstance(policy, dict):
        return SafeIoPolicy.from_dict(policy)
    raise ConnectorConfigError(
        "local-files requires SafeIoPolicy in context['safe_io']",
        code="PMCONN740",
        provider=PROVIDER_NAME,
    )


def _resolve_root(
    root_rel: str,
    policy: SafeIoPolicy,
    context: Mapping[str, Any],
) -> Path:
    raw = Path(root_rel)
    if raw.is_absolute():
        resolved, _ = resolve_under_policy(
            raw, policy, run_id=str(context.get("run_id") or "local-files")
        )
        return resolved
    if not policy.approved_roots:
        raise ConnectorConfigError(
            "SafeIoPolicy requires approved_roots for local-files",
            code="PMCONN741",
            provider=PROVIDER_NAME,
        )
    base = policy.approved_roots[0]
    candidate = (base / root_rel).resolve()
    resolved, _ = resolve_under_policy(
        candidate, policy, run_id=str(context.get("run_id") or "local-files")
    )
    return resolved


def _validate_glob(pattern: str, *, allow_recursive: bool) -> None:
    text = pattern.strip().replace("\\", "/")
    if not text:
        raise ConnectorConfigError(
            "glob must be non-empty",
            code="PMCONN750",
            provider=PROVIDER_NAME,
        )
    if text.startswith("/") or text.startswith("~"):
        raise ConnectorConfigError(
            "Absolute glob patterns are rejected",
            code="PMCONN751",
            provider=PROVIDER_NAME,
        )
    parts = text.split("/")
    if ".." in parts:
        raise ConnectorConfigError(
            "Glob traversal (..) is rejected",
            code="PMCONN752",
            provider=PROVIDER_NAME,
        )
    if "**" in parts and not allow_recursive:
        raise ConnectorConfigError(
            "Recursive glob ** requires explicit allow_recursive_glob",
            code="PMCONN753",
            provider=PROVIDER_NAME,
        )


def _normalize_rel(path: str) -> str:
    text = path.replace("\\", "/")
    return unicodedata.normalize("NFC", text)


def list_landing_files(
    root: Path,
    glob_pat: str,
    *,
    root_ref: str,
    policy: SafeIoPolicy,
    allow_recursive: bool = False,
    max_files: int = DEFAULT_MAX_FILES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
    run_id: str = "local-files",
) -> list[LandingFileIdentity]:
    """Bounded safe listing; no symlink follow; regular files only."""
    _validate_glob(glob_pat, allow_recursive=allow_recursive)
    if not root.exists():
        return []
    if root.is_symlink():
        raise ConnectorReadError(
            f"Landing root must not be a symlink: {root_ref}",
            code="PMCONN760",
            provider=PROVIDER_NAME,
        )
    matches: list[Path] = []
    # Non-recursive listing by default (fnmatch on relative POSIX paths).
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # Prune symlinked directories.
        pruned: list[str] = []
        for name in list(dirnames):
            child = Path(dirpath) / name
            if child.is_symlink():
                pruned.append(name)
        for name in pruned:
            dirnames.remove(name)
        if not allow_recursive and Path(dirpath).resolve() != root.resolve():
            dirnames.clear()
            continue
        for filename in filenames:
            path = Path(dirpath) / filename
            rel = _normalize_rel(str(path.relative_to(root)))
            if fnmatch.fnmatch(rel, glob_pat) or fnmatch.fnmatch(
                Path(rel).name, glob_pat
            ):
                matches.append(path)
        if not allow_recursive:
            break

    # Deterministic NFC POSIX relative path sort.
    matches.sort(key=lambda p: _normalize_rel(str(p.relative_to(root))).encode("utf-8"))
    if len(matches) > max_files:
        raise ConnectorReadError(
            f"Landing listing exceeds max_files={max_files}",
            code="PMCONN761",
            provider=PROVIDER_NAME,
        )

    identities: list[LandingFileIdentity] = []
    total_bytes = 0
    seen_rels: set[str] = set()
    for path in matches:
        if path.is_symlink():
            raise ConnectorReadError(
                f"Symlink rejected in listing: {_normalize_rel(str(path.relative_to(root)))}",
                code="PMCONN762",
                provider=PROVIDER_NAME,
            )
        if not path.is_file():
            continue
        # Revalidate under policy / TOCTOU.
        resolved, _ = resolve_under_policy(path, policy, run_id=run_id, must_exist=True)
        if resolved.is_symlink() or not resolved.is_file():
            raise ConnectorReadError(
                "TOCTOU: listed path is no longer a regular file",
                code="PMCONN763",
                provider=PROVIDER_NAME,
            )
        size = resolved.stat().st_size
        if size > max_file_bytes:
            raise ConnectorReadError(
                f"File exceeds max_file_bytes={max_file_bytes}",
                code="PMCONN764",
                provider=PROVIDER_NAME,
            )
        total_bytes += size
        if total_bytes > max_total_bytes:
            raise ConnectorReadError(
                f"Listing exceeds max_total_bytes={max_total_bytes}",
                code="PMCONN765",
                provider=PROVIDER_NAME,
            )
        rel = _normalize_rel(str(path.relative_to(root)))
        if rel in seen_rels:
            raise ConnectorReadError(
                f"Relative path collision after normalization: {rel}",
                code="PMCONN766",
                provider=PROVIDER_NAME,
            )
        seen_rels.add(rel)
        digest = _sha256_file(resolved)
        identities.append(
            LandingFileIdentity(
                root_ref=root_ref,
                relative_path=rel,
                size=size,
                content_sha256=digest,
            )
        )
    return identities


def read_csv_identities(
    root: Path,
    identities: Sequence[LandingFileIdentity],
    *,
    policy: SafeIoPolicy,
    contract_type: type[Any] | None = None,
    max_rows: int = DEFAULT_MAX_ROWS,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    run_id: str = "local-files",
    encoding: str = "utf-8",
    delimiter: str = ",",
) -> list[Any]:
    """Read ordered CSV files into one logical extract; cross-file header check."""
    rows: list[dict[str, Any]] = []
    header: list[str] | None = None
    for identity in identities:
        path = root / Path(identity.relative_path)
        resolved, _ = resolve_under_policy(path, policy, run_id=run_id, must_exist=True)
        if resolved.is_symlink() or not resolved.is_file():
            raise ConnectorReadError(
                f"TOCTOU on open: {identity.relative_path}",
                code="PMCONN770",
                provider=PROVIDER_NAME,
            )
        size = resolved.stat().st_size
        if size != identity.size:
            raise ConnectorReadError(
                f"Size changed since listing for {identity.relative_path}",
                code="PMCONN771",
                provider=PROVIDER_NAME,
            )
        if size > max_file_bytes:
            raise ConnectorReadError(
                f"File exceeds budget: {identity.relative_path}",
                code="PMCONN772",
                provider=PROVIDER_NAME,
            )
        digest = _sha256_file(resolved)
        if digest != identity.content_sha256:
            raise ConnectorReadError(
                f"Content changed since listing for {identity.relative_path}",
                code="PMCONN773",
                provider=PROVIDER_NAME,
            )
        with resolved.open(newline="", encoding=encoding) as handle:
            reader = csv.DictReader(handle, delimiter=delimiter)
            if reader.fieldnames is None:
                raise ConnectorReadError(
                    f"CSV missing header: {identity.relative_path}",
                    code="PMCONN774",
                    provider=PROVIDER_NAME,
                )
            fields = [_normalize_rel(str(f)) for f in reader.fieldnames]
            if header is None:
                header = fields
            elif fields != header:
                raise ConnectorReadError(
                    f"Cross-file CSV header mismatch at {identity.relative_path}",
                    code="PMCONN775",
                    provider=PROVIDER_NAME,
                    details={"expected": header, "got": fields},
                )
            for row in reader:
                rows.append(dict(row))
                if len(rows) > max_rows:
                    raise ConnectorReadError(
                        f"Row budget exceeded (max_rows={max_rows})",
                        code="PMCONN776",
                        provider=PROVIDER_NAME,
                    )
    return as_records(rows, contract_type)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


__all__ = [
    "PROVIDER_NAME",
    "LocalFilesSourceConnector",
    "create_local_files_source",
    "list_landing_files",
    "read_csv_identities",
]
