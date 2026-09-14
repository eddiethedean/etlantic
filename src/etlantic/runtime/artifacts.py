"""In-run artifact store realizing plan ArtifactStrategy."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import anyio
from anyio.lowlevel import checkpoint, checkpoint_if_cancelled
from anyio.to_thread import run_sync

from etlantic.io_policy import SafeIoPolicy, write_json_safe, write_text_safe
from etlantic.plan.artifacts import ArtifactRef, ArtifactStrategy
from etlantic.storage.protocol import as_records, records_to_dicts


@dataclass
class ArtifactStore:
    """Holds run artifacts in memory and optional durable workspace files.

    Native dataframe handles are stored as-is. Durable serialization requires
    collectible records; callers must convert frames before durable puts.
    """

    workspace: Path | None = None
    policy: SafeIoPolicy | None = None
    _values: dict[str, Any] = field(default_factory=dict)
    _refs: dict[str, ArtifactRef] = field(default_factory=dict)
    _ownership: dict[str, str] = field(default_factory=dict)

    def put(
        self,
        ref: ArtifactRef,
        value: Any,
        *,
        durable: bool = False,
        ownership: str | None = None,
    ) -> None:
        self._refs[ref.identity] = ref
        self._values[ref.identity] = value
        # Also index by logical output for easy lookup.
        self._values[ref.logical_output] = value
        self._refs[ref.logical_output] = ref
        if ownership is not None:
            self._ownership[ref.identity] = ownership
            self._ownership[ref.logical_output] = ownership
        if durable and self.workspace is not None:
            if _looks_like_frame(value):
                raise TypeError(
                    f"Cannot durably serialize native dataframe artifact "
                    f"{ref.logical_output!r}; collect to records first."
                )
            self.workspace.mkdir(parents=True, exist_ok=True)
            path = (
                self.workspace
                / f"{ref.identity.replace(':', '_').replace('/', '_')}.json"
            )
            if self.policy is None:
                self.policy = SafeIoPolicy.for_root(self.workspace)
            write_json_safe(
                path,
                records_to_dicts(value),
                self.policy,
                run_id=ref.identity,
            )
            self._values[ref.identity] = value

    def get_raw(self, key: str) -> Any:
        """Return the stored handle without record conversion."""
        if key not in self._values:
            raise KeyError(f"Artifact not found: {key}")
        return self._values[key]

    def get(self, key: str, *, contract_type: type[Any] | None = None) -> Any:
        """Return records when possible; otherwise the raw handle."""
        value = self.get_raw(key)
        # Preserve native frames / lazy handles for dataframe engines.
        if _looks_like_frame(value):
            return value
        return as_records(value, contract_type)

    def ownership(self, key: str) -> str | None:
        return self._ownership.get(key)

    def has(self, key: str) -> bool:
        return key in self._values

    def invalidate(self, keys: set[str]) -> None:
        for key in list(self._values):
            if key in keys:
                self._values.pop(key, None)
                self._refs.pop(key, None)
                self._ownership.pop(key, None)

    def clear(self) -> None:
        self._values.clear()
        self._refs.clear()
        self._ownership.clear()

    def list_refs(self) -> tuple[ArtifactRef, ...]:
        seen: set[str] = set()
        out: list[ArtifactRef] = []
        for ref in self._refs.values():
            if ref.identity in seen:
                continue
            seen.add(ref.identity)
            out.append(ref)
        return tuple(out)

    def should_durable(self, strategy: ArtifactStrategy | str) -> bool:
        value = strategy.value if isinstance(strategy, ArtifactStrategy) else strategy
        return value == ArtifactStrategy.DURABLE.value


async def check_attempt_deadline() -> None:
    """Deliver cancellation and enforce deadlines even after synchronous work."""
    await checkpoint_if_cancelled()
    if anyio.current_time() >= anyio.current_effective_deadline():
        raise TimeoutError("Adaptive member exceeded its deadline")
    await checkpoint()
    if anyio.current_time() >= anyio.current_effective_deadline():
        raise TimeoutError("Adaptive member exceeded its deadline")


class AttemptArtifactStore(ArtifactStore):
    """Private adaptive member outputs, published only after its complete body.

    Reads fall through to the run store without copying or reclaiming borrowed
    inputs. Writes remain private through schema work and middleware unwinding.
    Durable preparation also precedes the final deadline/visibility boundary.
    """

    def __init__(self, parent: ArtifactStore) -> None:
        super().__init__(workspace=parent.workspace, policy=parent.policy)
        self._parent = parent
        self._durable: dict[str, bool] = {}
        self._text_files: list[tuple[Path, str, SafeIoPolicy, str]] = []
        self.cleanup_failed = False

    def stage_text(
        self, path: Path, text: str, policy: SafeIoPolicy, *, run_id: str
    ) -> None:
        """Prepare an owned checkpoint file at the same visibility boundary."""
        self._text_files.append((path, text, policy, run_id))

    def clear(self) -> None:
        super().clear()
        self._durable.clear()
        self._text_files.clear()

    def put(
        self,
        ref: ArtifactRef,
        value: Any,
        *,
        durable: bool = False,
        ownership: str | None = None,
    ) -> None:
        super().put(ref, value, durable=False, ownership=ownership)
        self._durable[ref.identity] = durable

    def get_raw(self, key: str) -> Any:
        if super().has(key):
            return super().get_raw(key)
        return self._parent.get_raw(key)

    def has(self, key: str) -> bool:
        return super().has(key) or self._parent.has(key)

    def ownership(self, key: str) -> str | None:
        if super().has(key):
            return super().ownership(key)
        return self._parent.ownership(key)

    async def commit(self) -> None:
        await check_attempt_deadline()
        # Keep even partially prepared durable outputs out of the run's lookup
        # maps. Their files are owned by this attempt until visibility commits.
        prepared = ArtifactStore(workspace=self.workspace, policy=self.policy)
        written: list[tuple[Path, str | None, SafeIoPolicy]] = []
        checkpoint_payloads: dict[Path, bytes] = {}

        def remember(path: Path, policy: SafeIoPolicy, run_id: str) -> Path:
            from etlantic.interchange.security import ensure_file_within_budget
            from etlantic.io_policy import resolve_under_policy

            path, _ = resolve_under_policy(path, policy, run_id=run_id)
            previous = None
            if path.exists():
                ensure_file_within_budget(path, max_bytes=policy.max_read_bytes)
                previous = path.read_bytes().decode("utf-8")
            written.append((path, previous, policy))
            return path

        try:
            for path, text, policy, run_id in self._text_files:

                def prepare_text(
                    path: Path = path,
                    text: str = text,
                    policy: SafeIoPolicy = policy,
                    run_id: str = run_id,
                ) -> None:
                    from etlantic.io_policy import (
                        _acquire_lock,
                        _release_lock,
                        resolve_under_policy,
                    )

                    path, _ = resolve_under_policy(path, policy, run_id=run_id)
                    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    lock = (
                        _acquire_lock(path, timeout=policy.lock_timeout_seconds)
                        if policy.enable_locking
                        else None
                    )
                    try:
                        path = remember(path, policy, run_id)
                        checkpoint_payloads[path] = text.encode("utf-8")
                        # Hold the destination lock across preimage capture and
                        # replacement; the nested safe write shares that lock.
                        write_text_safe(
                            path,
                            text,
                            replace(policy, enable_locking=False),
                            run_id=run_id,
                        )
                    finally:
                        if lock is not None:
                            _release_lock(lock)

                # Drain file I/O before rolling back or releasing its buffers.
                await run_sync(prepare_text)
            for ref in self.list_refs():
                durable = self._durable[ref.identity]
                if durable and self.workspace is not None:
                    policy = self.policy or SafeIoPolicy.for_root(self.workspace)
                    remember(
                        self.workspace
                        / f"{ref.identity.replace(':', '_').replace('/', '_')}.json",
                        policy,
                        ref.identity,
                    )
                prepared.put(
                    ref,
                    self.get_raw(ref.identity),
                    durable=durable,
                    ownership=self.ownership(ref.identity),
                )
            await check_attempt_deadline()
        except BaseException:
            for path, previous, policy in reversed(written):
                try:
                    from etlantic.interchange.security import ensure_file_within_budget
                    from etlantic.io_policy import _acquire_lock, _release_lock

                    checkpoint = path in checkpoint_payloads
                    lock = (
                        _acquire_lock(path, timeout=policy.lock_timeout_seconds)
                        if checkpoint and policy.enable_locking
                        else None
                    )
                    try:
                        if checkpoint and path.exists():
                            ensure_file_within_budget(
                                path, max_bytes=policy.max_read_bytes
                            )
                            if path.read_bytes() != checkpoint_payloads[path]:
                                # A subsequent writer owns the replacement;
                                # rollback must not restore over its output.
                                continue
                        if previous is None:
                            path.unlink(missing_ok=True)
                        else:
                            write_text_safe(
                                path,
                                previous,
                                replace(policy, enable_locking=False)
                                if lock is not None
                                else policy,
                            )
                    finally:
                        if lock is not None:
                            _release_lock(lock)
                except Exception:
                    # Preserve the original failure. The host records the owned
                    # cleanup obligation without exposing paths or row payloads.
                    self.cleanup_failed = True
            raise
        # No user/backend operation or checkpoint between these map updates and
        # the host's terminal-success transition. Dependents see the whole set.
        self._parent._values.update(prepared._values)
        self._parent._refs.update(prepared._refs)
        self._parent._ownership.update(prepared._ownership)
        self._parent.policy = prepared.policy


def _looks_like_frame(value: Any) -> bool:
    if value is None or isinstance(
        value, (list, tuple, dict, str, bytes, int, float, bool)
    ):
        return False
    module = type(value).__module__ or ""
    name = type(value).__name__
    if module.startswith("polars") or module.startswith("pandas"):
        return True
    return name in {"DataFrame", "LazyFrame", "Series"}
