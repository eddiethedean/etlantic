# Phase 0.56 Local Qualification

**Decision: OPEN.** This record reports local implementation evidence; it does
not claim that AC056-001–044 have all passed. The evidence index leaves each
criterion open until its complete documented case has been observed.

Current index: 3 criteria passed, 39 pending, and 2 blocked of 44.

## Candidate environment

- Date: 2026-09-30
- Host: macOS 25.5.0, arm64
- Python: 3.11.15
- Live database: isolated local PostgreSQL 16.14 container
- Workspace base: `e7fd6b866dbecab646cf68b73405ee06ea4437e5`
- Candidate packages: core and companions currently build as 0.55.0; this is
  implementation work against the 0.55 compatibility baseline, not a release.

## Executed evidence

- Default non-optional suite:
  `uv run pytest -q -m "not medallantic and not polars and not pandas and not sql and not spark and not real_pyspark and not airflow and not prefect and not keyring and not sqlmodel and not datafusion"`
  — 2,717 passed, 67 skipped, and 586 deselected. The source-linked 0.52
  adaptive evidence regression was the sole failure in that run because its
  artifacts were stale after these source edits. The artifacts were regenerated
  and verified across 10 artifacts and 18 acceptance criteria; the exact
  regression test then passed on rerun.
- CP1 and CP-GA OpenAPI snapshots were refreshed for the managed rerun and
  replay endpoints; both stable-operation snapshot tests passed.
- Live PostgreSQL connector and multiprocess acceptance:
  `ETLANTIC_SQL_TEST_URL=... ETLANTIC_CP_TEST_URL=... uv run pytest -q tests/sql/test_postgresql_live_0_56.py tests/sqlmodel/test_durable_postgresql_multiprocess_0_56.py` — 4 passed.
- SQLModel migration campaign against SQLite and isolated PostgreSQL schemas:
  `ETLANTIC_SQLMODEL_TEST_URL=... uv run pytest -q tests/sqlmodel/test_cp1_migrations_0_51.py` — 8 passed.
- CP1 authorization matrix: 48 passed.
- Managed HTTP malformed revision-selector boundary: 1 passed.
- Native staged-checkpoint deadline rollback: 2 parameter cases passed.
- Standard SQLModel-backed FastAPI lifecycle:
  `uv run pytest -q tests/fastapi/test_managed_backend_0_56.py` — 4 passed.
  SQLite lifecycle cases verify the one-engine managed constructor, strict
  migration gate and partial-initialization disposal, disposal after failed
  startup and normal shutdown, and recovery of accepted durable work after
  shutdown. This is local lifecycle evidence, not a PostgreSQL qualification.
- Provider-aware run-action reason:
  `uv run pytest -q tests/fastapi/test_managed_control_races_0_56.py::test_action_discovery_reports_unsupported_cancel_provider`
  — 1 passed. The command query now reports `provider_unsupported` when the
  submission store cannot cancel; execution remains a reauthorized 501.
- Legacy incomplete submission:
  `uv run pytest -q tests/fastapi/test_managed_control_races_0_56.py::test_legacy_acceptance_without_envelope_cannot_be_replanned_or_executed`
  — 1 passed. A legacy record with a well-formed but unverified plan hash is
  neither replanned into an envelope nor dispatched by the managed runtime.
- Managed command and authorization matrix:
  `uv run pytest -q tests/fastapi/test_managed_application_0_56.py tests/fastapi/test_managed_backend_0_56.py tests/fastapi/test_cp1_full_authz_matrix.py tests/fastapi/test_managed_control_races_0_56.py`
  — 64 passed before the rerun endpoint was added. It includes action-provider
  availability, concurrent state changes after action discovery,
  authorization rechecks, legacy acceptance handling and failed-run retry
  behavior.
