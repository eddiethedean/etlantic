# Quality rules

Medallantic layer rules lower to ETLantic's portable `etlantic.quality/1`
representation. Validation is part of each relevant step rather than a final
pipeline-only check.

## Declare rules

```python
from medallantic import MedallionBuilder

builder = (
    MedallionBuilder(
        "orders",
        min_bronze_rate=90.0,
        min_silver_rate=97.0,
        min_gold_rate=99.0,
    )
    .bronze(
        "raw_orders",
        asset="bronze_orders",
        rules={
            "order_id": ["not_null"],
            "amount": ["min:0"],
        },
    )
)
```

Invalid shorthand fails during lowering with `MDL110`. A rule is not considered
enforced merely because it parsed successfully: the selected runtime/compiler
must advertise the required quality capability.

## Accept-rate policy

Layer thresholds are Medallantic policy. Evaluate a normalized report with:

```python
from medallantic import enforce_accept_rates

checked = enforce_accept_rates(
    report,
    policy_metadata=lowered.validation_policy.metadata,
)
```

An unmet threshold produces structured `MDL120` evidence and a failed outcome.
Do not calculate a second, application-specific success status from raw counts.

## Fail-closed behavior

- malformed rules fail before execution
- missing compiler/runtime capabilities fail planning
- unsupported engine-native rules are not silently translated
- quality evidence contains counts and diagnostics, not rejected source rows
- production execution still requires plugin authorization

Polars, Pandas, and local portable paths support the shipped rule kernel.
Consult the [compatibility guide](COMPATIBILITY.md) before relying on SQL,
PySpark, or engine-native extensions.
