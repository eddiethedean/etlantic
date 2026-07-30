# Development

This section defines how ETLantic is designed, tested, contributed to, and
released.

## Contributor essentials

- [Contributing](CONTRIBUTING.md)
- [Coding Standards](CODING_STANDARDS.md)
- [Testing](TESTING.md)
- [Documentation](DOCUMENTATION.md)
- [Release Process](RELEASE_PROCESS.md)
- [Support policy](SUPPORT.md)
- [Governance](GOVERNANCE.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [API stability and deprecation](DEPRECATION_POLICY.md)
- [Dependency Strategy](DEPENDENCY_STRATEGY.md)
- [Planning Hub](PLAN_INDEX.md)
- [Roadmap summary](ROADMAP_SUMMARY.md)
- [Full roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md)

## Current migrations and exit gates

- [Migration 0.33 → 0.34](MIGRATION_0_33_TO_0_34.md)
- [Exit gate 0.34](EXIT_GATE_0_34.md) (Done — operations / evidence / M6)
- [Migration 0.34 → 0.35](MIGRATION_0_34_TO_0_35.md)
- [Exit gate 0.35](EXIT_GATE_0_35.md) (Done — migration completion / joint freeze / M7)
- [Migration 0.32 → 0.33](MIGRATION_0_32_TO_0_33.md)
- [Exit gate 0.33](EXIT_GATE_0_33.md) (Done — SQLAlchemy / relational differential / M5)
- [Migration 0.31 → 0.32](MIGRATION_0_31_TO_0_32.md)
- [Exit gate 0.32](EXIT_GATE_0_32.md) (Done — PySpark / Delta differential / M4)
- [Migration 0.30 → 0.31](MIGRATION_0_30_TO_0_31.md)
- [Exit gate 0.31](EXIT_GATE_0_31.md) (Done — execution / materialization / M3)
- [Migration 0.29 → 0.30](MIGRATION_0_29_TO_0_30.md)
- [Exit gate 0.30](EXIT_GATE_0_30.md) (Done — portable quality / M2)
- [Migration 0.28 → 0.29](MIGRATION_0_28_TO_0_29.md)
- [Exit gate 0.29](EXIT_GATE_0_29.md) (Done)
- [Migration 0.27 → 0.28](MIGRATION_0_27_TO_0_28.md)
- [Exit gate 0.28](EXIT_GATE_0_28.md) (Done)
- [Migration 0.26 → 0.27](MIGRATION_0_26_TO_0_27.md)
- [Exit gate 0.27](EXIT_GATE_0_27.md)
- [0.38 stable-foundation removal candidates](REMOVAL_CANDIDATES_0_38.md)
- [Migration 0.24 → 0.25](MIGRATION_0_24_TO_0_25.md)
- [Exit gate 0.25](EXIT_GATE_0_25.md)
- [Migration 0.23 → 0.24](MIGRATION_0_23_TO_0_24.md)
- [Exit gate 0.24](EXIT_GATE_0_24.md)
- [Upgrade hub (cumulative)](../01_GETTING_STARTED/UPGRADE.md)

## Documentation audits

- [Documentation audit 0.34](DOCUMENTATION_AUDIT_0_34.md) (current)
- [Documentation audit 0.33](DOCUMENTATION_AUDIT_0_33.md)
- [Documentation audit 0.32](DOCUMENTATION_AUDIT_0_32.md)
- [Maintained 0.25 Documentation Audit](DOCUMENTATION_AUDIT_0_25.md)
- [Maintained 0.24 Documentation Audit](DOCUMENTATION_AUDIT_0_24.md)
- [Maintained 0.23 Documentation Audit](DOCUMENTATION_AUDIT_0_23.md)
- [Maintained 0.21 Documentation Audit](DOCUMENTATION_AUDIT_0_21.md)
- [Maintained 0.20 Documentation Audit](DOCUMENTATION_AUDIT_0_20.md)
- [Maintained 0.18 Documentation Audit](DOCUMENTATION_AUDIT_0_18.md)
- [Historical 0.17 Documentation Audit](DOCUMENTATION_AUDIT_0_17.md)

Historical migrations, exit gates, ADRs, and future stubs:
[Archive index](ARCHIVE_INDEX.md).

## Migration archive

Historical migrations, design studies, and maintainer plans are indexed in
[Archive index](ARCHIVE_INDEX.md) (not product docs).

## Decisions

- [Design Decisions](DESIGN_DECISIONS.md)
- [Architecture Decisions](ARCHITECTURE_DECISIONS.md)
- [Benchmarks](BENCHMARKS.md)
- [Performance guidance](PERFORMANCE.md)
- [Performance baselines](PERFORMANCE_RESULTS.md)

## Plans and implementation records

Start with the [Planning Hub](PLAN_INDEX.md). It distinguishes planned
programs, partially shipped work, shipped implementation records, and
historical review baselines, then routes to the authoritative current
documentation.

Use the
[main roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md)
for release order, [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md) for
current availability, and [architecture decisions](ARCHITECTURE_DECISIONS.md)
for locked boundaries. Historical material remains available through the
[archive index](ARCHIVE_INDEX.md).

The [Documentation Status](../02_FOUNDATIONS/DOCUMENTATION_STATUS.md) chapter
defines how design examples, proposals, and normative requirements should be
interpreted during implementation.
