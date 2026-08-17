"""Immutable logical graph intermediate representation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class NodeKind(StrEnum):
    """Kinds of nodes in a logical pipeline graph."""

    SOURCE = "source"
    STEP = "step"
    SINK = "sink"
    SUBPIPELINE = "subpipeline"
    MAP = "map"
    REDUCE = "reduce"
    CONDITIONAL = "conditional"
    FAILURE = "failure"
    COMPENSATION = "compensation"


@dataclass(frozen=True, slots=True)
class PortSpec:
    """A typed port on a logical node."""

    name: str
    direction: str  # "input" | "output"
    contract_type: type[Any] | None
    contract_id: str | None
    required: bool = True
    role: str = "valid"  # "valid" | "invalid" | "side"


@dataclass(frozen=True, slots=True)
class ParameterSpec:
    """A typed parameter on a transformation step."""

    name: str
    value_type: type[Any] | None
    default: Any = ...
    has_default: bool = False
    value: Any = ...
    has_value: bool = False


@dataclass(frozen=True, slots=True)
class Edge:
    """A data-flow edge from a producer port to a consumer port."""

    producer_node: str
    producer_port: str
    consumer_node: str
    consumer_port: str
    producer_contract_id: str | None = None
    consumer_contract_id: str | None = None


@dataclass(frozen=True, slots=True)
class Node:
    """A node in the logical pipeline graph."""

    name: str
    kind: NodeKind
    identity: str
    contract_type: type[Any] | None = None
    contract_id: str | None = None
    binding: str | None = None
    transformation_id: str | None = None
    transformation_name: str | None = None
    inputs: tuple[PortSpec, ...] = ()
    outputs: tuple[PortSpec, ...] = ()
    parameters: tuple[ParameterSpec, ...] = ()
    # For subpipelines: nested graph identity and public port names
    nested_pipeline_id: str | None = None
    nested_graph: LogicalGraph | None = None
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))


@dataclass(frozen=True, slots=True)
class LogicalGraph:
    """Immutable, deterministic logical pipeline graph."""

    pipeline_id: str
    pipeline_name: str
    nodes: tuple[Node, ...] = ()
    edges: tuple[Edge, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def node_map(self) -> dict[str, Node]:
        """Return nodes keyed by name in declaration order."""
        return {node.name: node for node in self.nodes}

    def node_names(self) -> tuple[str, ...]:
        """Return node names in declaration order."""
        return tuple(node.name for node in self.nodes)

    def edges_from(self, node_name: str) -> tuple[Edge, ...]:
        """Return edges whose producer is ``node_name``."""
        return tuple(e for e in self.edges if e.producer_node == node_name)

    def edges_to(self, node_name: str) -> tuple[Edge, ...]:
        """Return edges whose consumer is ``node_name``."""
        return tuple(e for e in self.edges if e.consumer_node == node_name)


# Forward reference resolution for Node.nested_graph
Node.__annotations__["nested_graph"] = LogicalGraph | None
