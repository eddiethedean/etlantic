"""DataFusion dataframe plugin.

The optional ``datafusion`` and ``pyarrow`` imports are deliberately lazy so
installing ETLantic's core never imports a native engine.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from etlantic.capabilities import PluginCapabilities
from etlantic.dataframe.helpers import (
    normalized_from_field_dicts,
    schema_dict,
    split_valid_invalid_records,
)
from etlantic.dataframe.protocol import (
    DATAFRAME_PROTOCOL_VERSION,
    ArtifactOwnership,
    DataframeExecutionContext,
    DataframeOutputBundle,
    DataframePluginInfo,
    DataframeValidationOutcome,
    ValidationDecision,
)
from etlantic.interchange.tabular import InterchangeMechanism
from etlantic.quality.model import PORTABLE_QUALITY_CAPABILITIES
from etlantic.reliability import WRITE_CAPABILITY_EXTRAS
from etlantic.storage.protocol import as_records, records_to_dicts

__version__ = "0.50.0"


def _imports() -> tuple[Any, Any]:
    try:
        import pyarrow as pa  # noqa: I001
        from datafusion import SessionContext
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise ImportError(
            "DataFusion execution requires optional dependencies; install "
            "etlantic-datafusion[datafusion]."
        ) from exc
    return SessionContext, pa


class DataFusionPlugin:
    """DataFusion plugin implementing the dataframe protocol."""

    def __init__(self) -> None:
        mechanisms = frozenset(
            {
                InterchangeMechanism.NATIVE_FALLBACK.value,
                InterchangeMechanism.RECORDS_FALLBACK.value,
                InterchangeMechanism.ARROW_C_DATA.value,
                InterchangeMechanism.ARROW_C_STREAM.value,
                InterchangeMechanism.ARROW_IPC_STREAM.value,
            }
        )
        caps = PluginCapabilities(
            engine="datafusion",
            async_execution=True,
            dataframe=True,
            eager=True,
            lazy=True,
            arrow_import=True,
            arrow_export=True,
            schema_inspection=True,
            invalid_row_separation=True,
            thread_safe=False,
            interchange_mechanisms=mechanisms,
            extras=frozenset({"datafusion"})
            | PORTABLE_QUALITY_CAPABILITIES
            | frozenset(
                e
                for e in WRITE_CAPABILITY_EXTRAS
                if e in {"write.append", "write.overwrite"}
            ),
        )
        self._info = DataframePluginInfo(
            name="etlantic-datafusion",
            engine="datafusion",
            version=__version__,
            protocol_version=DATAFRAME_PROTOCOL_VERSION,
            capabilities=caps,
        )

    @property
    def info(self) -> DataframePluginInfo:
        return self._info

    def materialize(self, *args: Any, **kwargs: Any) -> Any:
        """Compatibility alias for callers of the dataframe protocol."""
        if not args and not kwargs:
            raise TypeError("materialize requires a value")
        return self.materialize_input(*args, **kwargs)

    def from_records(
        self, rows: list[Any], *, contract_type: type[Any] | None = None
    ) -> Any:
        """Construct a DataFusion frame from Python records."""
        context = DataframeExecutionContext(
            run_id="direct",
            pipeline_id="direct",
            plan_id="direct",
            step_name="from_records",
            engine="datafusion",
        )
        return self.materialize_input(
            rows, contract_type=contract_type, context=context, port_name="records"
        )

    def execute_transformation(self, *args: Any, **kwargs: Any) -> Any:
        """Compatibility helper delegating to a callable transformation."""
        callable_ = kwargs.pop("callable_", kwargs.pop("callable", None))
        if callable_ is None and args and callable(args[0]):
            callable_, args = args[0], args[1:]
        if callable_ is None:
            raise TypeError("execute_transformation requires callable_=")
        return callable_(*args, **kwargs)

    def materialize_input(
        self,
        value: Any,
        *,
        contract_type: type[Any] | None,
        context: DataframeExecutionContext,
        port_name: str,
    ) -> Any:
        SessionContext, pa = _imports()
        if type(value).__module__.startswith("datafusion") and hasattr(value, "schema"):
            return value
        if hasattr(value, "to_arrow"):
            value = value.to_arrow()
        elif hasattr(value, "collect"):
            collected = value.collect()
            value = (
                collected.to_arrow() if hasattr(collected, "to_arrow") else collected
            )
        if not isinstance(value, pa.Table):
            rows = records_to_dicts(as_records(value, None))
            fields = list(getattr(contract_type, "model_fields", {}) or {})
            if not rows:
                value = pa.table({name: pa.array([]) for name in fields})
            else:
                value = pa.Table.from_pylist(rows)
        return SessionContext().from_arrow(value)

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
            invalid = {
                k: v
                for k, v in result.items()
                if k == "invalid" or k.endswith("_invalid")
            }
            side = {
                k: v for k, v in result.items() if k not in valid and k not in invalid
            }
            return DataframeOutputBundle(valid=valid, invalid=invalid, side=side)
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
    ) -> tuple[Any, ValidationDecision, list[dict[str, Any]], Any | None]:
        if contract_type is None:
            return value, ValidationDecision.SKIPPED, [], None
        rows = self.to_records(value, contract_type=None)
        valid, invalid, diagnostics = split_valid_invalid_records(
            rows, contract_type=contract_type
        )
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
            self.materialize_input(
                valid,
                contract_type=contract_type,
                context=context,
                port_name=port_name or "value",
            ),
            (
                ValidationDecision.QUARANTINED
                if outcome is DataframeValidationOutcome.QUARANTINE
                else ValidationDecision.REJECTED
            ),
            diagnostics,
            invalid,
        )

    def inspect_schema(self, value: Any, *, identity: str) -> dict[str, Any] | None:
        try:
            schema = (
                value.schema()
                if callable(getattr(value, "schema", None))
                else value.schema
            )
            fields = [
                {
                    "name": str(name),
                    "logical_type": _arrow_logical(field.type),
                    "required": not field.nullable,
                    "nullable": field.nullable,
                }
                for name, field in zip(schema.names, schema, strict=True)
            ]
            return schema_dict(normalized_from_field_dicts(fields, identity=identity))
        except Exception:
            return None

    def ensure_ownership(
        self,
        value: Any,
        *,
        ownership: ArtifactOwnership,
        context: DataframeExecutionContext,
    ) -> Any:
        return value

    def collect_if_needed(
        self, value: Any, *, context: DataframeExecutionContext
    ) -> Any:
        if (
            context.collect
            and type(value).__module__.startswith("datafusion")
            and hasattr(value, "to_arrow_table")
        ):
            return value.to_arrow_table()
        return value

    def to_records(self, value: Any, *, contract_type: type[Any] | None) -> list[Any]:
        if type(value).__module__.startswith("datafusion") and hasattr(
            value, "to_arrow_table"
        ):
            value = value.to_arrow_table()
        if hasattr(value, "to_pylist"):
            value = value.to_pylist()
        return as_records(value, contract_type)

    def row_count(self, value: Any) -> int | None:
        if hasattr(value, "num_rows"):
            return int(value.num_rows)
        return None


def _arrow_logical(dtype: Any) -> str:
    name = str(dtype).lower()
    if "int" in name:
        return "integer"
    if "float" in name or "double" in name or "decimal" in name:
        return "number"
    if "bool" in name:
        return "boolean"
    if "timestamp" in name or "date" in name:
        return "timestamp"
    return "string"
