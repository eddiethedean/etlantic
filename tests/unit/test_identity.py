"""Unit tests for identity helpers."""

from pipelantic.identity import (
    contract_id,
    identity_slug,
    implementation_id,
    node_id,
    port_id,
    published_contract_id,
    qualified_type_id,
)


def test_qualified_type_id_is_stable() -> None:
    class Demo:
        pass

    first = qualified_type_id(Demo)
    second = qualified_type_id(Demo)
    assert first == second
    assert "Demo" in first
    assert ":" in first


def test_node_and_port_ids() -> None:
    assert node_id("pkg:Pipe", "raw") == "pkg:Pipe/raw"
    assert port_id("pkg:Pipe/raw", "result") == "pkg:Pipe/raw:result"
    assert implementation_id("pkg:T", "polars") == "pkg:T/polars"


def test_contract_id_uses_type() -> None:
    from tests.conftest import Customer

    assert contract_id(Customer) == qualified_type_id(Customer)


def test_published_contract_id_from_contractmodel() -> None:
    from tests.conftest import Customer

    assert published_contract_id(Customer) == "customer"


def test_identity_slug() -> None:
    assert identity_slug("pkg.mod:Class") == "pkg.mod__class"
