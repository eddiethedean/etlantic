"""SQL / Spark / Delta / write-policy compatibility mappings."""

from __future__ import annotations

from typing import Any

from etlantic.capabilities import PluginCapabilities
from etlantic.diagnostics import Diagnostic, Severity
from etlantic.reliability import WriteMode
from etlantic.runtime.request import RetryPolicy

# SparkForge write vocabulary → ETLantic WriteMode
_WRITE_MODE_MAP: dict[str, WriteMode] = {
    "append": WriteMode.APPEND,
    "overwrite": WriteMode.OVERWRITE,
    "overwrite_partitions": WriteMode.OVERWRITE,
    "merge": WriteMode.MERGE,
    "upsert": WriteMode.UPSERT,
    "no_write": WriteMode.NO_WRITE,
    "skip": WriteMode.NO_WRITE,
    "none": WriteMode.NO_WRITE,
    "": WriteMode.OVERWRITE,
}

# Delta operations require spark_delta (and related) capabilities.
_DELTA_CAPABILITY: dict[str, str] = {
    "merge": "spark_delta",
    "optimize": "spark_delta",
    "vacuum": "spark_delta",
    "history": "spark_delta",
    "time_travel": "spark_delta",
}


def write_mode_from_sparkforge(raw: str | None) -> WriteMode:
    """Map a SparkForge write-mode string to ETLantic WriteMode."""
    key = (raw or "overwrite").strip().lower()
    if key not in _WRITE_MODE_MAP:
        raise ValueError(f"Unsupported SparkForge write mode: {raw!r}")
    return _WRITE_MODE_MAP[key]


def write_mode_metadata(raw: str | None) -> dict[str, Any]:
    """Extra write-mode metadata preserved when modes collapse (e.g. partitions)."""
    key = (raw or "overwrite").strip().lower()
    meta: dict[str, Any] = {}
    if key == "overwrite_partitions":
        meta["partition_overwrite"] = True
        meta["sparkforge_write_mode"] = key
    elif key:
        meta["sparkforge_write_mode"] = key
    return meta


def retry_policy_from_sparkforge(raw: dict[str, Any] | None) -> RetryPolicy:
    """Normalize SparkForge retry config into ETLantic ``RetryPolicy``."""
    data = dict(raw or {})
    retry_on_raw = data.get("retry_on") or data.get("retry_on_exceptions") or ()
    if isinstance(retry_on_raw, str):
        retry_on: tuple[str, ...] = (retry_on_raw,)
    else:
        retry_on = tuple(str(x) for x in retry_on_raw)
    backoff = data.get("backoff_seconds")
    if backoff is None:
        backoff = data.get("retry_delay_seconds")
    if backoff is None:
        backoff = data.get("delay")
    raw_attempts = data.get("max_attempts")
    if raw_attempts is None:
        raw_attempts = data.get("retries")
    max_attempts = int(1 if raw_attempts is None else raw_attempts)
    if max_attempts < 1:
        max_attempts = 1
    return RetryPolicy(
        max_attempts=max_attempts,
        backoff_seconds=float(0.0 if backoff is None else backoff),
        retry_on=retry_on,
    )


def assert_delta_capabilities(
    operations: list[str],
    *,
    capabilities: PluginCapabilities | None = None,
    strict: bool = True,
) -> list[Diagnostic]:
    """Fail closed when declared Delta ops are unsupported by capabilities.

    When ``capabilities`` is None and ``strict`` is True (default), emit errors
    so callers must supply a plugin that supports ``spark_delta`` before
    execution. When ``strict`` is False (plan-only), emit warnings instead.
    """
    diagnostics: list[Diagnostic] = []
    missing_caps_severity = Severity.ERROR if strict else Severity.WARNING
    for op in operations:
        key = op.strip().lower()
        required = _DELTA_CAPABILITY.get(key)
        if required is None:
            diagnostics.append(
                Diagnostic(
                    code="PMSF321",
                    severity=Severity.ERROR,
                    message=f"Unknown Delta operation {op!r}.",
                    path=("delta_operations", op),
                    phase="sparkforge_adapter",
                )
            )
            continue
        if capabilities is None:
            diagnostics.append(
                Diagnostic(
                    code="PMSF322",
                    severity=missing_caps_severity,
                    message=(
                        f"Delta operation {op!r} requires capability {required!r}; "
                        "no Spark plugin capabilities were supplied"
                        + (" (fail closed)." if strict else " (plan-only warning).")
                    ),
                    path=("delta_operations", op),
                    phase="sparkforge_adapter",
                )
            )
            continue
        if not capabilities.supports(required):
            diagnostics.append(
                Diagnostic(
                    code="PMSF323",
                    severity=missing_caps_severity,
                    message=(
                        f"Delta operation {op!r} requires capability {required!r} "
                        "which the selected Spark plugin does not declare"
                        + (" (fail closed)." if strict else " (plan-only warning).")
                    ),
                    path=("delta_operations", op),
                    phase="sparkforge_adapter",
                )
            )
    return diagnostics


COMPATIBILITY_MATRIX: dict[str, dict[str, str]] = {
    "write": {k: v.value for k, v in _WRITE_MODE_MAP.items() if k},
    "delta": dict(_DELTA_CAPABILITY),
    "engines": {
        "spark": "Profile.spark_engine=pyspark",
        "pyspark": "Profile.spark_engine=pyspark",
        "sql": "Profile.sql_engine=sql",
        "delta": "Profile.spark_engine=pyspark + spark_delta capability",
    },
    "notes": {
        "overwrite_partitions": (
            "Maps to WriteMode.OVERWRITE with metadata.partition_overwrite=true"
        ),
    },
}
