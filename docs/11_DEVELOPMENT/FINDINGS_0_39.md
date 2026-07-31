# Findings Ledger 0.39 — Control-Plane API and Identity (CP1)

> **Status: Gate-ready for tag/publish rehearsal toward ETLantic 0.39.0** after
> post-exit honesty pass (idempotency/poll/SSE, authz/redaction, CI pins/docs).
> **P0 = 0.** Soft-continue: `038-X-01` (echo plugin PyPI connector) remains
> non-blocking. **CP1 ≠ production multi-tenant** (**0.43**).

## Severity policy

From [IMPLEMENTATION_PLAN_0_39](IMPLEMENTATION_PLAN_0_39.md):

| Severity | Meaning | Release treatment |
|---|---|---|
| **P0** | Identity spoofing, cross-tenant disclosure, durable-accept loss, secret/row leakage, unsafe schema authority side effect | Must close before 0.39 |
| **P1** | Material compatibility, authz matrix gaps, OpenAPI/client, multi-worker, or adoption risk | Close or defer with owner, mitigation, target phase, and non-blocking rationale |
| **P2** | Localized usability, performance, or maintainability defect | May defer with owner and target |
| **P3** | Cosmetic or opportunistic improvement | Backlog |

Changing severity without written rationale does not close a finding.

## Locked dispositions

Recorded in
[ADR-016: Control-Plane Identity](adr/ADR-016-CONTROL-PLANE-IDENTITY.md). Do not
reopen without a written finding and migration plan.

| Decision | Outcome | Notes |
|---|---|---|
| Identity vocabulary | `Principal`, `TenantRef`, `WorkspaceRef`, `EnvironmentRef`, `SecurityDomain`, immutable `ControlPlaneContext` | Server-derived; no credentials in serialized context |
| Correlation id | Opaque `correlation_id` / `X-Correlation-ID` | Not authorization material |
| Idempotency | Scoped by tenant, workspace, principal, operation, and client key | Conflict on fingerprint mismatch |
| Non-enumeration | Authz before lookup; cross-scope → `404`; in-scope forbid → `403` | Deny existence disclosure across tenants |
| Durable submission | `202` only after accept receipt; no `BackgroundTasks` for heavy work | Process-local globals are not the acceptance store; **`accepted` ≠ executed** |
| Events / SSE | `etlantic.control_plane.event/1` + `sse_cursor/1` | 0.41-migration-friendly |
| Path/header tenant claims | Routing only — never authority | Spoofed claims denied under non-enum policy |
| CP1 vs GA | CP1 ≠ production multi-tenant | Graduation remains **0.43** |
| Landing watch | Outside core | Submitters compose against 0.38 bindings |
| Dual FastAPI surface | `ETLanticAPI` (CP1) + thin `create_reference_app` | `include_router` does not install Problem Details — host responsibility |

## Open findings

Open **P0 count is 0**.

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| `038-X-01` | P1 | Ecosystem + echo maintainer | Soft-continue | Independent echo connector on PyPI still soft-continue | Does not block CP1; see [FINDINGS_0_38](FINDINGS_0_38.md) |

## Closed in 0.39 (post-exit honesty pass)

Post-exit audit reopened P0/P1 honesty gaps; all listed top-20 rows closed with
regressions.

