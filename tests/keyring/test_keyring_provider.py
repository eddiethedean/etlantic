"""Keyring secret provider tests."""

from __future__ import annotations

from unittest.mock import patch

import anyio
import pytest

pytest.importorskip("keyring")

from etlantic.exceptions import PipelineExecutionError
from etlantic.secrets.provider import SecretResolutionContext
from etlantic.secrets.ref import SecretRef
from etlantic_keyring import KeyringSecretProvider, create_provider

pytestmark = pytest.mark.keyring


def test_create_provider_factory() -> None:
    provider = create_provider(service="my-app")
    assert isinstance(provider, KeyringSecretProvider)
    assert provider.descriptor.engine == "keyring"


def test_keyring_resolve_round_trip() -> None:
    provider = KeyringSecretProvider(service="etlantic")
    ref = SecretRef(provider="keyring", name="warehouse", key="password")

    with patch("etlantic_keyring.keyring.get_password", return_value="s3cr3t"):

        async def _run() -> str:
            value = await provider.resolve(
                ref,
                SecretResolutionContext(run_id="r1", pipeline_id="p1"),
            )
            return value.get_secret_value()

        assert anyio.run(_run) == "s3cr3t"


def test_keyring_fail_closed_on_missing() -> None:
    provider = KeyringSecretProvider()
    ref = SecretRef(provider="keyring", name="missing", key="account")

    with patch("etlantic_keyring.keyring.get_password", return_value=None):

        async def _run() -> None:
            await provider.resolve(
                ref,
                SecretResolutionContext(run_id="r1", pipeline_id="p1"),
            )

        with pytest.raises(PipelineExecutionError):
            anyio.run(_run)
