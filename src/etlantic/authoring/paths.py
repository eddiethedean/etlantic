"""Stable document paths for edits and diagnostics."""

from __future__ import annotations


def node_path(name: str) -> tuple[str, ...]:
    return ("nodes", name)


def port_path(node: str, direction: str, port: str) -> tuple[str, ...]:
    return ("nodes", node, direction, port)


def edge_path(
    producer_node: str,
    producer_port: str,
    consumer_node: str,
    consumer_port: str,
) -> tuple[str, ...]:
    return (
        "edges",
        f"{producer_node}.{producer_port}->{consumer_node}.{consumer_port}",
    )


def contract_path(identity: str) -> tuple[str, ...]:
    return ("contracts", identity)


def transformation_path(identity: str) -> tuple[str, ...]:
    return ("transformations", identity)


def field_path(contract_id: str, field_name: str) -> tuple[str, ...]:
    return ("contracts", contract_id, "fields", field_name)