| ID | Severity | Summary | Evidence |
|---|---|---|---|
| `039-P0-01` | P0 | Idempotency key omitted principal + operation | ADR-016 tuple in memory + SQLModel stores; `tests/control_plane/test_idempotency_scope_0_39.py` |
| `039-P0-02` | P0 | `poll_accepted` unscoped across tenants | Context-scoped poll; `test_idempotency_scope_0_39.py`, `tests/fastapi/test_cp1_submit_hardening.py` |
| `039-P0-03` | P0 | Idempotent submit re-appended `run.accepted` SSE | Accept returns created flag; append once; `test_cp1_submit_hardening.py` |
| `039-P0-04` | P0 | Submit body could override path `definition_id` | Path wins / mismatch 400; `test_cp1_submit_hardening.py` |
| `039-H05` | P1 | `/ready` returned 200 when stores missing | Ready → 503; `tests/fastapi/test_cp1_full_authz_matrix.py::test_ready_503_when_stores_missing` |
| `039-H06` | P1 | In-scope deny used opaque 404 instead of 403 | ADR matrix; `tests/fastapi/test_cp1_authz_matrix.py` |
| `039-H07` | P1 | Two-workspace HTTP matrix missing | Same-tenant `ws-1`/`ws-2`; `test_cp1_full_authz_matrix.py` |
| `039-H08` | P1 | Definition / validate / plan responses unredacted | Outbound redaction; `tests/fastapi/test_cp1_redaction.py` |
| `039-H09` | P1 | Validate/plan `verify=False` + hard-coded preview overclaim | Injectable profile + Experimental label / production path; redaction tests |
| `039-H10` | P1 | `MemoryEventStore` race under concurrent append | `RLock`; `tests/control_plane/test_control_plane.py::test_memory_event_store_concurrent_append` |
| `039-H11` | P1 | No durable EventStore / unbounded `follow=true` | SQLModel event store + follow poll/duration cap; `tests/sqlmodel/test_control_plane_stores.py`, SSE README / routes |
| `039-H12` | P1 | Schema observation ack always 200 for phantom IDs | 404 after authz; `tests/fastapi/test_cp1_durable.py` |
| `039-H13` | P1 | Event / accept receipt missing ADR additive fields | `/1` additive fields + OpenAPI; `tests/fastapi/test_cp1_openapi.py` |
| `039-H14` | P1 | `event_matches_run` over-matched `acceptance_id` | Explicit `run_id` only; `tests/fastapi/test_cp1_sse.py` |
| `039-H15` | P1 | SQLModel CP store tests unmarked → deselected in CI | `pytestmark = pytest.mark.sqlmodel` on `tests/sqlmodel/test_control_plane_stores.py` |
| `039-H16` | P1 | Connector `PACKAGE_VERSION` / local-files still `0.38.0` | Bumped to `0.39.0` in sql/s3/iceberg/snowflake + `local_files.py` |
| `039-H17` | P1 | Adopter pin/expect bugs (QUICKSTART / pilot / sample_pilot) | Retargeted to 0.39.0; `scripts/check_docs.py` needles for expect/prints/sample_pilot |
| `039-H18` | P1 | Dual-surface / maturity docs still “thin ref / 0.38” | OPTIONAL_PACKAGES, DISTRIBUTION, KNOWN_ISSUES, EVALUATOR, PRODUCTION_READINESS |
| `039-H19` | P1 | Surface inventory / ADR-016 / echo floor leftovers | Provisional CP wire schemas registered; ADR core **0.39.0**; echo comments `>=0.39,<0.40` |
| `039-H20` | P1 | Findings/exit honesty + residual hardening | This ledger + EXIT_GATE; OpenAPI snapshot fail-if-missing; `include_router` Problem Details host-owned; optional `fastapi` marker on `test_cp1_*.py`; `accepted` ≠ executed noted |

## Threat-review dispositions (Wave 7)

| Threat | Disposition | Evidence |
|---|---|---|
| Identity spoofing (path/header claims vs `ControlPlaneContext`) | **Mitigated** | Path/header tenant values are routing only; `membership_context_factory` + `assert_path_scope` / server-derived context; ADR-016; `tests/fastapi/test_cp1_authz_matrix.py`, `test_cp1_full_authz_matrix.py` |
| Idempotency collisions across tenant/workspace/principal | **Fixed** | Store keys are ADR-016 `(tenant, workspace, principal, operation, key)` with conflict on payload mismatch; `test_idempotency_scope_0_39.py`, `test_cp1_durable.py` |
| Artifact access without prior authz | **Fixed** | `require_authorized(..., "run.artifacts", ...)` precedes run lookup; cross-tenant 404 in full authz matrix |
| Schema observation becoming contract authority via API side effect | **Mitigated** | Observations labeled `observations`; ack explicitly states non-authority; `tests/fastapi/test_cp1_durable.py` asserts label/note |
| Information disclosure via status codes, lists, cursors, or SSE resume | **Fixed** | Non-enumeration 401/403/404 policy; list isolation; SSE authz before stream; unknown cursor → 410 (not silent skip); redaction on errors/events/reports — `tests/fastapi/test_cp1_sse.py`, `test_cp1_redaction.py`, `test_cp1_full_authz_matrix.py` |

## Carried soft-continues from 0.38

| ID | Severity | Notes |
|---|---|---|
| `038-X-01` | P1 | Independent echo plugin connector on PyPI still soft-continue; does not block CP1 |

## See also

- [Implementation plan 0.39](IMPLEMENTATION_PLAN_0_39.md)
- [Exit gate 0.39](EXIT_GATE_0_39.md)
- [ADR-016: Control-Plane Identity](adr/ADR-016-CONTROL-PLANE-IDENTITY.md)
- [Multi-tenant control plane plan](MULTI_TENANT_CONTROL_PLANE_PLAN.md)
- [Prior connectivity findings](FINDINGS_0_38.md)
