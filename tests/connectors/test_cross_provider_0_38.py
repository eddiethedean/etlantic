"""Wave 7 cross-provider burn-in (038-A01, A17, A19, A20 soft-continue)."""

from __future__ import annotations

import json
from importlib.metadata import EntryPoint
from pathlib import Path
from unittest.mock import MagicMock

import anyio
import pytest
from etlantic_s3 import create_source as create_s3_source
from etlantic_snowflake import create_source as create_snowflake_source
from tests.connectors.third_party_echo import (
    PROVIDER as ECHO_PROVIDER,
)
from tests.connectors.third_party_echo import (
    create_echo_third_party_source,
)

from etlantic import Data, Extract, Load, Pipeline, Profile
from etlantic.connectors.discovery import (
    SOURCE_CONNECTORS_GROUP,
    discover_source_connectors,
)
from etlantic.connectors.local_files import create_local_files_source
from etlantic.connectors.maturity import ConnectorMaturity
from etlantic.connectors.models import ConnectorBinding
from etlantic.plan.planner import plan_pipeline
from etlantic.plugin_lifecycle import DiscoveredPlugin
from etlantic.registry import PlanningContext
from etlantic.testing.connectors import run_source_connector_conformance_suite

MATRIX_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "11_DEVELOPMENT"
    / "CONNECTOR_CAPABILITY_MATRIX_0_38.json"
)


class RawEvent(Data):
    event_id: str
    payload: str


class PortableOrders(Pipeline):
    """Logical topology shared across provider profile swaps (038-A01 / A17)."""

    src = Extract[RawEvent](asset="orders_in")
    out = Load[RawEvent](input=src, asset="orders_out")


def _graph_signature(plan) -> tuple[tuple[str, str, str | None], ...]:
    nodes = plan.logical_graph.nodes
    return tuple(sorted((n.name, n.kind.value, n.binding) for n in nodes))


def _profile_for(provider: str, *, mode: str = "snapshot") -> Profile:
    """Same asset names; provider/config swap only (no Extract rewrite)."""
    if provider == "local-files":
        source = {
            "provider": "local-files",
            "format": "csv",
            "root": "inbox",
            "root_ref": "landing",
            "glob": "*.csv",
            "mode": mode,
            "required_capabilities": [
                "source.batch_snapshot",
                "format.csv",
            ],
        }
    elif provider == "s3":
        source = {
            "provider": "s3",
            "format": "parquet",
            "config": {
                "bucket": "lake",
                "prefix": "orders",
                "pointer_key": "orders.commit",
                "mode": mode,
            },
            "required_capabilities": ["source.batch_snapshot"],
        }
    elif provider == "snowflake":
        source = {
            "provider": "snowflake",
            "config": {
                "table": "ORDERS",
                "schema": "PUBLIC",
                "mode": mode,
            },
            "required_capabilities": ["source.batch_snapshot"],
        }
    else:
        raise AssertionError(f"unknown provider {provider}")
    return Profile(
        name=f"burnin-{provider}-{mode}",
        security_mode="development",
        assets={
            "orders_in": source,
            "orders_out": "memory://orders_out",
        },
    )


def test_038_a01_same_pipeline_local_s3_snowflake_topology() -> None:
    """Logical graph/contracts unchanged; connector resolutions differ."""
    signatures: dict[str, tuple] = {}
    resolutions: dict[str, str] = {}
    for provider in ("local-files", "s3", "snowflake"):
        profile = _profile_for(provider)
        plan = plan_pipeline(
            PortableOrders,
            context=PlanningContext.create(profile=profile),
        )
        signatures[provider] = _graph_signature(plan)
        binding = plan.bindings["src"]
        resolutions[provider] = binding.provider
        assert binding.kind == "source"
        assert "live_files" not in (binding.metadata or {})
        # Static plans never list concrete files.
        assert "files" not in (binding.metadata or {})
        assert plan.logical_graph is not None

    assert signatures["local-files"] == signatures["s3"] == signatures["snowflake"]
    assert resolutions == {
        "local-files": "local-files",
        "s3": "s3",
        "snowflake": "snowflake",
    }


def test_038_a17_profile_mode_switch_no_topology_rewrite() -> None:
    snap = plan_pipeline(
        PortableOrders,
        context=PlanningContext.create(
            profile=_profile_for("local-files", mode="snapshot")
        ),
    )
    incr = plan_pipeline(
        PortableOrders,
        context=PlanningContext.create(
            profile=_profile_for("local-files", mode="incremental")
        ),
    )
    assert _graph_signature(snap) == _graph_signature(incr)
    assert snap.bindings["src"].mode == "snapshot"
    assert incr.bindings["src"].mode == "incremental"
    # Config fingerprints differ by mode but topology does not.
    assert (
        snap.bindings["src"].config_fingerprint
        != incr.bindings["src"].config_fingerprint
    )


