# API — Quality

> **Status: Available in ETLantic 0.38.0 (provisional).** Generated from
> `etlantic.quality`. Hub: [Python API Reference](API_REFERENCE.md).
>
> Wire id: `etlantic.quality/1`. ContractModel remains the semantic authority
> for field and constraint meaning. This namespace owns the portable quality
> expression envelope used for planning and capability negotiation.

!!! warning "Provisional"
    `etlantic.quality` may change with migration notes in a future minor. Prefer
    documented helpers below; pin core to `==0.38.0` in pilots.

## Behavioral contracts

| API | Returns | Important failures / side effects |
|---|---|---|
| `rule_not_null` / `rule_range` / … | `QualityRule` builders | Authoring only; no I/O |
| `QualityRuleset` / `QualityExpression` | Envelope models | Serialize with `quality_to_dict` (`etlantic.quality/1`) |
| `make_quality_gate` | Gate metadata for planning | Attaches under `QUALITY_METADATA_KEY` |
| `analyze_quality` | `QualityAnalysis` | Capability / mapping analysis; does not execute engines |
| `map_rule_to_contract` | `ContractConstraintMapping` | Raises `UnmappedQualityRuleError` when no mapping exists |
| `evaluate_rule` / `split_by_quality` | Evaluation helpers | Engine-specific; SQL/PySpark remain fail-closed for portable quality in 0.32 |
| `quality_from_dict` / `upgrade_quality_dict` | Codec + upgrade | Unsupported schema raises `UnsupportedQualitySchemaError` |

```python
import etlantic as etl

rule = etl.quality.rule_not_null("customer_id")
expr = etl.quality.QualityExpression(rules=[rule])
payload = etl.quality.quality_to_dict(expr)
```

Medallantic `rules=` lower onto this vocabulary — see
[Medallantic quality](../09_MEDALLANTIC/QUALITY.md).

## Generated reference

::: etlantic.quality
    options:
      show_source: false
      members_order: source
      filters:
        - "!^_"