- Managed rerun/replay service and HTTP commands:
  `uv run pytest -q tests/fastapi/test_managed_application_0_56.py tests/fastapi/test_managed_backend_0_56.py tests/fastapi/test_cp1_full_authz_matrix.py tests/fastapi/test_managed_control_races_0_56.py tests/fastapi/test_managed_rerun_http_0_56.py`
  — 67 passed. A packaged worker performed both accepted child transfers from
  the immutable parent snapshot, and tests cover explicit rerun after a
  committed effect, full-snapshot replay intent, unknown-effect rejection,
  idempotency, action discovery and OpenAPI registration. AC056-031 remains
  open until checkpoint resume, repair and backfill are executable and the
  complete lifecycle case is qualified.
- Managed provider scope and secret cache isolation:
  `uv run pytest -q tests/fastapi/test_managed_rerun_http_0_56.py tests/secrets/test_secrets.py tests/control_plane/test_control_plane.py`
  — 20 passed. A server-configured resource owner reaches secret, storage and
  connector calls through the worker's temporary trusted scope. Runtime secret
  cache entries are partitioned by principal and full tenant/workspace/
  environment/security-domain/owner scope; a different scope and unscoped
  local runtime cannot reuse the value. The scope is absent from accepted
  envelopes. AC056-023 remains open for action executors, resource resolvers,
  tampered-reference policy and complete lifecycle qualification.
- Follow-up core and FastAPI wheels:
  `uv build --package etlantic --wheel` and
  `uv build --package etlantic-fastapi --wheel` succeeded. Both wheels were
  force-installed into the existing clean Python 3.11 environment alongside
  the phase candidate's SQLModel wheel; public imports, migrations,
  managed-backend construction and explicit close passed a smoke check. The
  latest core and FastAPI wheels were installed again; SQLite migrations,
  managed-backend construction/close and rerun/replay OpenAPI registration
  passed. The latest clean-wheel smoke also imported `TrustedExecutionScope`
  and verified that a configured resource owner reaches the server context.
- Wheel build: all 25 workspace wheels built successfully.
- Clean install smoke: core, FastAPI, PostgreSQL SQL, Foundry and SQLModel
  wheels installed into a fresh Python 3.11 environment; public imports and
  Foundry configuration-schema discovery passed.
- Public CLI: sample pipeline validation passed with no diagnostics; plan
  generation returned fingerprint
  `8f3879b301b3b0ea1b87434eef3dd0a58ef0cbe8342ced056323cc9d6d5b19da`.
- Plugin manifests: 16 packages passed.
- Final `scripts/check_adaptive_0_52.py --write` refreshed and verified 10
  artifacts across 18 prior-phase acceptance criteria; its exact CI regression
  test passed afterward.
- `scripts/check_pyright.sh` passed: 784 suppressions matched the locked
  inventory, the strict shadow scan matched its 10,452-diagnostic baseline,
  and raw Pyright reported zero errors and warnings.
- `ruff check .`, `git diff --check`, plugin-manifest checks and `uv lock --check`
  passed.

## Open release requirements

- AC056-001–002, AC056-004–019 and AC056-033: the managed application,
  authorization, specification, admission, worker, result and PostgreSQL
  provider paths have implementation and focused tests, but their full
  criterion-level failure, concurrency and runtime campaigns remain open.
- AC056-020–026: isolated action jobs, previews/provisioning, scoped secret
  lifecycle and immutable upload leases are not fully implemented and observed.
- AC056-027–029 and AC056-031–032: scheduler admission parity,
  checkpoint-resume/repair/backfill, qualified pause/amendment and complete
  lifecycle qualification remain open. Idempotent rerun and full-snapshot
  replay commands now share the managed worker path.
- AC056-034 and AC056-036: no isolated live Foundry account is configured.
  The required two independent Foundry scopes and all 12 real-worker pairings
  have not been exercised; mock transport tests do not qualify them.
- AC056-037–041 and AC056-043–044: independent private-provider, full
  disclosure campaign, PostgreSQL backup/restore/failure, version-skew/rollback,
  complete advanced engine matrix, managed adaptive `/2`, and generic consumer
  evidence remain open.

See [`RELEASE_INDEX.json`](RELEASE_INDEX.json) for the per-criterion status,
case references, provider tuple and open reason. These limitations keep the
0.56 release decision open even though the implemented local gates pass.
