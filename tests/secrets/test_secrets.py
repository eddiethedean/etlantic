"""Secret provider regression tests."""

from __future__ import annotations

import pickle
from dataclasses import asdict
from pathlib import Path

import anyio
import pytest

from etlantic.exceptions import PipelineExecutionError
from etlantic.secrets.env import EnvSecretProvider
from etlantic.secrets.file import MountedFileSecretProvider
from etlantic.secrets.provider import SecretResolutionContext
from etlantic.secrets.ref import SecretRef
from etlantic.secrets.value import SecretSerializationError, SecretValue


def test_env_provider_fail_closed() -> None:
    provider = EnvSecretProvider()

    async def _run() -> None:
        await provider.resolve(
            SecretRef(provider="env", name="NOPE", key="value"),
            SecretResolutionContext(run_id="r", pipeline_id="p"),
        )

    with pytest.raises(PipelineExecutionError):
        anyio.run(_run)


def test_file_provider_round_trip(tmp_path: Path) -> None:
    secret_file = tmp_path / "db_password"
    secret_file.write_text("s3cr3t\n", encoding="utf-8")
    provider = MountedFileSecretProvider(root=tmp_path)

    async def _run() -> SecretValue:
        return await provider.resolve(
            SecretRef(provider="file", name="db_password", key="value"),
            SecretResolutionContext(run_id="r", pipeline_id="p"),
        )

    value = anyio.run(_run)
    assert value.get_secret_value() == "s3cr3t"
    with pytest.raises(SecretSerializationError):
        value.to_dict()


def test_file_provider_rejects_path_traversal(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside_secret"
    outside.write_text("leak", encoding="utf-8")
    provider = MountedFileSecretProvider(root=tmp_path)

    async def _run() -> None:
        await provider.resolve(
            SecretRef(provider="file", name="../outside_secret", key="value"),
            SecretResolutionContext(run_id="r", pipeline_id="p"),
        )

    with pytest.raises(PipelineExecutionError, match="escapes mount root"):
        anyio.run(_run)


def test_secret_value_refuses_asdict_and_pickle() -> None:
    secret = SecretValue(
        _value="hunter2",
        provider="env",
        name="DB",
        key="password",
    )
    with pytest.raises(TypeError):
        asdict(secret)
    with pytest.raises(SecretSerializationError):
        pickle.dumps(secret)
    with pytest.raises(SecretSerializationError):
        secret.to_dict()
    assert "hunter2" not in repr(secret)
    assert str(secret) == "***"
