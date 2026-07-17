"""Secret provider conformance helpers."""

from __future__ import annotations

import asyncio

from etlantic.secrets.provider import (
    ProviderContext,
    SecretProvider,
    SecretResolutionContext,
)
from etlantic.secrets.ref import SecretRef
from etlantic.secrets.value import SecretValue


def assert_secret_provider_info(provider: SecretProvider) -> None:
    descriptor = provider.descriptor
    assert descriptor.name
    assert descriptor.engine
    assert descriptor.capabilities is not None


async def _resolve_once(
    provider: SecretProvider,
    reference: SecretRef,
    *,
    run_id: str = "conformance",
) -> SecretValue:
    context = SecretResolutionContext(
        run_id=run_id,
        pipeline_id="conformance",
        purpose="testing",
    )
    async with provider.lifespan(
        ProviderContext(run_id=run_id, pipeline_id="conformance")
    ):
        return await provider.resolve(reference, context)


def run_secret_conformance_suite(
    provider: SecretProvider,
    *,
    reference: SecretRef,
    expected_substring: str | None = None,
) -> SecretValue:
    """Resolve one secret and assert SecretValue hygiene."""
    assert_secret_provider_info(provider)
    value = asyncio.run(_resolve_once(provider, reference))
    assert isinstance(value, SecretValue)
    assert value.name == reference.name
    text = str(value.value)
    assert isinstance(text, str)
    if expected_substring is not None:
        assert expected_substring in text
    # Ensure repr does not leak the secret.
    assert text not in repr(value)
    return value


def assert_missing_secret_fails(
    provider: SecretProvider,
    reference: SecretRef,
) -> None:
    """Providers must fail closed when a secret is absent."""
    try:
        value = asyncio.run(_resolve_once(provider, reference, run_id="missing"))
    except (
        LookupError,
        KeyError,
        OSError,
        FileNotFoundError,
        RuntimeError,
        ValueError,
    ):
        return
    except Exception as exc:
        msg = str(exc).lower()
        if any(
            token in msg
            for token in ("not found", "missing", "unknown", "does not exist", "absent")
        ):
            return
        raise AssertionError(
            "Missing secret must fail closed with a lookup-style error; "
            f"got {type(exc).__name__}: {exc}"
        ) from exc
    raise AssertionError(
        f"Secret provider must fail closed for missing secrets; got {value!r}"
    )