def test_038_a19_capability_matrix_matches_connectors() -> None:
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    assert matrix["schema"] == "etlantic.connector_capability_matrix/1"
    providers = matrix["providers"]

    local = create_local_files_source()
    local_info = local.info()
    assert local_info.maturity is ConnectorMaturity.PREVIEW
    assert set(local_info.capabilities) == set(
        providers["local-files"]["source_capabilities"]
    )

    s3 = create_s3_source()
    assert s3.info().maturity is ConnectorMaturity.EXPERIMENTAL
    assert set(s3.info().capabilities) == set(providers["s3"]["source_capabilities"])

    snow = create_snowflake_source()
    assert snow.info().maturity is ConnectorMaturity.EXPERIMENTAL
    assert set(snow.info().capabilities) == set(
        providers["snowflake"]["source_capabilities"]
    )

    from etlantic_iceberg import create_source as create_iceberg_source

    from etlantic_sql.connectors import create_source as create_pg_source

    iceberg = create_iceberg_source()
    assert iceberg.info().maturity is ConnectorMaturity.EXPERIMENTAL
    assert set(iceberg.info().capabilities) == set(
        providers["iceberg"]["source_capabilities"]
    )

    pg = create_pg_source()
    assert pg.info().maturity is ConnectorMaturity.EXPERIMENTAL
    assert set(pg.info().capabilities) == set(
        providers["postgresql"]["source_capabilities"]
    )


def test_binding_fingerprint_stable_for_identical_public_config() -> None:
    left = ConnectorBinding(
        provider="s3",
        config={"bucket": "lake", "prefix": "orders", "pointer_key": "orders.commit"},
        mode="snapshot",
        required_capabilities=("source.batch_snapshot",),
    )
    right = ConnectorBinding(
        provider="s3",
        config={"bucket": "lake", "prefix": "orders", "pointer_key": "orders.commit"},
        mode="snapshot",
        required_capabilities=("source.batch_snapshot",),
    )
    assert left.config_fingerprint == right.config_fingerprint
    assert left.to_dict()["config_fingerprint"] == right.config_fingerprint


def test_038_x01_in_repo_third_party_entry_point(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Soft-continue for independent connector: EP load + public conformance."""
    factory = create_echo_third_party_source
    ep = MagicMock(spec=EntryPoint)
    ep.name = ECHO_PROVIDER
    ep.value = "tests.connectors.third_party_echo:create_echo_third_party_source"
    ep.group = SOURCE_CONNECTORS_GROUP
    ep.load = factory
    discovered = DiscoveredPlugin(
        group=SOURCE_CONNECTORS_GROUP,
        name=ECHO_PROVIDER,
        target=ep.value,
        distribution_name="etlantic-plugin-echo-fake",
        distribution_version="0.38.0",
        entry_point=ep,
    )

    def _discover(group: str):
        if group == SOURCE_CONNECTORS_GROUP:
            return [discovered], []
        return [], []

    monkeypatch.setattr(
        "etlantic.connectors.discovery.discover_entry_points", _discover
    )
    items, diags = discover_source_connectors()
    assert not diags
    assert any(item.name == ECHO_PROVIDER for item in items)
    loaded = items[0].entry_point.load()
    # load() may return the factory or the instance depending on EP shape
    connector = loaded() if callable(loaded) and not hasattr(loaded, "info") else loaded
    if callable(connector) and not hasattr(connector, "info"):
        connector = connector()
    assert connector.info().provider == ECHO_PROVIDER
    # Public imports only — no private underscore modules in the fake package.
    import tests.connectors.third_party_echo as echo_mod

    source = echo_mod.__file__ or ""
    text = Path(source).read_text(encoding="utf-8")
    assert "etlantic.connectors._" not in text
    assert "from etlantic._" not in text

    # Capability-selected suite: info-only proves public protocol surface without
    # requiring local-files filesystem semantics on the third-party stub.
    results = run_source_connector_conformance_suite(connector, capabilities=())
    assert any(r["case"] == "info" and r.get("ok") for r in results)
    assert all(r.get("ok") for r in results)


def test_provider_plan_read_identity_scheme_only() -> None:
    """038-A01 companion: connector plan_read never lists live files."""

    async def _check() -> None:
        for factory in (
            create_local_files_source,
            create_s3_source,
            create_snowflake_source,
        ):
            connector = factory()
            binding = {
                "provider": connector.info().provider,
                "format": "csv",
                "root_ref": "landing",
                "mode": "snapshot",
                "config": {
                    "bucket": "lake",
                    "prefix": "x",
                    "pointer_key": "x.commit",
                    "table": "ORDERS",
                    "root_ref": "landing",
                    "mode": "snapshot",
                },
            }
            plan = await connector.plan_read(
                binding=binding, context={"run_id": "burnin"}
            )
            payload = plan.to_dict()
            encoded = json.dumps(payload, sort_keys=True)
            assert "inbox/" not in encoded
            assert ".csv" not in encoded or plan.provider == "local-files"
            # listing_intent may include glob patterns, never concrete file paths
            intent = plan.listing_intent or {}
            assert "files" not in intent
            assert "paths" not in intent

    anyio.run(_check)
