# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false, reportUnusedFunction=false
"""Built-in record-oriented dataframe plugin used by the local engine."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from typing import Any

from etlantic.capabilities import PluginCapabilities
from etlantic.dataframe.helpers import (
    schema_dict,
    split_valid_invalid_records,
)
from etlantic.dataframe.protocol import (
    ArtifactOwnership,
    DataframeExecutionContext,
    DataframeOutputBundle,
    DataframePluginInfo,
    DataframeValidationOutcome,
    ValidationDecision,
)
from etlantic.inference import InferenceLimits, infer_source
from etlantic.interchange.tabular import InterchangeMechanism
from etlantic.storage.protocol import as_records, records_to_dicts

__version__ = "0.51.0"


def _iter_inference_records(value: Any, *, max_rows: int = 10_000):
    """Adapt record-like values without materializing generic iterables."""
    if isinstance(value, Mapping):
        yield value
        return
    to_dicts = getattr(value, "to_dicts", None)
    if callable(to_dicts):
        head = getattr(value, "head", None)
        if not callable(head):
            return
        bounded = head(max_rows)
        bounded_to_dicts = getattr(bounded, "to_dicts", None)
        if not callable(bounded_to_dicts):
            return
        value = bounded_to_dicts()
    elif hasattr(value, "to_dict") and callable(value.to_dict):
        head = getattr(value, "head", None)
        if not callable(head):
            return
        bounded = head(max_rows)
        bounded_to_dict = getattr(bounded, "to_dict", None)
        if not callable(bounded_to_dict):
            return
        with suppress(TypeError):
            value = bounded_to_dict(orient="records")
    if isinstance(value, (str, bytes, bytearray)):
        yield {"value": value}
        return
    try:
        iterator = iter(value)
    except TypeError:
        yield {"value": value}
        return
    for item in iterator:
        if hasattr(item, "model_dump"):
            yield item.model_dump()
        else:
            yield item


class LocalDataframePlugin:
    """Eager, record-oriented implementation with no optional dependencies."""

    def __init__(self) -> None:
        self._info = DataframePluginInfo(
            name="etlantic-local",
            engine="local",
            version=__version__,
            capabilities=PluginCapabilities(
                engine="local",
                dataframe=True,
                eager=True,
                lazy=False,
                schema_inspection=True,
                invalid_row_separation=True,
                interchange_mechanisms=frozenset(
                    {
                        InterchangeMechanism.RECORDS_FALLBACK.value,
                        InterchangeMechanism.NATIVE_FALLBACK.value,
                    }
                ),
                extras=frozenset({"local"}),
            ),
        )

    @property
    def info(self) -> DataframePluginInfo:
        return self._info

    def materialize_input(
        self,
        value: Any,
        *,
        contract_type: type[Any] | None,
        context: DataframeExecutionContext,
        port_name: str,
    ) -> list[dict[str, Any]]:
        return records_to_dicts(as_records(value, None))

    def invoke(
        self,
        *,
        callable_: Any,
        inputs: Mapping[str, Any],
        parameters: Mapping[str, Any],
        context: DataframeExecutionContext,
    ) -> Any:
        return callable_(**{**dict(parameters), **dict(inputs)})

    def normalize_output(
        self,
        result: Any,
        *,
        output_ports: tuple[str, ...],
        context: DataframeExecutionContext,
    ) -> DataframeOutputBundle:
        if isinstance(result, dict) and any(p in result for p in output_ports):
            valid = {p: result[p] for p in output_ports if p in result}
            return DataframeOutputBundle(
                valid=valid,
                invalid={
                    k: v
                    for k, v in result.items()
                    if k == "invalid" or k.endswith("_invalid")
                },
            )
        return DataframeOutputBundle(
            valid={(output_ports[0] if output_ports else "result"): result}
        )

    def validate_frame(
        self,
        value: Any,
        *,
        contract_type: type[Any] | None,
        context: DataframeExecutionContext,
        boundary: str,
        port_name: str | None = None,
    ):
        if contract_type is None:
            return value, ValidationDecision.SKIPPED, [], None
        valid, invalid, diagnostics = split_valid_invalid_records(
            list(value), contract_type=contract_type
        )
        valid = [
            item.model_dump() if hasattr(item, "model_dump") else item for item in valid
        ]
        if not invalid:
            return value, ValidationDecision.PASSED, diagnostics, None
        outcome = (
            context.validation_policy.input_outcome
            if boundary.startswith("input")
            else context.validation_policy.output_outcome
        )
        if outcome is DataframeValidationOutcome.FAIL:
            return value, ValidationDecision.FAILED, diagnostics, None
        if outcome is DataframeValidationOutcome.OBSERVE_ONLY:
            return value, ValidationDecision.OBSERVED, diagnostics, None
        if outcome is DataframeValidationOutcome.WARN:
            return value, ValidationDecision.WARNED, diagnostics, None
        return (
            valid,
            (
                ValidationDecision.QUARANTINED
                if outcome is DataframeValidationOutcome.QUARANTINE
                else ValidationDecision.REJECTED
            ),
            diagnostics,
            invalid,
        )

    def inspect_schema(
        self,
        value: Any,
        *,
        identity: str,
        limits: InferenceLimits | None = None,
    ) -> dict[str, Any] | None:
        result = infer_source(
            value, identity=identity, limits=limits or InferenceLimits()
        )
        payload = schema_dict(result.schema)
        if payload is not None and result.diagnostics:
            payload["diagnostics"] = [
                diagnostic.to_dict()
                for diagnostic in result.diagnostics
                if hasattr(diagnostic, "to_dict")
            ]
        return payload

    def ensure_ownership(
        self,
        value: Any,
        *,
        ownership: ArtifactOwnership,
        context: DataframeExecutionContext,
    ) -> Any:
        if not isinstance(value, list):
            return value
        return [
            dict(row)
            if isinstance(row, Mapping)
            else row.model_dump()
            if hasattr(row, "model_dump")
            else dict(row)
            for row in value
        ]

    def collect_if_needed(
        self, value: Any, *, context: DataframeExecutionContext
    ) -> Any:
        return value

    def to_records(self, value: Any, *, contract_type: type[Any] | None) -> list[Any]:
        return as_records(value, contract_type)

    def row_count(self, value: Any) -> int | None:
        return len(value) if isinstance(value, (list, tuple)) else None


def _logical(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return "string"
