# Versioning

Versioning allows data contracts to evolve without breaking the pipelines that depend on them.

ETLantic delegates the definition of contract compatibility to **ContractModel** while coordinating version validation across transformations and pipelines.

## Goals

A versioning strategy should:

- Allow contracts to evolve safely.
- Detect breaking changes before execution.
- Support multiple published versions.
- Enable gradual migrations.
- Produce deterministic contract artifacts.
- Keep version semantics independent of execution engines.

## Responsibility Boundaries

| Component | Responsibility |
|-----------|----------------|
| Pydantic | Model structure |
| ContractModel | Contract identity, version metadata, compatibility analysis |
| [ODCS](ODCS.md) | Portable version representation |
| ETLantic | Pipeline-wide version validation and planning |
| Plugins | Runtime execution only |

## Contract Identity

Every published data contract should expose a stable identity:

- Contract identifier
- Version
- ODCS version
- Owner
- Metadata

Identity should remain stable across compatible revisions.

## Semantic Versioning

ETLantic recommends Semantic Versioning:

- **MAJOR** – Breaking schema or semantic changes
- **MINOR** – Backward-compatible additions
- **PATCH** – Documentation, metadata, or compatible corrections

Example:

```python
contract_config = ContractConfig(
    name="customer",
    version="2.1.0",
)
```

## Compatible Changes

Examples of compatible changes include:

- Adding optional fields
- Clarifying descriptions
- Adding documentation
- Adding compatible metadata
- Fixing non-semantic errors

Compatibility decisions ultimately belong to ContractModel.

## Breaking Changes

Examples of breaking changes include:

- Removing required fields
- Renaming published fields
- Changing field meaning
- Narrowing allowed values
- Changing required types
- Tightening constraints that invalidate previously valid data

Breaking changes should require a new major version.

## Pipeline Validation

When validating a pipeline, ETLantic asks ContractModel whether connected contracts are compatible.

Conceptually:

```python
compatible = compare_contracts(
    producer_contract,
    consumer_contract,
)
```

ETLantic should rely on the public ContractModel compatibility API rather than implementing its own rules.

## Multiple Versions

Different pipelines may intentionally reference different versions of the same logical contract.

```text
Customer v1
      │
Pipeline A

Customer v2
      │
Pipeline B
```

ETLantic should allow this while detecting accidental incompatibilities.

## Migrations

Contract migrations should occur through explicit transformations.

```text
Customer v1
      │
      ▼
UpgradeCustomerV1ToV2
      │
      ▼
Customer v2
```

This keeps version transitions visible and testable.

## Generated Artifacts

Generated ODCS artifacts should include version information and be deterministic so they can be reviewed in version control.

Example:

```text
contracts/
└── data/
    ├── customer-1.0.0.odcs.yaml
    └── customer-2.0.0.odcs.yaml
```

## Deprecation

Contracts may be marked as deprecated before removal.

Recommended metadata:

- Deprecation date
- Replacement contract
- Planned removal version
- Migration guidance

ETLantic should surface deprecation warnings during planning.

## Compatibility Reports

Compatibility reports should explain *why* two versions are or are not compatible.

Typical diagnostics include:

- Missing required field
- Changed field type
- Tightened constraint
- Removed alias
- Version mismatch

Structured reports make migrations easier than simple pass/fail results.

## Best Practices

- Give every published contract an explicit version.
- Treat contract versions as part of the public interface.
- Use transformations for schema evolution.
- Keep generated contracts under version control.
- Run compatibility checks in CI.
- Avoid changing published contracts in place.

## Anti-Patterns

Avoid:

- Overwriting published contracts without a version change.
- Inferring compatibility from Python class names alone.
- Duplicating compatibility logic outside ContractModel.
- Skipping compatibility checks during pipeline validation.

## Key Principle

> ContractModel decides whether two data contract versions are compatible. ETLantic uses that decision to ensure pipelines remain safe as contracts evolve.

## Next Step

Continue with **GENERATION.md** to learn how ETLantic and ContractModel generate deterministic contract artifacts from Python models.
