"""Immutable edit operations for PipelineDefinition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from etlantic.authoring.builders import (
    add_node,
    connect,
    disconnect,
    remove_node,
    replace_nodes,
)
from etlantic.authoring.definition import NodeDefinition, PipelineDefinition
from etlantic.authoring.serialize import pipeline_fingerprint

EditOp = Literal[
    "add_node",
    "remove_node",
    "connect",
    "disconnect",
    "update_node",
    "clone",
    "move",
]


@dataclass(frozen=True, slots=True)
class EditCommand:
    """An immutable edit applied to a PipelineDefinition."""

    op: EditOp
    path: tuple[str, ...] = ()
    payload: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.op,
            "path": list(self.path),
            "payload": dict(self.payload or {}),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EditCommand:
        op = str(data["op"])
        if op == "update":
            op = "update_node"
        return cls(
            op=op,  # type: ignore[arg-type]
            path=tuple(str(p) for p in (data.get("path") or ())),
            payload=dict(data.get("payload") or {}),
        )


@dataclass(frozen=True, slots=True)
class EditResult:
    """Result of applying an edit command."""

    definition: PipelineDefinition
    fingerprint: str
    concurrency_token: str

    def to_dict(self) -> dict[str, Any]:
        from etlantic.authoring.serialize import pipeline_to_dict

        return {
            "fingerprint": self.fingerprint,
            "concurrency_token": self.concurrency_token,
            "definition": pipeline_to_dict(self.definition),
        }


def apply_edit(
    defn: PipelineDefinition,
    command: EditCommand,
    *,
    expected_token: str | None = None,
) -> EditResult:
    """Apply an immutable edit; fails closed on concurrency token mismatch."""
    current_fp = defn.fingerprint or pipeline_fingerprint(defn)
    if expected_token is not None and expected_token != current_fp:
        raise ValueError(
            f"Optimistic concurrency failure: expected {expected_token!r}, "
            f"have {current_fp!r}"
        )
    payload = dict(command.payload or {})
    updated = defn
    if command.op == "add_node":
        node = NodeDefinition.from_dict(payload["node"])
        updated = add_node(defn, node)
    elif command.op == "remove_node":
        name = str(payload.get("name") or (command.path[-1] if command.path else ""))
        updated = remove_node(defn, name)
    elif command.op == "connect":
        updated = connect(
            defn,
            str(payload["producer_node"]),
            str(payload["producer_port"]),
            str(payload["consumer_node"]),
            str(payload["consumer_port"]),
            producer_contract_id=payload.get("producer_contract_id"),
            consumer_contract_id=payload.get("consumer_contract_id"),
        )
    elif command.op == "disconnect":
        updated = disconnect(
            defn,
            str(payload["producer_node"]),
            str(payload["producer_port"]),
            str(payload["consumer_node"]),
            str(payload["consumer_port"]),
        )
    elif command.op == "update_node":
        name = str(payload["name"])
        node = NodeDefinition.from_dict(payload["node"])
        if node.name != name:
            raise ValueError(
                f"update_node requires payload.node.name == payload.name "
                f"({node.name!r} != {name!r}); rename is not supported"
            )
        if not any(n.name == name for n in defn.nodes):
            raise ValueError(f"Unknown node {name!r}")
        nodes = tuple(node if n.name == name else n for n in defn.nodes)
        updated = replace_nodes(defn, nodes)
    elif command.op == "clone":
        from etlantic.authoring.builders import clone_definition

        updated = clone_definition(defn)
    elif command.op == "move":
        # Reorder nodes; topology unchanged.
        order = [str(x) for x in payload.get("order") or ()]
        by_name = {n.name: n for n in defn.nodes}
        if set(order) != set(by_name):
            raise ValueError("move order must list every node exactly once")
        updated = replace_nodes(defn, tuple(by_name[name] for name in order))
    else:
        raise ValueError(f"Unsupported edit op {command.op!r}")

    fp = pipeline_fingerprint(updated)
    updated = updated.with_fingerprint(fp)
    return EditResult(definition=updated, fingerprint=fp, concurrency_token=fp)
