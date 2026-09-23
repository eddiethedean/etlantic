# pyright: reportMissingImports=false, reportUnknownMemberType=false, reportUnknownVariableType=false
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


def test_keyring_resolve_uses_name_as_service_and_key_as_username() -> None:
    provider = KeyringSecretProvider(service="etlantic")
    ref = SecretRef(provider="keyring", name="warehouse", key="password")

    with patch(
        "etlantic_keyring.keyring.get_password", return_value="s3cr3t"
    ) as mock_get:

        async def _run() -> str:
            value = await provider.resolve(
                ref,
                SecretResolutionContext(run_id="r1", pipeline_id="p1"),
            )
            return value.get_secret_value()

        assert anyio.run(_run) == "s3cr3t"
        mock_get.assert_called_once_with("warehouse", "password")


def test_keyring_value_key_uses_default_service() -> None:
    provider = KeyringSecretProvider(service="etlantic")
    ref = SecretRef(provider="keyring", name="db_password", key="value")

    with patch("etlantic_keyring.keyring.get_password", return_value="x") as mock_get:

        async def _run() -> str:
            value = await provider.resolve(
                ref,
                SecretResolutionContext(run_id="r1", pipeline_id="p1"),
            )
            return value.get_secret_value()

        assert anyio.run(_run) == "x"
        mock_get.assert_called_once_with("etlantic", "db_password")


def test_keyring_fail_closed_on_missing() -> None:
    provider = KeyringSecretProvider()
    ref = SecretRef(provider="keyring", name="missing", key="account")

    with patch("etlantic_keyring.keyring.get_password", return_value=None):

        async def _run() -> None:
            await provider.resolve(
                ref,
                SecretResolutionContext(run_id="r1", pipeline_id="p1"),
            )

        with pytest.raises(PipelineExecutionError) as exc:
            anyio.run(_run)
        assert exc.value.code == "PMEXEC403"


def test_keyring_backend_exception_is_pmexec403() -> None:
    provider = KeyringSecretProvider(service="etlantic")
    ref = SecretRef(provider="keyring", name="warehouse", key="password")

    with patch(
        "etlantic_keyring.keyring.get_password",
        side_effect=RuntimeError("keyring down"),
    ):

        async def _run() -> None:
            await provider.resolve(
                ref,
                SecretResolutionContext(run_id="r1", pipeline_id="p1"),
            )

        with pytest.raises(PipelineExecutionError) as exc:
            anyio.run(_run)
        assert exc.value.code == "PMEXEC403"
        assert "warehouse" in str(exc.value)
