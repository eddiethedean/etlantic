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

- [Migration 0.41 → 0.42](MIGRATION_0_41_TO_0_42.md) (Gate-ready — CP4)
- [Exit gate 0.42](EXIT_GATE_0_42.md) (Gate-ready — CP4)
- [Findings ledger 0.42](FINDINGS_0_42.md)
- [0.42 implementation plan](IMPLEMENTATION_PLAN_0_42.md)
- [ADR-019: Policy, quotas, and audit](adr/ADR-019-POLICY-QUOTAS-AND-AUDIT.md)
- [What's new in 0.42](../01_GETTING_STARTED/WHATS_NEW_0_42.md) (Gate-ready)
- [CP4 operator runbook](CP4_OPERATOR_RUNBOOK.md)
- [CP4 outage matrix](cp4_outage_matrix_0_42.json)
- [Migration 0.40 → 0.41](MIGRATION_0_40_TO_0_41.md) (Gate-ready — CP3)
- [Exit gate 0.41](EXIT_GATE_0_41.md) (Gate-ready — CP3)
- [Findings ledger 0.41](FINDINGS_0_41.md)
- [0.41 implementation plan](IMPLEMENTATION_PLAN_0_41.md)
- [ADR-018: Durable submission and state](adr/ADR-018-DURABLE-SUBMISSION-AND-STATE.md)
- [What's new in 0.42](../01_GETTING_STARTED/WHATS_NEW_0_42.md) (Gate-ready)
- [Durable chaos matrix (fake evidence)](durable_chaos_matrix_0_41.json)
- [Migration 0.39 → 0.40](MIGRATION_0_39_TO_0_40.md) (Done — CP2)
- [Exit gate 0.40](EXIT_GATE_0_40.md) (Done — CP2)
- [Findings ledger 0.40](FINDINGS_0_40.md)
- [0.40 implementation plan](IMPLEMENTATION_PLAN_0_40.md)
- [ADR-017: Registry and isolation](adr/ADR-017-REGISTRY-AND-ISOLATION.md)
- [What's new in 0.40](../01_GETTING_STARTED/WHATS_NEW_0_40.md) (Done)
- [Isolation profile matrix (fake evidence)](isolation_profile_matrix_0_40.json)
- [Migration 0.38 → 0.39](MIGRATION_0_38_TO_0_39.md) (Done — CP1)
- [Exit gate 0.39](EXIT_GATE_0_39.md) (Done — CP1)
- [Findings ledger 0.39](FINDINGS_0_39.md)
- [0.39 implementation plan](IMPLEMENTATION_PLAN_0_39.md)
- [ADR-016: Control-plane identity](adr/ADR-016-CONTROL-PLANE-IDENTITY.md)
- [What's new in 0.39](../01_GETTING_STARTED/WHATS_NEW_0_39.md) (Done)
- [Migration 0.37 → 0.38](MIGRATION_0_37_TO_0_38.md) (Done)
- [Exit gate 0.38](EXIT_GATE_0_38.md) (Done — connectivity)
- [Findings ledger 0.38](FINDINGS_0_38.md)
- [0.38 implementation plan](IMPLEMENTATION_PLAN_0_38.md)
- [Forward implementation plans](FORWARD_IMPLEMENTATION_PLANS.md) (0.39–0.52 delivery contract)
- [ADR-015: Connector protocols](adr/ADR-015-CONNECTOR-PROTOCOLS.md)
- [Migration 0.36 → 0.37](MIGRATION_0_36_TO_0_37.md)
- [Exit gate 0.37](EXIT_GATE_0_37.md) (Gate-ready — stable foundation)
- [Findings ledger 0.37](FINDINGS_0_37.md)
- [0.37 implementation plan](IMPLEMENTATION_PLAN_0_37.md)
- [Migration 0.35 → 0.36](MIGRATION_0_35_TO_0_36.md)
- [Exit gate 0.36](EXIT_GATE_0_36.md) (Done — joint compatibility burn-in)
- [Findings ledger 0.36](FINDINGS_0_36.md)
- [Migration 0.34 → 0.35](MIGRATION_0_34_TO_0_35.md)
- [Exit gate 0.35](EXIT_GATE_0_35.md) (Done — migration completion / joint freeze / M7)
- [Migration 0.33 → 0.34](MIGRATION_0_33_TO_0_34.md)
- [Exit gate 0.34](EXIT_GATE_0_34.md) (Done — operations / evidence / M6)
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
- [0.37 stable-foundation removal candidates](REMOVAL_CANDIDATES_0_37.md)
- [Migration 0.24 → 0.25](MIGRATION_0_24_TO_0_25.md)
- [Exit gate 0.25](EXIT_GATE_0_25.md)
- [Migration 0.23 → 0.24](MIGRATION_0_23_TO_0_24.md)
- [Exit gate 0.24](EXIT_GATE_0_24.md)
- [Upgrade hub (cumulative)](../01_GETTING_STARTED/UPGRADE.md)

## Documentation audits

- [Documentation audit 0.35](DOCUMENTATION_AUDIT_0_35.md) (latest completed)
- [Documentation ownership map](DOCUMENTATION_OWNERSHIP.md)
- [Documentation audit 0.34](DOCUMENTATION_AUDIT_0_34.md)
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
for locked boundaries. Post-foundation connectivity includes the
[Landing-zone file connector plan](LANDING_ZONE_CONNECTOR_PLAN.md) (batch and
incremental in 0.38; continuous triggers in 0.39+),
[ADR-015](adr/ADR-015-CONNECTOR-PROTOCOLS.md), and the
[0.38 exit gate](EXIT_GATE_0_38.md). Historical material remains
available through the [archive index](ARCHIVE_INDEX.md).

Assigned post-control-plane reliability work includes portable delivery
objectives and governed erasure in
[0.42](IMPLEMENTATION_PLAN_0_42.md), followed by bounded dynamic control flow,
streaming dead-letter policy, and schema-registry interoperability in
[0.46](IMPLEMENTATION_PLAN_0_46.md). These are planned capabilities, not claims
about the shipped 0.38 package.

The [Documentation Status](../02_FOUNDATIONS/DOCUMENTATION_STATUS.md) chapter
defines how design examples, proposals, and normative requirements should be
interpreted during implementation.

- [EXIT_GATE_0_41.md](EXIT_GATE_0_41.md)
