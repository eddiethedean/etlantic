"""Runtime secret resolution package."""

from __future__ import annotations

from etlantic.secrets.cache import SecretCache
from etlantic.secrets.env import EnvSecretProvider
from etlantic.secrets.file import MountedFileSecretProvider
from etlantic.secrets.provider import (
    LeasedSecretProvider,
    ProviderContext,
    SecretAliasAuthorizer,
    SecretLease,
    SecretProvider,
    SecretProviderCapabilities,
    SecretProviderDescriptor,
    SecretResolutionContext,
)
from etlantic.secrets.ref import SecretRef
from etlantic.secrets.value import SecretSerializationError, SecretValue

__all__ = [
    "EnvSecretProvider",
    "LeasedSecretProvider",
    "MountedFileSecretProvider",
    "ProviderContext",
    "SecretAliasAuthorizer",
    "SecretCache",
    "SecretLease",
    "SecretProvider",
    "SecretProviderCapabilities",
    "SecretProviderDescriptor",
    "SecretRef",
    "SecretResolutionContext",
    "SecretSerializationError",
    "SecretValue",
]
