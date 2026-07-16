"""Pandas dataframe plugin for Pipelantic."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd

from pipelantic.capabilities import PluginCapabilities
from pipelantic.dataframe.arrow import arrow_available, to_arrow_table
from pipelantic.dataframe.helpers import (
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

__version__ = "0.6.0"


def create_plugin() -> PandasDataframePlugin:
    """Entry-point factory."""
    return PandasDataframePlugin()


class PandasDataframePlugin:
    """Compatibility Pandas dataframe execution plugin (eager only)."""

    def __init__(self) -> None:
        caps = PluginCapabilities(
            engine="pandas",
            async_execution=True,
            dataframe=True,
            eager=True,
            lazy=False,
            arrow_import=arrow_available(),
            arrow_export=arrow_available(),
            zero_copy=False,
            schema_inspection=True,
            invalid_row_separation=True,
            cancellation=False,
            thread_safe=False,
            extras=frozenset({"pandas"}),
        )
        self._info = DataframePluginInfo(
            name="pipelantic-pandas",
            engine="pandas",
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
        if isinstance(value, pd.DataFrame):
            return value.copy(deep=False)
        table = to_arrow_table(value)
        if table is not None:
            return table.to_pandas()
        # Polars → pandas without Arrow
        if type(value).__module__.startswith("polars"):
            if hasattr(value, "collect"):
                value = value.collect()
            if hasattr(value, "to_pandas"):
                return value.to_pandas()
        records = as_records(value, None)
        rows = records_to_dicts(records)
        if not rows:
            columns = list(getattr(contract_type, "model_fields", {}) or {})
            return pd.DataFrame(columns=columns)
        return pd.DataFrame(rows)

    def invoke(
        self,
        *,
        callable_: Any,
        inputs: Mapping[str, Any],
        parameters: Mapping[str, Any],
        context: DataframeExecutionContext,
    ) -> Any:
        # Inputs take precedence over parameters when names collide.
        kwargs = {**dict(parameters), **dict(inputs)}
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
    ) -> tuple[Any, ValidationDecision, list[dict[str, Any]], Any | None]:
        outcome = (
            context.validation_policy.input_outcome
            if boundary.startswith("input")
            else context.validation_policy.output_outcome
        )
        if contract_type is None:
            return value, ValidationDecision.SKIPPED, [], None
        frame = value
        if not isinstance(frame, pd.DataFrame):
            frame = self.materialize_input(
                frame,
                contract_type=contract_type,
                context=context,
                port_name=port_name or "value",
            )
        rows = frame.to_dict(orient="records")
        valid, invalid, diagnostics = split_valid_invalid_records(
            rows, contract_type=contract_type
        )
        # Diagnose object-dtype ambiguity
        for col in frame.columns:
            if str(frame[col].dtype) == "object":
                diagnostics.append(
                    {
                        "code": "PMDF420",
                        "message": (
                            f"Column {col!r} uses object dtype; logical type "
                            "may be ambiguous."
                        ),
                        "severity": "warning",
                    }
                )
        if not invalid:
            return frame, ValidationDecision.PASSED, diagnostics, None
        if outcome is DataframeValidationOutcome.FAIL:
            return frame, ValidationDecision.FAILED, diagnostics, None
        if outcome is DataframeValidationOutcome.OBSERVE_ONLY:
            return frame, ValidationDecision.OBSERVED, diagnostics, None
        if outcome is DataframeValidationOutcome.WARN:
            return frame, ValidationDecision.WARNED, diagnostics, None
        valid_frame = (
            pd.DataFrame(records_to_dicts(valid)) if valid else frame.iloc[0:0]
        )
        invalid_frame = pd.DataFrame(records_to_dicts(invalid))
        decision = (
            ValidationDecision.QUARANTINED
            if outcome is DataframeValidationOutcome.QUARANTINE
            else ValidationDecision.REJECTED
        )
        return valid_frame, decision, diagnostics, invalid_frame

    def inspect_schema(self, value: Any, *, identity: str) -> dict[str, Any] | None:
        if not isinstance(value, pd.DataFrame):
            return schema_dict(schema_from_contract(None, identity=identity))
        fields = []
        for name, dtype in value.dtypes.items():
            fields.append(
                {
                    "name": str(name),
                    "logical_type": _pandas_logical(dtype),
                    "required": True,
                    "nullable": bool(value[name].isna().any()) if len(value) else True,
                }
            )
        from pipelantic.dataframe.helpers import normalized_from_field_dicts

        return schema_dict(normalized_from_field_dicts(fields, identity=identity))

    def ensure_ownership(
        self,
        value: Any,
        *,
        ownership: ArtifactOwnership,
        context: DataframeExecutionContext,
    ) -> Any:
        if not isinstance(value, pd.DataFrame):
            return value
        # Always copy on fan-out / explicit copied ownership to prevent mutation.
        if ownership in {
            ArtifactOwnership.COPIED,
            ArtifactOwnership.SHARED,
        }:
            return value.copy(deep=True)
        return value

    def collect_if_needed(
        self,
        value: Any,
        *,
        context: DataframeExecutionContext,
    ) -> Any:
        return value

    def to_records(
        self,
        value: Any,
        *,
        contract_type: type[Any] | None,
    ) -> list[Any]:
        if isinstance(value, pd.DataFrame):
            return as_records(value.to_dict(orient="records"), contract_type)
        return as_records(value, contract_type)

    def row_count(self, value: Any) -> int | None:
        if isinstance(value, pd.DataFrame):
            return len(value)
        if isinstance(value, list):
            return len(value)
        return None


def _pandas_logical(dtype: Any) -> str:
    name = str(dtype)
    if name.startswith("int") or name.startswith("UInt") or "Int" in name:
        return "integer"
    if name.startswith("float") or "Float" in name:
        return "number"
    if name == "bool" or name.startswith("boolean"):
        return "boolean"
    if "datetime" in name:
        return "timestamp"
    if name == "object" or name == "string" or name.startswith("str"):
        return "string"
    if "category" in name:
        return "string"
    return "string"
