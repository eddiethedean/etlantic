"""Experimental FakeMcpServer method-authority tests (live client skipped)."""

from __future__ import annotations

import os

import pytest

pytest.importorskip("etlantic_mcp")

from etlantic.agents.catalog import FORBIDDEN_ACTIONS
from etlantic.agents.mcp_trust import mcp_server_allowed
from etlantic.profile import Profile
from etlantic_mcp import FakeMcpServer, live_configured

pytestmark = pytest.mark.mcp


def test_fake_read_only_methods() -> None:
    server = FakeMcpServer()
    ok = server.call("inspect", target="tests.fixtures.sample_pipeline:SamplePipeline")
    assert ok["ok"] is True
    denied = server.call("run.submit")
    assert denied["ok"] is False
    assert denied["diagnostic"]["code"] == "PMMCP100"
    secrets = server.call("secret.resolve")
    assert secrets["diagnostic"]["code"] == "PMMCP150"
    expand = server.call("inspect", grant_tools=["run.submit"])
    assert expand["diagnostic"]["code"] == "PMMCP110"


def test_fake_catalog_excludes_mutating_methods() -> None:
    server = FakeMcpServer()
    methods = set(server.list_methods())
    assert not (methods & FORBIDDEN_ACTIONS)
    assert "run.submit" not in methods
    assert "schedule.trigger" not in methods


def test_production_allowlist_fail_closed() -> None:
    profile = Profile(
        name="production",
        security_mode="production",
        plugin_allowlist={},
    )
    allowed, diag = mcp_server_allowed(
        profile, "etlantic-mcp", version="0.48.0", selected=True
    )
    assert allowed is False
    assert diag is not None
    pinned = Profile(
        name="production",
        security_mode="production",
        plugin_allowlist={"etlantic-mcp": "==0.48.0"},
    )
    ok, _ = mcp_server_allowed(pinned, "etlantic-mcp", version="0.48.0", selected=True)
    assert ok is True


@pytest.mark.skipif(
    not live_configured() and not os.environ.get("ETLANTIC_MCP_LIVE"),
    reason="048-M-01 live MCP client skipped",
)
def test_live_mcp_client_skipped() -> None:
    pytest.skip("048-M-01 live MCP-client interop remains deferred")
