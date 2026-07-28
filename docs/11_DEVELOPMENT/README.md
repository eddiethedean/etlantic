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
- [Roadmap summary](ROADMAP_SUMMARY.md)
- [Full roadmap](https://github.com/eddiethedean/etlantic/blob/main/ROADMAP.md)

## Current migrations and exit gates

- [Migration 0.29 → 0.30](MIGRATION_0_29_TO_0_30.md)
- [Exit gate 0.30](EXIT_GATE_0_30.md) (Done — portable quality / M2)
- [Migration 0.28 → 0.29](MIGRATION_0_28_TO_0_29.md)
- [Exit gate 0.29](EXIT_GATE_0_29.md) (Done)
- [Migration 0.27 → 0.28](MIGRATION_0_27_TO_0_28.md)
- [Exit gate 0.28](EXIT_GATE_0_28.md) (Done)
- [Migration 0.26 → 0.27](MIGRATION_0_26_TO_0_27.md)
- [Exit gate 0.27](EXIT_GATE_0_27.md)
- [1.0 removal candidates](REMOVAL_CANDIDATES_1_0.md)
- [Migration 0.24 → 0.25](MIGRATION_0_24_TO_0_25.md)
- [Exit gate 0.25](EXIT_GATE_0_25.md)
- [Migration 0.23 → 0.24](MIGRATION_0_23_TO_0_24.md)
- [Exit gate 0.24](EXIT_GATE_0_24.md)
- [Upgrade hub (cumulative)](../01_GETTING_STARTED/UPGRADE.md)

## Documentation audits

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

## Maintainer plans and records (internal)

These pages sequence future work. They are not product user guides:

- [0.18 Gate A — Versioned Tabular Interchange (shipped record)](INTEROPERABILITY_FOUNDATION_PLAN.md)
- [FastAPI Integration Plan](FASTAPI_INTEGRATION_PLAN.md)
- [Programmatic Authoring and Lossless JSON (0.24)](PROGRAMMATIC_AUTHORING_0_24.md)
- [Schema Drift and Evolution Plan](SCHEMA_DRIFT_PLAN.md)
- [ETL Reliability and Recovery Plan](ETL_RELIABILITY_PLAN.md)
- [TransformationModel Incubation Plan](TRANSFORMATIONMODEL_PLAN.md)
- [SQLModel Integration Plan](SQLMODEL_INTEGRATION_PLAN.md)
- [SparkForge Feature Adoption](SPARKFORGE_ADOPTION.md)
- [Portable Transformation Implementation Plan](PORTABLE_TRANSFORM_PLAN.md)
- [Local Scheduler and Prefect Integration Plan](SCHEDULER_AND_PREFECT_PLAN.md)
- [DTCS and Portable Transformation Evolution](DTCS_PORTABLE_EVOLUTION.md)
- [DTCS 2.0 Portable Relational Publication Record](DTCS_PORTABLE_SPEC_PROPOSAL.md)
- [DTCS 3.0 Rich Portable Analytics Publication Record](DTCS_3_0_SPEC_PROPOSAL.md)

Start with the roadmap for sequencing and the decision records for architectural
boundaries.

The [Documentation Status](../02_FOUNDATIONS/DOCUMENTATION_STATUS.md) chapter
defines how design examples, proposals, and normative requirements should be
interpreted during implementation.
