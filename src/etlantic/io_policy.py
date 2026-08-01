"""Unified safe filesystem I/O policy (0.20)."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from contractmodel.validation.limits import check_file_byte_limit

from etlantic.diagnostics import Diagnostic, Severity, SourceLocation, ValidationReport
from etlantic.interchange.security import (
    DEFAULT_MAX_BYTES,
    UnsafeLoadError,
    ensure_file_within_budget,
    resolve_safe_path,
)

if TYPE_CHECKING:
    from etlantic.runtime.events import SecurityEvent

SymlinkPolicy = Literal["reject", "follow_within_root"]
OverwritePolicy = Literal["reject", "allow", "atomic_replace"]


def _security_event(**kwargs: Any) -> Any:
    from etlantic.runtime.events import SecurityEvent

    return SecurityEvent(**kwargs)


def _root_refs(value: Any) -> tuple[str, ...]:
    """Decode plan root aliases without accepting paths or string characters."""
    raw = (value,) if isinstance(value, str) else tuple(value or ())
    refs = tuple(str(item) for item in raw)
    for root_ref in refs:
        normalized = root_ref.replace("\\", "/")
        if (
            not root_ref.strip()
            or normalized.startswith("/")
            or (len(normalized) >= 2 and normalized[1] == ":")
            or ".." in normalized.split("/")
        ):
            raise ValueError("safe_io root_refs must be relative, non-empty aliases")
    return refs


def _wire_bool(value: Any, *, field_name: str) -> bool:
    """Decode a JSON boolean without treating non-empty strings as true."""
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    raise ValueError(f"{field_name} must be a boolean")


@dataclass(frozen=True, slots=True)
class SafeIoPolicy:
    """Policy for contract/profile/report/history/cache/artifact/viz FS access."""

    approved_roots: tuple[Path, ...] = ()
    max_read_bytes: int = DEFAULT_MAX_BYTES
    symlink_policy: SymlinkPolicy = "reject"
    overwrite_policy: OverwritePolicy = "atomic_replace"
    require_regular_files: bool = True
    enable_locking: bool = True
    lock_timeout_seconds: float = 30.0
    compute_integrity_digest: bool = True
    retention_seconds: int | None = None
    tenant: str = "default"
    environment: str = "default"
    security_domain: str = "default"

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved_roots": [str(p) for p in self.approved_roots],
            "max_read_bytes": self.max_read_bytes,
            "symlink_policy": self.symlink_policy,
            "overwrite_policy": self.overwrite_policy,
            "require_regular_files": self.require_regular_files,
            "enable_locking": self.enable_locking,
            "lock_timeout_seconds": self.lock_timeout_seconds,
            "compute_integrity_digest": self.compute_integrity_digest,
            "retention_seconds": self.retention_seconds,
            "tenant": self.tenant,
            "environment": self.environment,
            "security_domain": self.security_domain,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> SafeIoPolicy:
        data = dict(data or {})
        roots = tuple(Path(p) for p in (data.get("approved_roots") or ()))
        symlink_policy = str(data.get("symlink_policy") or "reject")
        overwrite_policy = str(data.get("overwrite_policy") or "atomic_replace")
        allowed_symlink = {"reject", "follow_within_root"}
        allowed_overwrite = {"reject", "allow", "atomic_replace"}
        if symlink_policy not in allowed_symlink:
            raise ValueError(
                f"Invalid symlink_policy {symlink_policy!r}; "
                f"expected one of {sorted(allowed_symlink)}"
            )
        if overwrite_policy not in allowed_overwrite:
            raise ValueError(
                f"Invalid overwrite_policy {overwrite_policy!r}; "
                f"expected one of {sorted(allowed_overwrite)}"
            )
        return cls(
            approved_roots=roots,
            max_read_bytes=int(data.get("max_read_bytes") or DEFAULT_MAX_BYTES),
            symlink_policy=symlink_policy,  # type: ignore[arg-type]
            overwrite_policy=overwrite_policy,  # type: ignore[arg-type]
            require_regular_files=_wire_bool(
                data.get("require_regular_files", True),
                field_name="require_regular_files",
            ),
            enable_locking=_wire_bool(
                data.get("enable_locking", True), field_name="enable_locking"
            ),
            lock_timeout_seconds=float(data.get("lock_timeout_seconds") or 30.0),
            compute_integrity_digest=_wire_bool(
                data.get("compute_integrity_digest", True),
                field_name="compute_integrity_digest",
            ),
            retention_seconds=data.get("retention_seconds"),
            tenant=str(data.get("tenant") or "default"),
            environment=str(data.get("environment") or "default"),
            security_domain=str(data.get("security_domain") or "default"),
        )

    @classmethod
    def for_root(
        cls,
        root: str | Path,
        *,
        security_domain: str = "default",
        tenant: str = "default",
        environment: str = "default",
        **kwargs: Any,
    ) -> SafeIoPolicy:
        return cls(
            approved_roots=(Path(root).expanduser().resolve(),),
            security_domain=security_domain,
            tenant=tenant,
            environment=environment,
            **kwargs,
        )


@dataclass(frozen=True, slots=True)
class SafeIoPlanPolicy:
    """Plan-safe I/O policy: root refs only — no absolute approved_roots.

    Runtime :class:`SafeIoPolicy` may carry physical paths. Plan snapshots and
    connector plans must retain aliases / policy semantics instead.
    """

    version: str = "safe_io_plan/1"
    root_refs: tuple[str, ...] = ()
    max_read_bytes: int = DEFAULT_MAX_BYTES
    symlink_policy: SymlinkPolicy = "reject"
    overwrite_policy: OverwritePolicy = "atomic_replace"
    require_regular_files: bool = True
    enable_locking: bool = True
    lock_timeout_seconds: float = 30.0
    compute_integrity_digest: bool = True
    retention_seconds: int | None = None
    tenant: str = "default"
    environment: str = "default"
    security_domain: str = "default"
    fail_on_symlink: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "root_refs": list(self.root_refs),
            "max_read_bytes": self.max_read_bytes,
            "symlink_policy": self.symlink_policy,
            "overwrite_policy": self.overwrite_policy,
            "require_regular_files": self.require_regular_files,
            "enable_locking": self.enable_locking,
            "lock_timeout_seconds": self.lock_timeout_seconds,
            "compute_integrity_digest": self.compute_integrity_digest,
            "retention_seconds": self.retention_seconds,
            "tenant": self.tenant,
            "environment": self.environment,
            "security_domain": self.security_domain,
            "fail_on_symlink": self.fail_on_symlink,
        }

    @classmethod
    def from_safe_io(cls, data: dict[str, Any] | None) -> SafeIoPlanPolicy:
        """Build a plan policy from a runtime ``safe_io`` mapping.

        Physical ``approved_roots`` are omitted; only ``root_refs`` (when
        present) and non-path policy flags are retained.
        """
        data = dict(data or {})
        symlink_policy = str(data.get("symlink_policy") or "reject")
        overwrite_policy = str(data.get("overwrite_policy") or "atomic_replace")
        allowed_symlink = {"reject", "follow_within_root"}
        allowed_overwrite = {"reject", "allow", "atomic_replace"}
        if symlink_policy not in allowed_symlink:
            raise ValueError(
                f"Invalid symlink_policy {symlink_policy!r}; "
                f"expected one of {sorted(allowed_symlink)}"
            )
        if overwrite_policy not in allowed_overwrite:
            raise ValueError(
                f"Invalid overwrite_policy {overwrite_policy!r}; "
                f"expected one of {sorted(allowed_overwrite)}"
            )
        fail_on = data.get("fail_on_symlink")
        if fail_on is None:
            fail_on = symlink_policy == "reject"
        return cls(
            version=str(data.get("version") or "safe_io_plan/1"),
            root_refs=_root_refs(data.get("root_refs")),
            max_read_bytes=int(data.get("max_read_bytes") or DEFAULT_MAX_BYTES),
            symlink_policy=symlink_policy,  # type: ignore[arg-type]
            overwrite_policy=overwrite_policy,  # type: ignore[arg-type]
            require_regular_files=_wire_bool(
                data.get("require_regular_files", True),
                field_name="require_regular_files",
            ),
            enable_locking=_wire_bool(
                data.get("enable_locking", True), field_name="enable_locking"
            ),
            lock_timeout_seconds=float(data.get("lock_timeout_seconds") or 30.0),
            compute_integrity_digest=_wire_bool(
                data.get("compute_integrity_digest", True),
                field_name="compute_integrity_digest",
            ),
            retention_seconds=data.get("retention_seconds"),
            tenant=str(data.get("tenant") or "default"),
            environment=str(data.get("environment") or "default"),
            security_domain=str(data.get("security_domain") or "default"),
            fail_on_symlink=_wire_bool(fail_on, field_name="fail_on_symlink"),
        )


def sanitize_safe_io_for_plan(data: dict[str, Any] | None) -> dict[str, Any]:
    """Replace physical approved_roots with plan-safe root_ref semantics."""
    raw = dict(data or {})
    if not raw:
        return {}
    return SafeIoPlanPolicy.from_safe_io(raw).to_dict()


@dataclass
class SafeIoResult:
    """Outcome of a safe I/O operation."""

    path: Path
    digest: str | None = None
    bytes_written: int | None = None
    diagnostics: list[Diagnostic] = field(default_factory=list)
    security_events: list[SecurityEvent] = field(default_factory=list)


def _io_error(code: str, message: str, path: str | Path) -> UnsafeLoadError:
    report = ValidationReport.from_diagnostics(
        [
            Diagnostic(
                code=code,
                severity=Severity.ERROR,
                message=message,
                source=SourceLocation(path=str(path)),
                phase="safe_io",
            )
        ]
    )
    return UnsafeLoadError(message, report=report)


def _deny_event(
    *,
    run_id: str,
    path: Path,
    outcome: str,
    message: str,
) -> Any:
    return _security_event(
        kind="safe_io",
        run_id=run_id,
        provider="filesystem",
        outcome=outcome,
        message=message,
        subject=str(path),
        metadata={"path": str(path)},
    )


def _is_special_file(path: Path) -> bool:
    try:
        mode = path.lstat().st_mode
    except OSError:
        return False
    import stat

    return (
        stat.S_ISCHR(mode)
        or stat.S_ISBLK(mode)
        or stat.S_ISFIFO(mode)
        or stat.S_ISSOCK(mode)
    )


def resolve_under_policy(
    path: str | Path,
    policy: SafeIoPolicy,
    *,
    run_id: str = "io",
    must_exist: bool = False,
) -> tuple[Path, list[SecurityEvent]]:
    """Resolve a path under approved roots with symlink/special-file checks."""
    events: list[SecurityEvent] = []
    raw = Path(path).expanduser()
    if policy.symlink_policy == "reject" and raw.exists() and raw.is_symlink():
        events.append(
            _deny_event(
                run_id=run_id,
                path=raw,
                outcome="denied",
                message="Symlink rejected by SafeIoPolicy.",
            )
        )
        raise _io_error("PMSRC110", f"Symlink rejected: {raw}", raw)

    if not policy.approved_roots:
        events.append(
            _deny_event(
                run_id=run_id,
                path=raw,
                outcome="denied",
                message="SafeIoPolicy requires approved_roots (default deny).",
            )
        )
        raise _io_error(
            "PMSRC101",
            "SafeIoPolicy requires non-empty approved_roots; failing closed.",
            path,
        )

    # Prefer first root as default confinement.
    root = policy.approved_roots[0]
    try:
        resolved = resolve_safe_path(raw, root=root)
    except UnsafeLoadError:
        # Allow if under any approved root.
        resolved = raw.resolve(strict=False)
        ok = False
        for candidate_root in policy.approved_roots:
            try:
                resolved.relative_to(candidate_root.expanduser().resolve())
                ok = True
                break
            except ValueError:
                continue
        if not ok:
            events.append(
                _deny_event(
                    run_id=run_id,
                    path=raw,
                    outcome="denied",
                    message="Path escapes approved roots.",
                )
            )
            raise _io_error(
                "PMSRC101",
                f"Path {path!s} escapes approved roots.",
                path,
            ) from None

    if must_exist and not resolved.exists():
        raise _io_error("PMSRC102", f"File not found: {resolved}", resolved)

    if resolved.exists():
        if policy.require_regular_files and _is_special_file(resolved):
            events.append(
                _deny_event(
                    run_id=run_id,
                    path=resolved,
                    outcome="denied",
                    message="Special file rejected.",
                )
            )
            raise _io_error("PMSRC111", f"Special file rejected: {resolved}", resolved)
        if policy.symlink_policy == "reject":
            _reject_symlink_escape(
                raw=raw,
                resolved=resolved,
                policy=policy,
                run_id=run_id,
                events=events,
            )
        elif policy.symlink_policy == "follow_within_root":
            _reject_symlink_escape(
                raw=raw,
                resolved=resolved,
                policy=policy,
                run_id=run_id,
                events=events,
                allow_within_root=True,
            )

    return resolved, events


def _path_has_symlink_component(path: Path) -> bool:
    """Return True when any existing component along path is a symlink."""
    try:
        if path.is_symlink():
            return True
        for parent in path.parents:
            if parent.exists() and parent.is_symlink():
                return True
    except OSError:
        return False
    return False


def _reject_symlink_escape(
    *,
    raw: Path,
    resolved: Path,
    policy: SafeIoPolicy,
    run_id: str,
    events: list[SecurityEvent],
    allow_within_root: bool = False,
) -> None:
    """Reject symlink paths per policy.

    When ``allow_within_root`` is False (``symlink_policy="reject"``), any
    symlink component on the path is denied. When True
    (``follow_within_root``), only escapes outside approved roots are denied.
    """
    has_symlink = _path_has_symlink_component(raw) or _path_has_symlink_component(
        resolved
    )
    if not has_symlink:
        return

    if not allow_within_root:
        events.append(
            _deny_event(
                run_id=run_id,
                path=resolved,
                outcome="denied",
                message="Symlink component rejected by SafeIoPolicy.",
            )
        )
        raise _io_error(
            "PMSRC110",
            f"Symlink rejected: {raw}",
            raw,
        )

    if allow_within_root and policy.approved_roots:
        for candidate_root in policy.approved_roots:
            root_res = candidate_root.expanduser().resolve()
            try:
                resolved.relative_to(root_res)
                return
            except ValueError:
                continue

    try:
        no_follow = Path(os.path.realpath(raw, strict=False))  # type: ignore[call-arg]
    except TypeError:
        no_follow = Path(os.path.realpath(str(raw)))
    if policy.approved_roots:
        for candidate_root in policy.approved_roots:
            root_res = candidate_root.expanduser().resolve()
            try:
                no_follow.relative_to(root_res)
                return
            except ValueError:
                continue

    events.append(
        _deny_event(
            run_id=run_id,
            path=resolved,
            outcome="denied",
            message="Symlink escape rejected.",
        )
    )
    raise _io_error(
        "PMSRC110",
        f"Symlink escape rejected: {raw}",
        raw,
    )


def read_text_safe(
    path: str | Path,
    policy: SafeIoPolicy,
    *,
    run_id: str = "io",
    encoding: str = "utf-8",
) -> tuple[Path, str, list[SecurityEvent]]:
    """Bounded safe text read under policy."""
    resolved, events = resolve_under_policy(
        path, policy, run_id=run_id, must_exist=True
    )
    ensure_file_within_budget(resolved, max_bytes=policy.max_read_bytes)
    # Double-check via contractmodel helper for consistency.
    result = check_file_byte_limit(resolved, max_bytes=policy.max_read_bytes)
    if result is not None and not result.success:
        raise _io_error(
            "PMSRC103",
            f"Oversized input rejected: {resolved}",
            resolved,
        )
    return resolved, resolved.read_text(encoding=encoding), events


def _lock_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".lock")


def _acquire_lock(path: Path, *, timeout: float) -> Path:
    lock = _lock_path(path)
    deadline = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(fd, str(os.getpid()).encode("ascii"))
            os.close(fd)
            return lock
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise _io_error(
                    "PMSRC112",
                    f"Timed out acquiring lock for {path}",
                    path,
                ) from None
            time.sleep(0.05)


def _release_lock(lock: Path) -> None:
    with contextlib.suppress(OSError):
        lock.unlink(missing_ok=True)


def write_text_safe(
    path: str | Path,
    text: str,
    policy: SafeIoPolicy,
    *,
    run_id: str = "io",
    encoding: str = "utf-8",
) -> SafeIoResult:
    """Atomic, locked, integrity-aware text write under policy."""
    resolved, events = resolve_under_policy(path, policy, run_id=run_id)
    resolved.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    if resolved.exists() and policy.overwrite_policy == "reject":
        events.append(
            _deny_event(
                run_id=run_id,
                path=resolved,
                outcome="denied",
                message="Overwrite rejected.",
            )
        )
        raise _io_error("PMSRC113", f"Overwrite rejected: {resolved}", resolved)

    payload = text.encode(encoding)
    digest = (
        "sha256:" + hashlib.sha256(payload).hexdigest()
        if policy.compute_integrity_digest
        else None
    )

    lock: Path | None = None
    if policy.enable_locking:
        lock = _acquire_lock(resolved, timeout=policy.lock_timeout_seconds)
    try:
        if (
            policy.overwrite_policy in {"allow", "atomic_replace"}
            or not resolved.exists()
        ):
            fd, tmp_name = tempfile.mkstemp(
                prefix=f".{resolved.name}.",
                suffix=".tmp",
                dir=str(resolved.parent),
            )
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp_name, resolved)
            except Exception:
                with contextlib.suppress(OSError):
                    os.unlink(tmp_name)
                raise
        else:
            raise _io_error("PMSRC113", f"Overwrite rejected: {resolved}", resolved)
    finally:
        if lock is not None:
            _release_lock(lock)

    events.append(
        _security_event(
            kind="safe_io",
            run_id=run_id,
            provider="filesystem",
            outcome="written",
            subject=str(resolved),
            metadata={"digest": digest, "bytes": len(payload)},
        )
    )
    return SafeIoResult(
        path=resolved,
        digest=digest,
        bytes_written=len(payload),
        security_events=events,
    )


def append_line_safe(
    path: str | Path,
    line: str,
    policy: SafeIoPolicy,
    *,
    run_id: str = "io",
    encoding: str = "utf-8",
) -> SafeIoResult:
    """Append one line under file lock using O_APPEND (no full-file read)."""
    resolved, events = resolve_under_policy(path, policy, run_id=run_id)
    resolved.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    text = line if line.endswith("\n") else f"{line}\n"
    payload = text.encode(encoding)
    digest = (
        "sha256:" + hashlib.sha256(payload).hexdigest()
        if policy.compute_integrity_digest
        else None
    )
    lock: Path | None = None
    if policy.enable_locking:
        lock = _acquire_lock(resolved, timeout=policy.lock_timeout_seconds)
    try:
        fd = os.open(str(resolved), os.O_APPEND | os.O_WRONLY | os.O_CREAT, 0o600)
        try:
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if lock is not None:
            _release_lock(lock)
    events.append(
        _security_event(
            kind="safe_io",
            run_id=run_id,
            provider="filesystem",
            outcome="appended",
            subject=str(resolved),
            metadata={"digest": digest, "bytes": len(payload)},
        )
    )
    return SafeIoResult(
        path=resolved,
        digest=digest,
        bytes_written=len(payload),
        security_events=events,
    )


def write_json_safe(
    path: str | Path,
    data: Any,
    policy: SafeIoPolicy,
    *,
    run_id: str = "io",
) -> SafeIoResult:
    """Write JSON via :func:`write_text_safe`."""
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    return write_text_safe(path, text, policy, run_id=run_id)


def read_modify_write_json_safe(
    path: str | Path,
    policy: SafeIoPolicy,
    modifier: Callable[[dict[str, Any]], dict[str, Any]],
    *,
    run_id: str = "io",
) -> SafeIoResult:
    """Read-modify-write JSON atomically under a single file lock."""
    resolved, events = resolve_under_policy(path, policy, run_id=run_id)
    resolved.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock: Path | None = None
    if policy.enable_locking:
        lock = _acquire_lock(resolved, timeout=policy.lock_timeout_seconds)
    try:
        current: dict[str, Any] = {}
        if resolved.exists():
            _resolved, text, read_events = read_text_safe(
                resolved, policy, run_id=run_id
            )
            events.extend(read_events)
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                current = parsed
        updated = modifier(current)
        nested = replace(policy, enable_locking=False)
        result = write_text_safe(
            resolved,
            json.dumps(updated, indent=2, sort_keys=True) + "\n",
            nested,
            run_id=run_id,
        )
        events.extend(result.security_events)
        return SafeIoResult(
            path=result.path,
            digest=result.digest,
            bytes_written=result.bytes_written,
            security_events=events,
        )
    finally:
        if lock is not None:
            _release_lock(lock)


def namespaced_path(
    root: str | Path,
    *parts: str,
    policy: SafeIoPolicy | None = None,
) -> Path:
    """Build an isolation-namespaced path under root."""
    base = Path(root)
    dims: list[str] = []
    if policy is not None:
        dims.extend(
            [
                _safe_segment(policy.security_domain),
                _safe_segment(policy.tenant),
                _safe_segment(policy.environment),
            ]
        )
    safe_parts = [_safe_segment(p) for p in parts]
    return base.joinpath(*dims, *safe_parts)


def _safe_segment(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in str(value))


def cleanup_retention(root: str | Path, policy: SafeIoPolicy) -> list[Path]:
    """Delete files under root older than retention_seconds (if configured)."""
    if policy.retention_seconds is None:
        return []
    cutoff = time.time() - float(policy.retention_seconds)
    removed: list[Path] = []
    base = Path(root)
    if not base.exists():
        return removed
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed.append(path)
        except OSError:
            continue
    return removed
