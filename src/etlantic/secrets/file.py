"""Mounted-file secret provider (explicit compatibility)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from etlantic.exceptions import PipelineExecutionError
from etlantic.interchange.security import UnsafeLoadError, resolve_safe_path
from etlantic.secrets.provider import (
    ProviderContext,
    SecretProviderCapabilities,
    SecretProviderDescriptor,
    SecretResolutionContext,
)
from etlantic.secrets.ref import SecretRef
from etlantic.secrets.value import SecretValue


class MountedFileSecretProvider:
    """Resolve secrets from files under a mount root.

    Default path: ``{root}/{name}`` or ``{root}/{name}/{key}``.
    Fail-closed on missing/unreadable files and path escape.
    """

    def __init__(self, *, root: str | Path) -> None:
        self._root = Path(root).expanduser().resolve()
        self.descriptor = SecretProviderDescriptor(
            name="file-secrets",
            engine="file",
            capabilities=SecretProviderCapabilities(
                versions=False,
                binary_values=True,
                in_memory_cache=True,
                async_native=True,
            ),
        )

    def _path(self, reference: SecretRef) -> Path:
        name = str(reference.name or "")
        if not name or name.startswith("/") or ".." in Path(name).parts:
            raise PipelineExecutionError(
                f"Secret {reference.identity()} name escapes mount root.",
                code="PMEXEC402",
            )
        if reference.key and reference.key not in {"value", "default", ""}:
            key = str(reference.key)
            if key.startswith("/") or ".." in Path(key).parts:
                raise PipelineExecutionError(
                    f"Secret {reference.identity()} key escapes mount root.",
                    code="PMEXEC402",
                )
            candidate = self._root / name / key
        else:
            candidate = self._root / name
        try:
            return resolve_safe_path(candidate, root=self._root)
        except UnsafeLoadError as exc:
            raise PipelineExecutionError(
                f"Secret {reference.identity()} path escapes mount root.",
                code="PMEXEC402",
            ) from exc

    async def resolve(
        self,
        reference: SecretRef,
        context: SecretResolutionContext,
    ) -> SecretValue:
        try:
            path = self._path(reference)
        except PipelineExecutionError as exc:
            if getattr(exc, "run_id", None) is None:
                raise PipelineExecutionError(
                    str(exc),
                    run_id=context.run_id,
                    code=getattr(exc, "code", None) or "PMEXEC402",
                ) from exc
            raise
        if not path.is_file():
            raise PipelineExecutionError(
                f"Secret {reference.identity()} file not found under mount root "
                f"(relative={path.relative_to(self._root).as_posix()}, "
                f"run={context.run_id}).",
                run_id=context.run_id,
                code="PMEXEC402",
            )
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise PipelineExecutionError(
                f"Secret {reference.identity()} unreadable under mount root "
                f"(relative={path.relative_to(self._root).as_posix()}): {exc}",
                run_id=context.run_id,
                code="PMEXEC402",
            ) from exc
        text: str | bytes
        try:
            # Normalize common line endings so Windows CRLF secrets don't
            # leak a trailing "\r" into the resolved SecretValue.
            text = raw.decode("utf-8").rstrip("\r\n")
            content_type = "text"
        except UnicodeDecodeError:
            text = raw
            content_type = "binary"
        return SecretValue(
            _value=text,
            provider=reference.provider,
            name=reference.name,
            key=reference.key,
            version=reference.version,
            content_type=content_type,
        )

    async def lifespan(self, context: ProviderContext) -> AsyncIterator[None]:
        yield
