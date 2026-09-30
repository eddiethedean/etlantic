# Phase 0.56 Local Qualification

**Decision: OPEN.** This record reports local implementation evidence; it does
not claim that AC056-001–044 have all passed. The evidence index marks a
criterion passed only after its complete documented case has been observed.

Current index: 6 criteria passed, 36 pending, and 2 blocked of 44.

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
  — 2,745 passed, 67 skipped, and 589 deselected. The first run had one failure
  because source-linked 0.52 adaptive evidence was stale after these edits. The
  artifacts were regenerated and verified across 10 artifacts and 18
  acceptance criteria; `tests/plan/test_phase_0_52_review_blockers.py::test_final_052_006_evidence_regenerates_cleanly`
  then passed on rerun.
- CP1 and CP-GA OpenAPI snapshots were refreshed for the managed rerun and
  replay endpoints; both stable-operation snapshot tests passed.
- Live PostgreSQL connector and multiprocess acceptance:
  `ETLANTIC_SQL_TEST_URL=... ETLANTIC_CP_TEST_URL=... uv run pytest -q tests/sql/test_postgresql_live_0_56.py tests/sqlmodel/test_durable_postgresql_multiprocess_0_56.py` — 4 passed.
- Final isolated PostgreSQL 16.14 qualification:
  `ETLANTIC_SQLMODEL_TEST_URL=... uv run pytest -q tests/sqlmodel/test_cp1_migrations_0_51.py`
  — 14 passed across SQLite and PostgreSQL schemas, including migration 008,
  concurrent SQLModel event sequencing, downgrade/re-upgrade and retained event
  history. `ETLANTIC_SQL_TEST_URL=... uv run pytest -q
  tests/sql/test_postgresql_live_0_56.py` — 4 passed, covering append/upsert/
  replace, idempotent replay, bounded source/schema reads, permission denial,
  staged rollback and lost-ack reconciliation. `ETLANTIC_CP_TEST_URL=... uv run
  pytest -q tests/sqlmodel/test_durable_postgresql_multiprocess_0_56.py` — 2
  passed, covering eight-process single acceptance and quota idempotency plus
  restart reads. The disposable database ran PostgreSQL 16.14; it was isolated
  from application data.
- Clean installed-wheel smoke:
  rebuilt core, FastAPI and SQLModel 0.55.0 candidate wheels were installed
  into a fresh Python 3.14.3 virtual environment without workspace path
  injection. Migration 008 applied, idempotent event replay survived engine
  disposal/reopen, the standard managed backend constructed and closed, and
  generated OpenAPI included `/v1/runs/{run_id}/events/history`. Exact wheel
  sizes and SHA-256 values are recorded in `WHEEL_MANIFEST.json`. This is
  useful AC056-040 evidence; complete package/export/schema compatibility,
  version skew and upgrade/rollback qualification remain pending.
- SQLModel migration campaign against SQLite and isolated PostgreSQL schemas:
  `ETLANTIC_SQLMODEL_TEST_URL=... uv run pytest -q tests/sqlmodel/test_cp1_migrations_0_51.py` — 8 passed.
- CP1 authorization matrix: 48 passed.
- Managed HTTP malformed revision-selector boundary: 1 passed.
- Native staged-checkpoint deadline rollback: 2 parameter cases passed.
- Standard SQLModel-backed FastAPI lifecycle:
  `uv run pytest -q tests/fastapi/test_managed_backend_0_56.py` — 5 passed.
  SQLite lifecycle cases verify the one-engine managed constructor, strict
  migration gate and partial-initialization disposal, disposal after failed
  startup and normal shutdown, and recovery of accepted durable work after
  shutdown. This is local lifecycle evidence, not a PostgreSQL qualification.
- Standard worker report durability and recovery:
  `uv run pytest -vv -s -o faulthandler_timeout=15 tests/fastapi/test_managed_backend_0_56.py::test_standard_backend_worker_persists_queryable_report_in_sqlmodel`
  — 1 passed. The standard backend worker transferred a canonical JSON-to-CSV
  run without a caller runner, persisted its report in the scoped SQLModel
  table, and exposed the report after backend restart. A simulated worker crash
  after report persistence recovered the expired lease from the stored report;
  the test changed the source before recovery and verified the sink was not
  written a second time. A second workspace could not read the scoped report.
- Versioned report-table migration:
  `uv run pytest -q tests/sqlmodel/test_cp1_migrations_0_51.py`
  — local SQLite cases cover fresh install, upgrade from each prior head through
  006, restart, downgrade to 006 and re-upgrade. PostgreSQL cases were skipped
  on the initial SQLite-only run; the final PostgreSQL-backed rerun above passed
  all 14 migration cases.
