# Findings Ledger 0.38 — Data Connectivity and Connector SDK

> **Status: Gate-ready for tag/publish rehearsal toward ETLantic 0.38.0** after
> post-exit honesty pass (fake connectors, manifests/CI, plan caps, pin docs).
> Ledger for the 0.38 connectivity program. Close a finding only when its
> regression test and durable evidence land. **P0 must be 0 before tag.**
> Package version is **0.38.0**. Soft-continue: `038-X-01`.

## Severity policy

From [IMPLEMENTATION_PLAN_0_38](IMPLEMENTATION_PLAN_0_38.md):

| Severity | Meaning | Release treatment |
|---|---|---|
| **P0** | Secret/trust failure, silent semantic fallback, partial publication exposed, unsafe cursor advance, unusable artifact | Must close before 0.38 |
| **P1** | Material compatibility, correctness, cleanup, adoption, cost, or support risk | Close or defer with owner, mitigation, target phase, and non-blocking rationale |
| **P2** | Localized usability, performance, or maintainability defect | May defer with owner and target |
| **P3** | Cosmetic or opportunistic improvement | Backlog |

Changing severity without written rationale does not close a finding.

## Locked dispositions

Recorded in
[ADR-015: Connector Protocols](adr/ADR-015-CONNECTOR-PROTOCOLS.md). Do not
reopen without a written finding and migration plan.

| Decision | Outcome | Notes |
|---|---|---|
| Protocol families | `etlantic.source/1`, `etlantic.sink/1`, `etlantic.storage/1` | Entry points `etlantic.source_connectors`, `etlantic.sink_connectors`, `etlantic.storage_connectors` |
| Public package | `etlantic.connectors` | Runtime-checkable, async-first |
| Capability spellings | Frozen vocabulary in ADR-015 | Landing tokens + write/publication/transactions/reconciliation |
| Plan vs runtime evidence | Static plan records identity **scheme** only | Concrete files in `LandingReadManifest` / run report |
| Checkpoint schema | `etlantic.landing_checkpoint/1` | No rows, credentials, or absolute paths |
| Reference set | local-files built-in; `etlantic-s3`, `etlantic-iceberg`, `etlantic-snowflake`; PostgreSQL via `etlantic-sql` | Vendor SDKs stay out of core |
| StorageBinding | Compatibility adapter only | No silent connector capability claims |
| Continuous watch | Out of core | Compose in 0.39+ against same bindings |

## Maturity classifiers (038-M)

| Provider | Maturity | Classifier | Notes |
|---|---|---|---|
| `local-files` | Preview | Beta (core) | Snapshot + incremental; rename_done preserves nested paths |
| `s3` | Experimental | Alpha (`etlantic-s3`) | JSON payloads; overwrite replaces pointer; fake multipart |
| `iceberg` | Experimental | Alpha (`etlantic-iceberg`) | Fake catalog; no `write.partition_replace` claim |
| `snowflake` | Experimental | Alpha (`etlantic-snowflake`) | Fake autocommit=False + query_id |
| `postgresql` | Experimental | Beta package / Experimental connector path | Via `etlantic-sql` |

Matrix artifact:
[CONNECTOR_CAPABILITY_MATRIX_0_38.json](CONNECTOR_CAPABILITY_MATRIX_0_38.json).

## Wave 7 burn-in results

| ID | Result | Evidence |
|---|---|---|
| `038-A01` | Pass | Same logical pipeline under local-files / s3 / snowflake profiles — topology stable; resolutions differ (`tests/connectors/test_cross_provider_0_38.py`) |
| `038-A17` | Pass | Snapshot ↔ incremental mode switch without Extract rewrite |
| `038-A19` | Pass | Matrix caps match connector `info()` for local, s3, iceberg, snowflake, postgresql |
| `038-A20` / `038-X-01` | Soft-continue | In-repo third-party EP stub + public-import check; echo plugin PyPI proof deferred |
| Fake conformance | Pass | `scripts/check_connector_conformance.py --fake` (exit 1 on failed cases) |

## Open findings

