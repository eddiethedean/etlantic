# Findings Ledger 0.39 — Control-Plane API and Identity (CP1)

> **Status: Gate-ready for tag/publish rehearsal toward ETLantic 0.39.0.**
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
| Durable submission | `202` only after accept receipt; no `BackgroundTasks` for heavy work | Process-local globals are not the acceptance store |
| Events / SSE | `etlantic.control_plane.event/1` + `sse_cursor/1` | 0.41-migration-friendly |
| Path/header tenant claims | Routing only — never authority | Spoofed claims denied under non-enum policy |
| CP1 vs GA | CP1 ≠ production multi-tenant | Graduation remains **0.43** |
| Landing watch | Outside core | Submitters compose against 0.38 bindings |

## Open findings

Open **P0 count is 0**.

| ID | Severity | Owner | State | Summary | Evidence / disposition |
|---|---|---|---|---|---|
| — | — | — | — | No open P0/P1 rows blocking exit | Wave 7 closed |

## Threat-review dispositions (Wave 7)

| Threat | Disposition | Evidence |
|---|---|---|
| Identity spoofing (path/header claims vs `ControlPlaneContext`) | **Mitigated** | Path/header tenant values are routing only; `membership_context_factory` + `assert_path_scope` / server-derived context; ADR-016; `tests/fastapi/test_cp1_authz_matrix.py`, `test_cp1_full_authz_matrix.py` |
| Idempotency collisions across tenant/workspace/principal | **Fixed** | Store keys are `(tenant, workspace, idempotency_key)` with conflict on payload mismatch; multi-worker shared-store test in `tests/fastapi/test_cp1_durable.py` |
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