- Idempotent lifecycle-event storage and migration:
  `uv run pytest -q tests/control_plane/test_control_plane.py::test_memory_event_store_append_once_is_scoped_and_conflict_checked tests/sqlmodel/test_control_plane_stores.py::test_sqlite_event_append_once_survives_restart_and_rejects_conflicts tests/sqlmodel/test_cp1_migrations_0_51.py::test_idempotent_event_migration_round_trip_preserves_event_history`
  — 3 passed. Migration 008 adds a separate scoped event-key table, preserving
  CP1 event rows and allowing retry-safe lifecycle publication. The migration
  rollback to 007 and re-upgrade retained event history; SQLite restart returned
  the original event for the same key and rejected changed content.
- Managed lifecycle events and paginated event history:
  `uv run pytest -q tests/fastapi/test_managed_backend_0_56.py::test_standard_backend_worker_persists_queryable_report_in_sqlmodel tests/fastapi/test_cp1_sse.py tests/fastapi/test_managed_application_0_56.py::test_headless_run_event_pages_are_scoped_and_resumable tests/fastapi/test_cp1_full_authz_matrix.py tests/fastapi/test_cp1_openapi.py`
  — 62 passed in the latest focused run (the final worker integration and all
  event-history/authz/OpenAPI tests were included). Lifecycle delivery uses
  stable per-attempt keys and persists one start/completion pair across report
  recovery. Headless and HTTP page queries return the same scoped events;
  reconnect cursors advance through the workspace log, with explicit empty-page
  behavior when other runs' events are interleaved. Unknown scoped cursors
  return 410. AC056-019 remains pending for retention, artifact authorization
  and the complete reconnect/duplicate-delivery isolation campaign.
- Provider-aware run-action reason:
  `uv run pytest -q tests/fastapi/test_managed_control_races_0_56.py::test_action_discovery_reports_unsupported_cancel_provider`
  — 1 passed. The command query now reports `provider_unsupported` when the
  submission store cannot cancel; execution remains a reauthorized 501.
- Legacy incomplete submission:
  `uv run pytest -q tests/fastapi/test_managed_control_races_0_56.py::test_legacy_acceptance_without_envelope_cannot_be_replanned_or_executed`
  — 1 passed. A legacy record with a well-formed but unverified plan hash is
  neither replanned into an envelope nor dispatched by the managed runtime.
- Installed connector catalog and option schemas:
  `uv run pytest -q tests/connectors/test_connector_catalog_0_56.py tests/connectors/test_connector_configuration_schemas_0_56.py tests/connectors/test_discovery_0_38.py tests/fastapi/test_managed_application_0_56.py tests/fastapi/test_cp1_full_authz_matrix.py tests/fastapi/test_cp1_openapi.py tests/fastapi/test_cp_ga_openapi_0_43.py`
  — 69 passed. Headless and HTTP catalog requests return the same
  profile-authorized installed-provider schemas, including protocol/package
  versions, maturity and capabilities. Schema types, defaults and constraints
  are preserved; secret defaults/examples/enums are stripped for named or
  provider-marked fields, and credential-named keys are recursively removed
  from nested samples. Unknown provider options fail planning with `PMCONN880`
  without echoing submitted values. AC056-006 is qualified.
- Typed request controls and managed-envelope resolution:
  `uv run pytest tests/runtime/test_run_request_wire.py tests/runtime/test_local_runtime.py -q`
  — 20 passed. Request import/export preserves nested overrides and namespaced
  extension data, rejects unknown constructor semantics and secret-bearing
  extensions, and isolates caller/export mutations. Profile precedence is
  field-specific; explicit defaults such as one attempt, zero backoff and
  no timeout survive the wire. Envelope schema `/2` stores the requested and
  resolved request plus deterministic setting provenance, and the packaged
  worker consumes the resolved values. A legacy `/1` envelope upgrades using
  the previous default precedence. A clean Python 3.11 installation of the
  built core, FastAPI and Foundry wheels passed the request round-trip and
  envelope-schema smoke check. AC056-005 is qualified.
