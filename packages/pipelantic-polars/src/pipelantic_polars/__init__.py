"""Polars dataframe plugin for Pipelantic."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import polars as pl

from pipelantic.capabilities import PluginCapabilities
from pipelantic.dataframe.arrow import arrow_available, to_arrow_table
from pipelantic.dataframe.helpers import (
    logical_type_from_annotation,
    schema_dict,
    schema_from_contract,
    split_valid_invalid_records,
)
from pipelantic.dataframe.protocol import (
    DATAFRAME_PROTOCOL_VERSION,
    ArtifactOwnership,
    DataframeExecutionContext,
    DataframeMetrics,
    DataframeOutputBundle,
    DataframePluginInfo,
    DataframeValidationOutcome,
    ValidationDecision,
)
from pipelantic.storage.protocol import as_records, records_to_dicts

__version__ = "0.5.0"


def create_plugin() -> PolarsDataframePlugin:
    """Entry-point factory."""
    return PolarsDataframePlugin()


class PolarsDataframePlugin:
    """Reference Polars dataframe execution plugin."""

    def __init__(self) -> None:
        caps = PluginCapabilities(
            engine="polars",
            async_execution=True,
            dataframe=True,
            eager=True,
            lazy=True,
            arrow_import=arrow_available(),
            arrow_export=arrow_available(),
            zero_copy=arrow_available(),
            schema_inspection=True,
            invalid_row_separation=True,
            cancellation=True,
            thread_safe=True,
            extras=frozenset({"polars"}),
        )
        self._info = DataframePluginInfo(
            name="pipelantic-polars",
            engine="polars",
            version=__version__,
            protocol_version=DATAFRAME_PROTOCOL_VERSION,
            capabilities=caps,
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
    ) -> Any:
        if isinstance(value, (pl.DataFrame, pl.LazyFrame)):
            return value
        table = to_arrow_table(value)
        if table is not None:
            return pl.from_arrow(table)
        records = as_records(value, None)
        rows = records_to_dicts(records)
        if not rows:
            schema = self._empty_schema(contract_type)
            return pl.DataFrame(schema=schema)
        return pl.DataFrame(rows)

    def invoke(
        self,
        *,
        callable_: Any,
        inputs: Mapping[str, Any],
        parameters: Mapping[str, Any],
        context: DataframeExecutionContext,
    ) -> Any:
        kwargs = {**dict(inputs), **dict(parameters)}
        return callable_(**kwargs)

    def normalize_output(
        self,
        result: Any,
        *,
        output_ports: tuple[str, ...],
        context: DataframeExecutionContext,
    ) -> DataframeOutputBundle:
        metrics = DataframeMetrics(converted=False)
        if isinstance(result, dict) and any(p in result for p in output_ports):
            valid = {k: result[k] for k in output_ports if k in result}
            invalid = {
                k: v
                for k, v in result.items()
                if k.endswith("_invalid") or k == "invalid"
            }
            side = {
                k: v for k, v in result.items() if k not in valid and k not in invalid
            }
            return DataframeOutputBundle(
                valid=valid,
                invalid=invalid,
                side=side,
                metrics=metrics,
            )
        port = output_ports[0] if output_ports else "result"
        return DataframeOutputBundle(valid={port: result}, metrics=metrics)

    def validate_frame(
        self,
        value: Any,
        *,
        contract_type: type[Any] | None,
        context: DataframeExecutionContext,
        boundary: str,
        port_name: str | None = None,
    ) -> tuple[Any, ValidationDecision, list[dict[str, Any]]]:
        outcome = (
            context.validation_policy.input_outcome
            if boundary.startswith("input")
            else context.validation_policy.output_outcome
        )
        if contract_type is None:
            return value, ValidationDecision.SKIPPED, []
        frame = value
        if isinstance(frame, pl.LazyFrame):
            # Avoid hidden collection: only validate schema against declared fields.
            schema = schema_from_contract(
                contract_type, identity=contract_type.__name__
            )
            if schema is None:
                return frame, ValidationDecision.SKIPPED, []
            names = set(frame.collect_schema().names())
            missing = [
                f.name for f in schema.fields if f.required and f.name not in names
            ]
            if missing and outcome is DataframeValidationOutcome.FAIL:
                return (
                    frame,
                    ValidationDecision.FAILED,
                    [
                        {
                            "code": "PMDF411",
                            "message": f"Missing required columns: {missing}",
                            "severity": "error",
                        }
                    ],
                )
            return frame, ValidationDecision.PASSED, []

        if not isinstance(frame, pl.DataFrame):
            frame = self.materialize_input(
                frame,
                contract_type=contract_type,
                context=context,
                port_name=port_name or "value",
            )
        rows = frame.to_dicts()
        valid, invalid, diagnostics = split_valid_invalid_records(
            rows, contract_type=contract_type
        )
        if not invalid:
            return frame, ValidationDecision.PASSED, []
        if outcome is DataframeValidationOutcome.FAIL:
            return frame, ValidationDecision.FAILED, diagnostics
        if outcome is DataframeValidationOutcome.OBSERVE_ONLY:
            return frame, ValidationDecision.OBSERVED, diagnostics
        if outcome is DataframeValidationOutcome.WARN:
            return frame, ValidationDecision.WARNED, diagnostics
        # reject / quarantine → split frames
        valid_frame = pl.DataFrame(records_to_dicts(valid)) if valid else frame.clear()
        return valid_frame, ValidationDecision.REJECTED, diagnostics

    def inspect_schema(self, value: Any, *, identity: str) -> dict[str, Any] | None:
        if isinstance(value, pl.LazyFrame):
            schema = value.collect_schema()
            fields = [
                {
                    "name": name,
                    "logical_type": _polars_logical(dtype),
                    "required": True,
                    "nullable": True,
                }
                for name, dtype in schema.items()
            ]
            from pipelantic.dataframe.helpers import normalized_from_field_dicts

            return schema_dict(normalized_from_field_dicts(fields, identity=identity))
        if isinstance(value, pl.DataFrame):
            fields = [
                {
                    "name": name,
                    "logical_type": _polars_logical(dtype),
                    "required": True,
                    "nullable": True,
                }
                for name, dtype in zip(value.columns, value.dtypes, strict=False)
            ]
            from pipelantic.dataframe.helpers import normalized_from_field_dicts

            return schema_dict(normalized_from_field_dicts(fields, identity=identity))
        return schema_dict(schema_from_contract(None, identity=identity))

    def ensure_ownership(
        self,
        value: Any,
        *,
        ownership: ArtifactOwnership,
        context: DataframeExecutionContext,
    ) -> Any:
        if ownership is ArtifactOwnership.COPIED and isinstance(value, pl.DataFrame):
            return value.clone()
        if ownership is ArtifactOwnership.COPIED and isinstance(value, pl.LazyFrame):
            return value  # immutable plan; cloning not required
        return value

    def collect_if_needed(
        self,
        value: Any,
        *,
        context: DataframeExecutionContext,
    ) -> Any:
        if context.collect and isinstance(value, pl.LazyFrame):
            return value.collect()
        return value

    def to_records(
        self,
        value: Any,
        *,
        contract_type: type[Any] | None,
    ) -> list[Any]:
        if isinstance(value, pl.LazyFrame):
            value = value.collect()
        if isinstance(value, pl.DataFrame):
            return as_records(value.to_dicts(), contract_type)
        return as_records(value, contract_type)

    def row_count(self, value: Any) -> int | None:
        if isinstance(value, pl.DataFrame):
            return value.height
        if isinstance(value, pl.LazyFrame):
            return None
        if isinstance(value, list):
            return len(value)
        return None

    def _empty_schema(self, contract_type: type[Any] | None) -> dict[str, pl.DataType]:
        if contract_type is None or not hasattr(contract_type, "model_fields"):
            return {}
        out: dict[str, pl.DataType] = {}
        for name, field_info in contract_type.model_fields.items():
            out[name] = _annotation_to_polars(field_info.annotation)
        return out


def _annotation_to_polars(annotation: Any) -> pl.DataType:
    logical = logical_type_from_annotation(annotation)
    mapping = {
        "string": pl.Utf8,
        "integer": pl.Int64,
        "number": pl.Float64,
        "boolean": pl.Boolean,
        "timestamp": pl.Datetime,
        "date": pl.Date,
        "decimal": pl.Decimal,
    }
    return mapping.get(logical, pl.Utf8)


def _polars_logical(dtype: Any) -> str:
    name = str(dtype)
    if "Int" in name or "UInt" in name:
        return "integer"
    if "Float" in name:
        return "number"
    if "Bool" in name:
        return "boolean"
    if "Date" in name and "Time" not in name:
        return "date"
    if "Datetime" in name or "Timestamp" in name:
        return "timestamp"
    if "Decimal" in name:
        return "decimal"
    if "List" in name or "Array" in name:
        return "array"
    if "Struct" in name:
        return "object"
    return "string"
