"""etlantic-keyring — OS keyring secret provider for ETLantic."""

from __future__ import annotations

from collections.abc import AsyncIterator

import keyring
from etlantic.exceptions import PipelineExecutionError
from etlantic.secrets.provider import (
    ProviderContext,
    SecretProviderCapabilities,
    SecretProviderDescriptor,
    SecretResolutionContext,
)
from etlantic.secrets.ref import SecretRef
from etlantic.secrets.value import SecretValue

__version__ = "0.21.0"

__all__ = [
    "KeyringSecretProvider",
    "__version__",
    "create_provider",
]


class KeyringSecretProvider:
    """Resolve secrets from the OS keyring via ``keyring.get_password``.

    ``SecretRef.name`` is the keyring service; ``SecretRef.key`` is the username.
    When ``key`` is ``value``, ``default``, or empty, ``name`` is used as the
    username and the configured default service applies.
    """

    def __init__(self, *, service: str = "etlantic") -> None:
        self._default_service = service
        self.descriptor = SecretProviderDescriptor(
            name="keyring-secrets",
            engine="keyring",
            version=__version__,
            capabilities=SecretProviderCapabilities(
                versions=False,
                in_memory_cache=True,
                async_native=True,
            ),
        )

    def _service_and_username(self, reference: SecretRef) -> tuple[str, str]:
        key = reference.key
        if key and key not in {"value", "default", ""}:
            service = reference.name or self._default_service
            return service, key
        username = reference.name
        return self._default_service, username

    async def resolve(
        self,
        reference: SecretRef,
        context: SecretResolutionContext,
    ) -> SecretValue:
        service, username = self._service_and_username(reference)
        try:
            password = keyring.get_password(service, username)
        except Exception as exc:
            raise PipelineExecutionError(
                f"Secret {reference.identity()} keyring lookup failed for "
                f"service={service!r} username={username!r}: {exc}",
                run_id=context.run_id,
                code="PMEXEC403",
            ) from exc
        if password is None:
            raise PipelineExecutionError(
                f"Secret {reference.identity()} not found in keyring "
                f"(service={service!r}, username={username!r}, "
                f"run={context.run_id}).",
                run_id=context.run_id,
                code="PMEXEC403",
            )
        return SecretValue(
            _value=password,
            provider=reference.provider,
            name=reference.name,
            key=reference.key,
            version=reference.version,
        )

    async def lifespan(self, context: ProviderContext) -> AsyncIterator[None]:
        yield


def create_provider(*, service: str = "etlantic") -> KeyringSecretProvider:
    """Entry-point factory for ``etlantic.secret_providers``."""
    return KeyringSecretProvider(service=service)
