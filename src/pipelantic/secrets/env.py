"""Environment-variable secret provider (explicit compatibility)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

from pipelantic.exceptions import PipelineExecutionError
from pipelantic.secrets.provider import (
    ProviderContext,
    SecretProviderCapabilities,
    SecretProviderDescriptor,
    SecretResolutionContext,
)
from pipelantic.secrets.ref import SecretRef
from pipelantic.secrets.value import SecretValue


class EnvSecretProvider:
    """Resolve secrets from process environment variables.

    Looks up ``{name}`` or ``{name}_{key}`` when key is not the default.
    Fail-closed: missing values raise; no silent empty fallback.
    """

    def __init__(self, *, prefix: str = "") -> None:
        self._prefix = prefix
        self.descriptor = SecretProviderDescriptor(
            name="env-secrets",
            engine="env",
            capabilities=SecretProviderCapabilities(
                versions=False,
                in_memory_cache=True,
                async_native=True,
            ),
        )

    def _env_name(self, reference: SecretRef) -> str:
        base = f"{self._prefix}{reference.name}" if self._prefix else reference.name
        if reference.key and reference.key not in {"value", "default", ""}:
            return f"{base}_{reference.key}".upper()
        return base.upper()

    async def resolve(
        self,
        reference: SecretRef,
        context: SecretResolutionContext,
    ) -> SecretValue:
        env_name = self._env_name(reference)
        if env_name not in os.environ:
            raise PipelineExecutionError(
                f"Secret {reference.identity()} not found in environment "
                f"as {env_name!r} (run={context.run_id}).",
                run_id=context.run_id,
                code="PMEXEC401",
            )
        return SecretValue(
            _value=os.environ[env_name],
            provider=reference.provider,
            name=reference.name,
            key=reference.key,
            version=reference.version,
        )

    async def lifespan(self, context: ProviderContext) -> AsyncIterator[None]:
        yield
