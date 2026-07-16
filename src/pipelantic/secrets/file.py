"""Mounted-file secret provider (explicit compatibility)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from pipelantic.exceptions import PipelineExecutionError
from pipelantic.secrets.provider import (
    ProviderContext,
    SecretProviderCapabilities,
    SecretProviderDescriptor,
    SecretResolutionContext,
)
from pipelantic.secrets.ref import SecretRef
from pipelantic.secrets.value import SecretValue


class MountedFileSecretProvider:
    """Resolve secrets from files under a mount root.

    Default path: ``{root}/{name}`` or ``{root}/{name}/{key}``.
    Fail-closed on missing/unreadable files.
    """

    def __init__(self, *, root: str | Path) -> None:
        self._root = Path(root)
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
        if reference.key and reference.key not in {"value", "default", ""}:
            return self._root / reference.name / reference.key
        return self._root / reference.name

    async def resolve(
        self,
        reference: SecretRef,
        context: SecretResolutionContext,
    ) -> SecretValue:
        path = self._path(reference)
        if not path.is_file():
            raise PipelineExecutionError(
                f"Secret {reference.identity()} file not found at {path} "
                f"(run={context.run_id}).",
                run_id=context.run_id,
                code="PMEXEC402",
            )
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise PipelineExecutionError(
                f"Secret {reference.identity()} unreadable at {path}: {exc}",
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