Open **P0 count is 0**.

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| `038-X-01` | P1 | Ecosystem maintainers + echo plugin maintainer | Soft-continue (disposed for exit) | Independent third-party connector on distinct repo/CI not yet on PyPI | **Selection:** extend [`etlantic-plugin-echo`](https://github.com/eddiethedean/etlantic-plugin-echo) with `etlantic.source_connectors`. **Mitigation:** in-repo `tests/connectors/third_party_echo.py` loads via EP monkeypatch, public imports only, info conformance green; first-party `--fake` covers protocol proof. **Does not block** 0.38 tag. Target: echo repo EP before first Supported cloud promotion / 0.39. Non-blocking rationale: exit scorecard independent-connector cell satisfied by in-repo governance-separated stub + soft-continue disposition. |

## Closed in 0.38

Post-exit audit reopened P0/P1 honesty gaps; all listed rows closed with regressions.

| ID | Severity | Summary | Evidence |
|---|---|---|---|
| `038-P0-01` | P0 | Multi-sink publication barrier unused; ledger advanced per sink | `PublicationBarrier` wired in orchestrator; `tests/connectors/test_publication_barrier_0_38.py` |
| `038-P0-02` | P0 | Connector EPs omitted from coordinator / runtime registries | Connector groups in `PluginDiscoveryCoordinator`; runtime population in `lifecycle/runtime.py` |
| `038-P0-03` | P0 | `discover_connectors_for_profile` TypeError (`instantiate=True`) | Fixed discovery helper; `tests/connectors/test_discovery_0_38.py` |
| `038-P0-04` | P0 | Cloud packages missing plugin manifests → undiscoverable | `etlantic-plugin-manifest.json` + hatch force-include for s3/iceberg/snowflake; `scripts/check_plugin_manifests.py` |
| `038-P0-05` | P0 | Secret-like keys accepted into assets/plans | `reject_secret_like_keys` at asset parse; `tests/connectors/test_asset_secrets_0_38.py` |
| `038-P0-06` | P0 | `StorageBindingAdapter` leaked context secrets + over-claimed `rolled_back` | Redacted metadata; ambiguous → `unknown`; `tests/connectors/test_adapter_redaction_0_38.py` |
| `038-P0-07` | P0 | Absolute landing roots in plan snapshots / listing intent | `SafeIoPlanPolicy` + plan-safe stripping; `tests/profile/test_safe_io_plan_policy_0_38.py` |
| `038-P0-08` | P0 | Postgres fake reconcile-after-rollback false `committed` | Pending vs committed query ids; `tests/sql/test_postgresql_connectors.py` |
| `038-P0-09` | P0 | `unknown` publication discarded proposal / released lease | Hold + reconcile path in orchestrator (`038-R04`) |
| `038-H10` | P1 | S3 commit always `if_none_match=True` blocked overwrite | Mode-gated pointer replace; `tests/s3/test_fake_s3.py::test_second_overwrite_publish_succeeds` |
| `038-H11` | P1 | S3 advertised parquet / multipart JSON concat | `format=json`; single serialize at prepare; multi-batch test |
| `038-H12` | P1 | Iceberg advertised `write.partition_replace` without semantics | Capability dropped; matrix + README; mode rejected |
| `038-H13` | P1 | Iceberg abort after commit rolled back published snapshot | Staged id cleared on commit; abort-after-commit test |
| `038-H15` | P1 | `rename_done` flattened nested paths (basename collisions) | Preserve relative path under `.done/`; snapshot nested test |
| `038-H16` | P1 | Conformance script ignored failed cases; tautological assert | Exit 1 on `ok=false`; removed `or True`; optional fake sinks |
| `038-H17` | P1 | CI package job omitted s3/iceberg/snowflake wheels | `checks.yml` build + import smoke |
| `038-H18` | P1 | Adopter pin/doc bugs (0.37 expect / bad rollback / RTD slug) | QUICKSTART, TROUBLESHOOTING, MIGRATION, DOCUMENTATION_VERSIONING |
| `038-H19` | P1 | Plan-time connector capability negotiation missing | `connectors/negotiate.py` + planner hook; `PMCONN850`; plan caps tests |
| `038-H20` | P1 | `commit_ledger` / TOCTOU residual | Optional `CommitReceipt` + `may_advance_cursor`; O_NOFOLLOW same-fd read |

## Closure rules

1. Every P0 requires a regression test and linked durable evidence before
   severity can move or the finding can close.
2. Deferred P1 rows must name owner, target phase (usually 0.39+), mitigation,
   and why they do not block the 0.38 exit.
3. Do not reopen a locked disposition without an explicit finding ID and
   migration note.

## See also

- [Exit gate 0.38](EXIT_GATE_0_38.md)
- [Implementation plan 0.38](IMPLEMENTATION_PLAN_0_38.md)
- [Migration 0.37 → 0.38](MIGRATION_0_37_TO_0_38.md)
- [What's New in 0.38](../01_GETTING_STARTED/WHATS_NEW_0_38.md)
- [Findings ledger 0.37](FINDINGS_0_37.md)
