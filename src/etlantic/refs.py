"""Typed output references for pipeline wiring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar, cast

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class OutputRef(Generic[T]):
    """A typed reference to a concrete producer port in a pipeline graph.

    Records the producing node, named output port, and output contract.
    Does not hold runtime dataframe or storage objects during authoring.
    """

    node_name: str
    port_name: str
    contract_type: type[T] | None
    pipeline_id: str | None = None
    node_kind: str = "step"
    producer_key: str | None = None

    @property
    def identity(self) -> str:
        """Stable identity for this output reference."""
        pipeline = self.pipeline_id or "<unbound>"
        return f"{pipeline}/{self.node_name}:{self.port_name}"

    def bind_pipeline(self, pipeline_id: str) -> OutputRef[T]:
        """Return a copy bound to a pipeline identity."""
        return OutputRef(
            node_name=self.node_name,
            port_name=self.port_name,
            contract_type=self.contract_type,
            pipeline_id=pipeline_id,
            node_kind=self.node_kind,
            producer_key=self.producer_key,
        )

    def with_node(
        self, node_name: str, *, pipeline_id: str | None = None
    ) -> OutputRef[T]:
        """Return a copy with a concrete node name."""
        return OutputRef(
            node_name=node_name,
            port_name=self.port_name,
            contract_type=self.contract_type,
            pipeline_id=pipeline_id if pipeline_id is not None else self.pipeline_id,
            node_kind=self.node_kind,
            producer_key=self.producer_key,
        )


def as_output_ref(value: Any, *, default_port: str = "result") -> OutputRef[Any] | None:
    """Normalize an Extract, Step attribute, or OutputRef into an OutputRef."""
    if isinstance(value, OutputRef):
        return value
    # Extract and Step expose .as_output_ref()
    converter = getattr(value, "as_output_ref", None)
    if callable(converter):
        return cast(OutputRef[Any], converter(default_port=default_port))
    return None