- Connector catalog final focused rerun:
  `pytest -q tests/connectors/test_connector_catalog_0_56.py tests/fastapi/test_managed_application_0_56.py::test_connector_catalog_is_shared_by_headless_and_http tests/fastapi/test_managed_application_0_56.py::test_connector_catalog_authorizes_before_plugin_discovery tests/fastapi/test_cp1_openapi.py tests/fastapi/test_cp_ga_openapi_0_43.py`
  — 6 passed. The final schema redaction test covers snake_case and camelCase
  secret fields, nested credentials in generic samples, provider-marked
  `writeOnly` fields, and installed package/version metadata. Headless/HTTP
  output parity, authorization-before-discovery and both OpenAPI operation
  snapshots passed.
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
- Revision-pinned admission, resource authorization and concurrent idempotency:
  `uv run pytest -q tests/fastapi/test_managed_application_0_56.py tests/fastapi/test_managed_backend_0_56.py tests/fastapi/test_cp1_full_authz_matrix.py tests/fastapi/test_managed_control_races_0_56.py tests/fastapi/test_managed_rerun_http_0_56.py tests/sqlmodel/test_cp1_migrations_0_51.py tests/sqlmodel/test_registry_stores_0_40.py tests/sqlmodel/test_cp4_stores_0_42.py tests/sqlmodel/test_durable_postgresql_multiprocess_0_56.py`
  — 93 passed, 5 skipped. Managed submission resolves an immutable definition
  revision once, authorizes every planned logical resource before acceptance,
  and binds policy to a verified effective fingerprint. Tests reject forged
  plan hashes and unknown revisions, preserve `latest-approved` selection on
  retry after an alias change, verify concurrent same-intent submissions charge
  quota once, and make concurrent changed intent conflict under the same
  idempotency key. Migration 006 imports legacy CP1 definitions into the CP2
  revision registry while retaining the CP1 rows. AC056-007 and AC056-008 remain
  open for durable resource/version resolution, full scope disclosure coverage,
  and process-level PostgreSQL failure and retry qualification.
- Current SQLModel migration and governance campaign after revision backfill:
  `uv run pytest -q tests/control_plane/ga/test_cp_ga_campaigns.py tests/sqlmodel/test_cp1_migrations_0_51.py tests/sqlmodel/test_registry_stores_0_40.py tests/sqlmodel/test_cp4_stores_0_42.py tests/sqlmodel/test_durable_postgresql_multiprocess_0_56.py`
  — 26 passed, 5 skipped. SQLite migration upgrade/backfill/restart and
  governance persistence passed; PostgreSQL-only cases skipped because database
  test URLs are not configured in this environment.
- Managed provider scope and secret cache isolation:
  `uv run pytest -q tests/fastapi/test_managed_rerun_http_0_56.py tests/secrets/test_secrets.py tests/control_plane/test_control_plane.py`
  — 20 passed. A server-configured resource owner reaches secret, storage and
  connector calls through the worker's temporary trusted scope. Runtime secret
  cache entries are partitioned by principal and full tenant/workspace/
  environment/security-domain/owner scope; a different scope and unscoped
  local runtime cannot reuse the value. The scope is absent from accepted
  envelopes. AC056-023 remains open for action executors, resource resolvers,
  tampered-reference policy and complete lifecycle qualification.
- Secret version selection and audit:
  `uv run pytest -q tests/secrets/test_secrets.py tests/runtime/test_bugfixes.py`
  — 24 passed. Environment and mounted-file providers reject unsupported
  version selectors; managed resolution rejects an unsupported or mismatched
  exact version and records a versioned provider's resolved version in the
  security event without the value. AC056-024 remains open for authorized
  late binding, rotation, revocation, expiry, outage and lease qualification.
- Managed late-binding policy and rotation:
  `uv run pytest -q tests/runtime/test_bugfixes.py tests/fastapi/test_managed_rerun_http_0_56.py tests/secrets/test_secrets.py`
  — 28 passed. Managed `current` references now require an injected worker
  policy, are authorized again before cache lookup, and fail before provider
  access when the policy is missing or denies them. Versioned providers must
  advertise alias support; managed alias values and provider values with lease,
  renewal, or revocation capabilities bypass the process cache. Tests verify
  rotation is visible on consecutive lookups, actual versions are audited,
  and scoped policy reaches the secret provider. AC056-024 remains open for
  provider lease renewal, revocation, expiry, outage and full lifecycle
  qualification.
- Provider alias declarations and lifecycle-aware caching:
  `uv run pytest -vv tests/runtime/test_bugfixes.py::test_versioned_provider_must_advertise_current_alias_support`
  — 1 passed; `uv run pytest -vv tests/runtime/test_bugfixes.py::test_secret_lifecycle_capability_disables_process_cache`
  — 3 passed. Versioned providers without alias capability are rejected before
  resolution, and providers advertising leases, renewal or revocation bypass
  process caching.
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
  The updated core wheel was force-installed, and its
  `etlantic.secrets.SecretAliasAuthorizer` export and
  `PipelineRuntime.secret_alias_authorizer` field passed an import smoke check.
