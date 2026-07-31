# Exit Gate 0.38 — Data Connectivity and Connector SDK

> **Status: Gate-ready for tag/publish rehearsal toward ETLantic 0.38.0.**
> Connector protocols, local landing-zone reference, CDK/conformance, and
> experimental cloud packages are in-tree. Close only against exact candidate
> wheels when publishing. **P0 = 0.** Soft-continue: `038-X-01` (independent
> echo plugin connector on PyPI) mitigated by in-repo third-party EP proof.

| Deliverable | Status |
|---|---|
| Planning: ADR-015 / this exit gate / findings / What's New / migration | Met |
| Public source/sink/storage protocols + `etlantic.connectors` | Met |
| Structured bindings, manifests, trust, planning | Met |
| Runtime publication barrier + cursor correctness | Met |
| Local landing-zone snapshot + incremental | Met |
| Connector CDK + public conformance suites | Met |
| Reference providers (S3, Iceberg, Snowflake, PostgreSQL) | Met (fake/CI; Experimental) |
| Maturity / compatibility records + third-party proof | Met with soft-continue `038-X-01` |
| Release rehearsal (wheels, digests, immutable docs) | Gate-ready (in-repo); publish residual |

## Quantified exit scorecard

From [IMPLEMENTATION_PLAN_0_38](IMPLEMENTATION_PLAN_0_38.md):

| Measure | Required | Current |
|---|---:|---|
| Public versioned connector protocol families | 3 | **Met** (source/sink/storage `/1`) |
| Required reference paths passing | 5 / 5 | **Met** (local, s3, iceberg, snowflake, postgresql fake) |
| Advertised capability-to-conformance coverage | 100% | **Met** (matrix + `--fake` conformance) |
| Same-pipeline portability profiles passing | 3 / 3 | **Met** (`038-A01` local/s3/snowflake) |
| Landing snapshot acceptance scenarios passing | 100% | **Met** |
| Landing incremental acceptance scenarios passing | 100% | **Met** |
| Concrete live files listed during ordinary static planning | 0 | **Met** |
| Resolved secrets in retained artifacts | 0 | **Met** (carry-forward + connector suites) |
| Arbitrary source rows in plans/reports/checkpoints/history | 0 | **Met** |
| Physical landing-root paths in new plans/reports | 0 | **Met** |
| Failed/unresolved publications advancing state | 0 | **Met** |
| Partial object publications visible as committed | 0 | **Met** (S3 fake conditional pointer) |
| Concurrent local runs selecting the same landing files | 0 | **Met** (lease tests) |
| Unsupported modes silently falling back | 0 | **Met** |
| Core long-lived directory-watch loops | 0 | **Met** (spec + code) |
| Production connector imports bypassing allowlist | 0 | **Met** |
| Supported compatibility matrix cells passing | 100% | **Met** for declared fake cells |
| Cleanup leaks during declared burn-in | 0 | **Met** (fake burn-in) |
| Independent connectors using private imports | 0 | **Met** (in-repo EP stub) |
| Unresolved P0 findings | 0 | **Met** |
| Remaining P1s without full disposition | 0 | **Met** (`038-X-01` disposed soft-continue) |
| Candidate wheels missing manifest/conformance evidence | 0 | Gate-ready (rehearsal residual at publish) |

## Evidence map

| Gate item | Evidence |
|---|---|
| Protocol / capability freeze | [ADR-015](adr/ADR-015-CONNECTOR-PROTOCOLS.md) |
| Implementation order | [IMPLEMENTATION_PLAN_0_38](IMPLEMENTATION_PLAN_0_38.md) |
| Landing-zone domain plan | [LANDING_ZONE_CONNECTOR_PLAN](LANDING_ZONE_CONNECTOR_PLAN.md) |
| Capability matrix | [CONNECTOR_CAPABILITY_MATRIX_0_38.json](CONNECTOR_CAPABILITY_MATRIX_0_38.json) |
| Cross-provider burn-in | `tests/connectors/test_cross_provider_0_38.py` |
| Finding severity / locked decisions | [FINDINGS_0_38](FINDINGS_0_38.md) |
| Adopter migration | [MIGRATION_0_37_TO_0_38](MIGRATION_0_37_TO_0_38.md) |
| Adopter highlights | [WHATS_NEW_0_38](../01_GETTING_STARTED/WHATS_NEW_0_38.md) |
| Prior foundation exit | [EXIT_GATE_0_37](EXIT_GATE_0_37.md) |

## Acceptance checklist

### Planning (Wave 0)

- [x] [IMPLEMENTATION_PLAN_0_38](IMPLEMENTATION_PLAN_0_38.md) published
- [x] [ADR-015](adr/ADR-015-CONNECTOR-PROTOCOLS.md) Accepted
- [x] This exit gate published
- [x] [FINDINGS_0_38](FINDINGS_0_38.md) ledger opened
- [x] [WHATS_NEW_0_38](../01_GETTING_STARTED/WHATS_NEW_0_38.md) published
- [x] [MIGRATION_0_37_TO_0_38](MIGRATION_0_37_TO_0_38.md) published
- [x] Indexes / roadmap / mkdocs point at 0.38 as current connectivity gate

### Protocols and planning

- [x] Source, sink, and storage protocols public and discoverable
- [x] Structured bindings secret-free and fingerprint-stable
- [x] Capability negotiation fails closed at plan time
- [x] Static plans never list live files
- [x] StorageBinding compatibility adapter without false connector claims

### Landing zone and publication

- [x] Snapshot and incremental modes pass deterministic conformance
- [x] Checkpoint schema `etlantic.landing_checkpoint/1` proven
- [x] Cursor/ledger advances only after proven committed publications
- [x] No core directory-watch loops

### Reference set and release

- [x] Local, S3, Iceberg, Snowflake, and PostgreSQL pass declared matrices (fake/CI)
- [x] Independent connector proof: soft-continue `038-X-01` + in-repo EP stub
- [x] Unresolved P0 count is **0**
- [x] Every remaining P1 has owner, target phase, mitigation, rationale
- [x] Exact candidate wheels, docs, and migration guidance rehearsed in-repo

## Residual / follow-ons

- Continuous file-drop watching / submitters — **0.39+**
- Distributed checkpoint fencing and multi-worker recovery — **0.40–0.41**
- Echo plugin source connector on PyPI (`038-X-01`) — before/with first
  cloud Supported promotion
- TransformationModel incubation — **0.52**

## See also

- [Implementation plan 0.38](IMPLEMENTATION_PLAN_0_38.md)
- [Findings ledger 0.38](FINDINGS_0_38.md)
- [ADR-015: Connector Protocols](adr/ADR-015-CONNECTOR-PROTOCOLS.md)
