"""Fail-closed secret rejection for profile asset descriptors (0.38)."""

from __future__ import annotations

import pytest

from etlantic.bindings import normalize_assets_map, parse_asset_descriptor
from etlantic.connectors.errors import ConnectorConfigError
from etlantic.profile import Profile


def test_config_password_key_rejected() -> None:
    with pytest.raises(ConnectorConfigError, match="secret-like") as excinfo:
        parse_asset_descriptor(
            {
                "provider": "postgresql",
                "location": "host/db",
                "config": {"password": "hunter2"},
            }
        )
    assert excinfo.value.code == "PMCONN902"


def test_config_url_userinfo_rejected() -> None:
    with pytest.raises(ConnectorConfigError, match="userinfo") as excinfo:
        parse_asset_descriptor(
            {
                "provider": "postgresql",
                "config": {"url": "postgres://u:p@h/db"},
            }
        )
    assert excinfo.value.code == "PMCONN903"


def test_normalize_assets_map_rejects_secret_config() -> None:
    with pytest.raises(ConnectorConfigError):
        normalize_assets_map(
            {
                "db": {
                    "provider": "postgresql",
                    "config": {"password": "x"},
                }
            }
        )


def test_profile_rejects_secret_asset_config() -> None:
    with pytest.raises(ConnectorConfigError):
        Profile(
            name="dev",
            security_mode="development",
            assets={
                "db": {
                    "provider": "postgresql",
                    "config": {"token": "leak"},
                }
            },
        )


def test_postgres_url_userinfo_string_still_rejected() -> None:
    with pytest.raises(ValueError, match="userinfo"):
        parse_asset_descriptor("postgres://u:p@h/db")