- Wheel build: all 25 workspace wheels built successfully.
- Clean install smoke: core, FastAPI, PostgreSQL SQL, Foundry and SQLModel
  wheels installed into a fresh Python 3.11 environment; public imports and
  Foundry configuration-schema discovery passed.
- Latest clean catalog wheel smoke: core, FastAPI and Foundry wheels built from
  this candidate installed into a fresh Python 3.11 virtual environment.
  Profile discovery returned schema-bearing Foundry source, sink and storage
  connectors with installed package versions, plus the built-in `local-files`
  source; public catalog imports, the `etlantic.connector_catalog/1` contract
  and FastAPI router import passed.
- Latest managed-backend clean wheel smoke: refreshed core, FastAPI and SQLModel
  wheels installed into a fresh Python 3.14.3 virtual environment. Migration 007,
  the registry-backed managed constructor, close, and the in-memory revision
  reversion/current-selection behavior all passed.
- Managed SQLModel report wheel smoke: the refreshed wheels were installed into
  a separate clean Python 3.14.3 environment. A fresh SQLite database migrated
  to `007_managed_run_reports_0_56`; the standard worker transferred a canonical
  JSON-to-CSV definition without a caller runner, persisted the actual report,
  and served that report after reopening the backend. Output and report identity
  stayed consistent after the source file changed.
- Final clean wheel smoke for event durability:
  `uv build --package etlantic --wheel`,
  `uv build --package etlantic-fastapi --wheel`, and
  `uv build --package etlantic-sqlmodel --wheel` succeeded. All three candidate
  wheels installed into a fresh Python 3.14.3 environment. The installed
  SQLModel wheel applied migration `008_idempotent_run_events_0_56`; its event
  store returned the original event after engine disposal/reopen. The installed
  FastAPI wheel constructed and closed the standard SQLModel backend, and its
  generated OpenAPI included the bounded run-event history endpoint.
- Public CLI: sample pipeline validation passed with no diagnostics; plan
  generation returned fingerprint
  `8f3879b301b3b0ea1b87434eef3dd0a58ef0cbe8342ced056323cc9d6d5b19da`.
- Plugin manifests: 16 packages passed.
- Final `scripts/check_adaptive_0_52.py --write` refreshed and verified 10
  artifacts across 18 prior-phase acceptance criteria; its exact CI regression
  test passed afterward.
- `scripts/check_pyright.sh` passed: 784 suppressions matched the locked
  inventory, the strict shadow scan matched its 10,453-diagnostic baseline,
  and raw Pyright reported zero errors and warnings. The suppression count is
  unchanged; the strict digest was refreshed for the managed route and
  acceptance-test line shifts and the new test surface.
- `ruff check .`, `git diff --check`, plugin-manifest checks and `uv lock --check`
  passed.

## Open release requirements

- AC056-001–002, AC056-004, AC056-009–019 and AC056-033: the managed application,
  authorization, specification, admission, worker, result and PostgreSQL
  provider paths have implementation and focused tests, but their full
  criterion-level failure, concurrency and runtime campaigns remain open.
- AC056-017–018: the standard SQLModel backend now persists runtime reports in
  a tenant/workspace-scoped table, and worker recovery reuses a report committed
  before attempt acknowledgment. Run-level start/completion events have
  idempotent scoped persistence. Bounded headless and HTTP event history reads
  share authorization and scoped cursor semantics. Report-publication failure
  after an external sink commit, event retention/artifact authorization, and
  separate result and cleanup state machines remain unqualified.
- AC056-007–008: immutable revision pinning, resource authorization,
  effective-fingerprint policy binding and same/different-intent retry behavior
  now have focused evidence. Complete durable resource/version resolution,
  full disclosure and cross-process CP1/CP3 failure/retry campaigns remain open.
- AC056-039 and AC056-042: PostgreSQL 16.14 migration and multi-process
  acceptance/quota tests now pass. AC056-042 is qualified for the tested 0.55
  migration chain and legacy incomplete-payload guard. AC056-039 remains open
  for backup/restore and broader failure campaigns.
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
  evidence remain open. AC056-040 has clean Python 3.14.3 wheel-build/install,
  migration-008, backend-construction and OpenAPI smoke evidence; its complete
  compatibility, version-skew, migration rollback and package matrix remains
  open.

See [`RELEASE_INDEX.json`](RELEASE_INDEX.json) for the per-criterion status,
case references, provider tuple and open reason. These limitations keep the
0.56 release decision open even though the implemented local gates pass.
