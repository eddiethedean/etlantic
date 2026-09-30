# Phase 0.56 Local Qualification

**Decision: OPEN.** This record reports local implementation evidence; it does
not claim that AC056-001–044 have all passed. The evidence index marks a
criterion passed only after its complete documented case has been observed.

Current index: 11 criteria passed, 31 pending, and 2 blocked of 44.

## Candidate environment

- Date: 2026-09-30
- Host: macOS 25.5.0, arm64
- Python: 3.11.15
- Live databases: earlier isolated PostgreSQL 16.14 container evidence; the
  current input-resource race and migration qualification used a temporary
  loopback PostgreSQL 16.13 Homebrew cluster.
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
- Default regression after the 0.56 action-worker changes:
  the same non-optional command passed 2,810 tests, skipped 71 optional cases,
  and deselected 604 by marker in 5m38s. This run included the action-job tests
  and regenerable 0.52 evidence check. The cross-provider planning fixture now
  sends each connector only its declared configuration, preserving the
  local-files schema's fail-closed unknown-option behavior.
- Latest default regression after managed attempt/node lineage:
  the same non-optional command passed 2,823 tests, skipped 72 optional cases,
  and deselected 606 by marker in 8m56s. One regression failed because the
  source-linked 0.52 adaptive evidence was stale after these runtime changes.
  The 10 evidence artifacts were regenerated and verified across 18 acceptance
  criteria; the exact failing regression then passed on rerun in 26.03s. The
  run plus the exact rerun covers every selected test successfully.
- Managed headless/HTTP parity (AC056-001):
  `uv run pytest -q tests/fastapi/test_managed_application_0_56.py` — 18 passed.
  The parity case sends registration, edit, validation, planning and idempotent
  submission through both the public `ManagedApplicationService` and its HTTP
  adapter, then compares the semantic responses for definitions, plans, run
  status, allowed actions and event history. Pending report/lineage/artifact
  reads and missing-definition reads return matching status and error codes.
  The test exposed and fixed two headless response omissions: empty validation
  metadata and the run-action response schema identifier. No private imports or
  synthetic HTTP request are used.
- CP1 and CP-GA OpenAPI snapshots were refreshed for the managed rerun and
  replay endpoints; both stable-operation snapshot tests passed.
- Live PostgreSQL connector and multiprocess acceptance:
  `ETLANTIC_SQL_TEST_URL=... ETLANTIC_CP_TEST_URL=... uv run pytest -q tests/sql/test_postgresql_live_0_56.py tests/sqlmodel/test_durable_postgresql_multiprocess_0_56.py` — 4 passed.
- Final isolated PostgreSQL 16.14 qualification:
  `ETLANTIC_SQLMODEL_TEST_URL=... uv run pytest -q tests/sqlmodel/test_cp1_migrations_0_51.py`
  — 18 passed across SQLite and PostgreSQL schemas, including migration 009,
  concurrent SQLModel event sequencing, downgrade/re-upgrade, retained event
  history and retention tombstones. `ETLANTIC_SQL_TEST_URL=... uv run pytest -q
  tests/sql/test_postgresql_live_0_56.py` — 6 passed, covering append/upsert/
  replace, idempotent replay, bounded source/schema reads, permission denial,
  staged rollback, lost-ack reconciliation, PostgreSQL table aliases, and an
  actual managed source-to-same-table replace rejected before the target
  transaction while preserving the source row. `ETLANTIC_CP_TEST_URL=... uv run
  pytest -q tests/sqlmodel/test_durable_postgresql_multiprocess_0_56.py` — 2
  passed, covering eight-process single acceptance and quota idempotency plus
  restart reads. The disposable database ran PostgreSQL 16.14; it was isolated
  from application data.
- Managed connector overlap guard:
  `uv run pytest -q tests/connectors/test_resource_overlap_0_56.py` — 4 passed.
  The runtime rejects matching opaque source/target identities before opening a
  sink session, fails closed when same-provider identities are unavailable,
  permits proven disjoint resources, and does not serialize identity tokens in
  reports. PostgreSQL normalizes table aliases and adds the live server address
  to compare distinct endpoint aliases. The live PostgreSQL test exercised the
  guard through the standard managed runtime. AC056-033 remains pending for the
  full provider permission, key, schema, cleanup and pairing matrix.
- Clean installed-wheel smoke:
  rebuilt core, FastAPI and SQLModel 0.55.0 candidate wheels were installed
  into a fresh Python 3.14.3 virtual environment without workspace path
  injection. Migration 009 applied, idempotent event replay survived engine
  disposal/reopen, pruning rejected stale cursors and duplicate replay, the
  standard managed backend constructed and closed, and generated OpenAPI
  included `/v1/runs/{run_id}/events/history`. Exact wheel sizes and SHA-256
  values are recorded in `WHEEL_MANIFEST.json`. This is
  useful AC056-040 evidence; complete package/export/schema compatibility,
  version skew and upgrade/rollback qualification remain pending. The latest
  rebuilt core, FastAPI and SQLModel wheels also passed a fresh Python 3.14.3
  managed-backend smoke: after migration to head, a backend configured with a
  two-event scope limit retained sequences 2 and 3 from three published events.
- Overlap-guard wheel smoke: rebuilt core and `etlantic-sql` wheels installed
  into a separate Python 3.14.3 environment. Public imports for
  `ResourceIdentityConnector` and both live PostgreSQL connector identity
  resolvers passed without workspace path injection. The current wheel hashes
  and sizes are recorded in `WHEEL_MANIFEST.json`.
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
  written a second time. A one-shot SQLModel report-write failure after the
  sink commit was recovered as a successful report with a committed effect
  record and a `PMEXEC410` warning, without rerunning ETL. A second workspace
  could not read the scoped report.
- Managed directory-CSV parser and worker evidence, extended by the immutable
  upload qualification below:
  `uv run pytest -q tests/connectors/test_local_files_csv_0_56.py` — 20 passed;
  `uv run pytest -q tests/fastapi/test_managed_backend_0_56.py::test_standard_worker_reads_configured_csv_and_does_not_retain_row_content`
  — 1 passed; and
  `uv run pytest -q tests/runtime/test_local_runtime.py::test_packaged_worker_executes_accepted_envelope_and_recovers_report`
  — 1 passed. The connector pins declared encoding and delimiter choices,
  rejects unsupported settings, malformed quoting, decode errors, duplicate or
  mismatched row shapes, empty files and over-budget inputs, and checks each
  file's content digest before parsing. The standard managed worker executed a
  UTF-8 BOM/semicolon transfer, rejected a changed effective profile before
  writing, then succeeded with the accepted profile; row values were absent
  from its report. Core, FastAPI and SQLModel wheels installed into a fresh
  Python 3.14.3 environment without workspace path injection. The installed
  backend migrated to 009 and repeated the profile-drift check and managed CSV
  transfer successfully. The later migration-010 worker and PostgreSQL tests
  below complete the immutable-upload CSV matrix for AC056-035.
- Owner-scoped immutable CSV uploads and durable input leases (AC056-025/026;
  AC056-026 and AC056-035 passed):
  `uv run pytest -q tests/control_plane/test_input_resources_0_56.py
  tests/connectors/test_local_files_csv_0_56.py
  tests/fastapi/test_managed_backend_0_56.py::test_managed_worker_executes_finalized_upload_and_lease_outlives_staging_ttl
  tests/fastapi/test_managed_backend_0_56.py::test_managed_http_stages_finalizes_and_aborts_only_staged_input
  tests/fastapi/test_managed_backend_0_56.py::test_managed_worker_rejects_invalid_or_tampered_finalized_csv_uploads
  tests/sqlmodel/test_cp1_migrations_0_51.py` — the no-database run passed 50
  tests and skipped 5 PostgreSQL-only cases because
  `ETLANTIC_SQLMODEL_TEST_URL` was not configured. With the temporary local
  PostgreSQL URL configured, the combined suite below passed all cases with no
  skips. Migration
  010 adds bounded relational staging storage and scoped durable leases. HTTP
  staging streams up to the configured byte limit; finalization binds the
  uploaded CSV to an immutable SHA-256/version/length/tenant/workspace/owner
  reference. Managed planning checks the reference, acceptance acquires a
  retention lease, and the worker resolves it through the trusted resource
  store and verifies its scope and bytes before parsing. Tests cover restart,
  tampered blobs and references, cross-owner denial, forbidden extra locator
  fields and physical paths, unsupported media/formats, bounded orphan cleanup,
  lease protection, expiry, staged-only abort and execution after staging TTL.
  The real managed worker first rejected a run before runtime startup, then
  reused the finalized resource for a successful retry, rerun and replay. Four
  durable leases protected it after staging TTL; the worker parsed the UTF-8
  BOM/semicolon upload into typed rows and emitted a comma-delimited sink
  without placing row values in the report. The HTTP cleanup case also verifies
  permission denial, caller-owner scoping, one-item cleanup batches, stable
  remaining counts and idempotent empty cleanup. Real managed-worker cases
  finalized empty,
  malformed, byte-over-budget and same-length-tampered CSV uploads; each
  produced a failed run report without creating the sink, and the over-budget
  case used a deliberately lower worker connector limit. A rebuilt clean-wheel
  smoke on Python 3.14.3 applied
  migration 010, constructed the standard backend, exposed the upload route in
  OpenAPI, finalized an upload, read it after backend restart under a durable
  lease, denied a cross-owner read and rejected same-length blob tampering.
  PostgreSQL concurrent lease/cleanup qualification passed six multi-process
  trials. Together, the bounded owner-scoped HTTP cleanup, accepted/retry/
  rerun/replay lease coverage, live-lease cleanup checks and race qualification
  complete AC056-026 locally. The broader worker threat and provider security
  campaign remains open for AC056-025.
- PostgreSQL input-resource acquisition/cleanup race:
  `ETLANTIC_SQLMODEL_TEST_URL=... uv run pytest -q
  tests/sqlmodel/test_input_resource_postgresql_0_56.py` — 1 passed. Six
  independent-process trials include forced lease-first and cleanup-first
  orderings plus four simultaneous races. A committed lease always preserved
  readable bytes through the cleanup horizon; cleanup winning first made the
  later lease fail with a stable 404. The temporary PostgreSQL 16.13 cluster
  listened only on loopback.
- Combined immutable-input, CSV, worker and migration qualification with the
  temporary PostgreSQL URL set — 56 passed, no skips. The migration module
  passed 19 SQLite/PostgreSQL cases through migration 010; no database URL is
  written to this evidence record.
- Versioned report-table and event-retention migration:
  `uv run pytest -q tests/sqlmodel/test_cp1_migrations_0_51.py`
  — the latest PostgreSQL-backed rerun passed 19 SQLite and PostgreSQL cases,
  covering fresh install, upgrade from each prior head, restart, downgrade and
  re-upgrade while preserving CP1 event history through migration 010.
- Idempotent lifecycle-event storage and migration:
  `uv run pytest -q tests/control_plane/test_control_plane.py::test_memory_event_store_append_once_is_scoped_and_conflict_checked tests/sqlmodel/test_control_plane_stores.py::test_sqlite_event_append_once_survives_restart_and_rejects_conflicts tests/sqlmodel/test_cp1_migrations_0_51.py::test_idempotent_event_migration_round_trip_preserves_event_history`
  — 3 passed. Migration 008 adds a separate scoped event-key table, and
  migration 009 adds digest-only tombstones without rewriting CP1 event rows.
  SQLite restart returns the original unpruned event for the same key and
  rejects changed content. The memory store now keeps only the key digest,
  payload digest and cursor for an idempotency tombstone, not a second event
  payload copy.
- Managed lifecycle events and paginated event history:
  `uv run pytest -q tests/fastapi/test_managed_backend_0_56.py::test_standard_backend_worker_persists_queryable_report_in_sqlmodel tests/fastapi/test_cp1_sse.py tests/fastapi/test_managed_application_0_56.py::test_headless_run_event_pages_are_scoped_and_resumable tests/fastapi/test_cp1_full_authz_matrix.py tests/fastapi/test_cp1_openapi.py`
  — 62 passed in the latest focused run (the final worker integration and all
  event-history/authz/OpenAPI tests were included). Lifecycle delivery uses
  stable per-attempt keys and persists one start/completion pair across report
  recovery. Headless and HTTP page queries return the same scoped events;
  reconnect cursors advance through the workspace log, with explicit empty-page
  behavior when other runs' events are interleaved. Unknown and pruned scoped
  cursors return 410. A pruned lifecycle key cannot recreate its event; changed
  content conflicts. Managed retention now applies a configurable per-scope
  event count on append and history reads (default 100,000), preserves sequence
  continuity, and leaves digest tombstones intact. The focused memory, SQLModel
  and managed-backend retention suite passed 36 tests, including policy
  validation, scope isolation, stale-cursor 410, restart and retry behavior.
  The configured automatic-retention path also passed against isolated
  PostgreSQL 16.14: history stayed within two events per scope, expired cursors
  and retries returned 410, and sequence allocation continued after pruning.
  AC056-019 remains pending for bounded tombstone expiry, result/artifact
  retention and the full reconnect and cross-scope isolation campaign.
- Durable run-artifact content (AC056-017/019 subrequirement): the managed
  worker writes only explicitly durable JSON outputs into hashed per-run
  directories. Artifact listings report content availability; HTTP and
  headless reads require `run.artifact.content` at both the run and artifact
  resource, and reads use the bounded `SafeIoPolicy`. The focused application
  and standard SQLModel backend tests cover denied discovery, per-artifact
  denial, download headers, and retrieval after reopening the service. The
  combined run of the managed application/backend, CP1 authorization matrices,
  and CP1/CP-GA OpenAPI tests passed 98 cases. Result-retention remains open.
- Attempt and execution-node lineage (AC056-017 subrequirement):
  `uv run pytest -q tests/fastapi/test_managed_application_0_56.py
  tests/fastapi/test_managed_backend_0_56.py
  tests/fastapi/test_cp1_full_authz_matrix.py` — 89 passed. Lineage queries now
  return stable run-to-attempt and attempt-to-executed-node edges, including
  attempt roles. If a worker dies after report publication and the durable
  completion acknowledgment is recovered after restart, the report and lineage
  retain both the original executing attempt and the result-reconciliation
  attempt. Partition identities are not emitted because the current worker
  report has no partition execution records; partition links and result
  retention remain open.
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
- Independent provider install and managed execution (AC056-037):
  `uv run python scripts/qualify_private_provider_0_56.py` — passed. The
  qualification separately built the core and `etlantic-private-ac056037`
  wheels, installed both into a fresh Python 3.11.15 environment, and ran the
  consumer under isolated Python with workspace import paths removed. A
  production profile authorized the private distribution by exact version;
  its entry point supplied the catalog schema, its native dataset reference and
  projection option survived definition authoring, plan generation and the
  durable execution envelope, and the standard managed worker discovered the
  installed provider and wrote the expected row to CSV. No application-side
  provider registration or ETL loop was used. Wheel digests and the completed
  consumer receipt are recorded in
  [`PRIVATE_PROVIDER_QUALIFICATION.json`](PRIVATE_PROVIDER_QUALIFICATION.json).
  The end-to-end submission exposed first-party plan metadata keys rejected by
  strict production decoding; `selected`, `sliced`, `sql_schema_mutations` and
  `sql_transaction_scopes` are now recognized as core metadata and covered by
  a production plan round-trip regression.
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
- Isolated connector action jobs (AC056-020 implementation evidence):
  `uv run pytest -q tests/control_plane/test_action_jobs_0_56.py
  tests/fastapi/test_managed_action_jobs_0_56.py` — 16 passed. The tests exercise
  closed secret-free requests, durable/idempotent acceptance, SQLModel restart,
  HTTP submission and owner-scoped pagination, action and object authorization
  rechecks before provider calls, lease fencing, deadline cancellation,
  provider-error redaction, nested result bounds and separate worker execution.
  The built-in catalog handler returned the profile-authorized page; registered
  async handlers executed test, schema-inspection and preflight payloads. The
  combined managed-service, authorization and OpenAPI regression passed 96
  tests. Live PostgreSQL 16.13 multiprocess qualification of the CP3 action
  store passed 3 tests: concurrent acceptance returned one receipt, competing
  workers produced one fenced claim, the accepted receipt survived reopening,
  and a different owner received an opaque 404. `ActionExecutionHost` and
  `ActionHandler` are available through `etlantic.runtime`; the handler and
  worker contract is documented in
  [`ACTION_WORKERS_0_56.md`](../../ACTION_WORKERS_0_56.md). This is generic
  action-worker evidence; provider-specific live test/schema/preflight
  integrations remain open, so AC056-020 is still pending.
- Bounded preview and explicit provisioning action contracts (AC056-021/022):
  The same 16-test action suite exercises preview requests containing only
  opaque provider, connection and resource references, bounded row/byte limits
  and redaction fields; inline credential fields are rejected. The separate
  action host applies its own caps, requires declared columns, redacts
  sensitive columns and caller-selected values, and marks truncation. Preview
  result TTL is configurable; SQLite-backed SQLModel qualification cleared the
  expired payload, preserved the successful receipt and expiry timestamp, and
  recovered that state after backend restart. Provisioning uses a separate
  permission, returns the same action receipt on an idempotent retry, forces
  create-only/if-exists-fail behavior, and validates a backend-derived schema
  fingerprint and matching effect receipt. Cleanup is a separately authorized
  command tied to a successful same-owner parent action; mismatched and foreign
  parents fail before provider IO. A mock effect store exercised create and
  compensation, while schema inspection was tested without target mutation.
  Provider-specific credential resolution and create/cleanup integrations are
  deployment-owned and were not qualified here, so AC056-021/022 remain
  pending.
- Candidate wheel build and isolated action-worker smoke (AC056-020 / 040):
  `uv build --all-packages --wheel` built all 25 workspace distributions.
  Their exact candidate wheel sizes and SHA-256 digests are recorded in
  `WHEEL_MANIFEST.json`. Core, FastAPI and SQLModel candidate wheels were
  installed in a clean Python 3.14.3 environment without workspace path
  injection. That install applied SQLModel migration 010, imported the public
  action execution exports, accepted a durable action through the managed
  service, executed it in a separate worker, and returned a redacted scoped
  receipt. It also exercised first-write SQLModel quota admission and read back
  the single persisted concurrency charge. This is package-install evidence;
  AC056-040's full compatibility,
  version-skew and upgrade/rollback matrix remains pending.
- Rebuilt candidate wheels after the AC056-001 service response fixes:
  `uv build --all-packages --wheel --out-dir /tmp/etlantic-phase056-wheels-ac001`
  built all 25 workspace wheels. The rebuilt core, FastAPI and SQLModel wheels
  installed into a fresh Python 3.14.3 environment without workspace path
  injection. The installed service and HTTP adapter returned matching
  validation, action-discovery and event-history results; idempotent submit
  recovered the same receipt. Migration 010 and the public action-worker
  exports passed. Updated wheel hashes are in `WHEEL_MANIFEST.json`.
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
  revision registry while retaining the CP1 rows. AC056-007 remains open for
  durable resource/version resolution and full scope disclosure coverage.
- PostgreSQL managed-service idempotency, quota and failure recovery:
  `ETLANTIC_CP_TEST_URL=... ETLANTIC_SQLMODEL_TEST_URL=... uv run pytest -q
  tests/sqlmodel tests/fastapi/test_managed_postgresql_process_0_56.py` — 63
  passed, with one SQLModel test warning. Eight independent processes submitted
  the same pinned run through separate managed-service instances; all received
  one receipt, the durable outbox held one command, the persisted concurrency
  quota was charged once, and a reopened service recovered that receipt. A
  second eight-process race used two different request intents under the same
  idempotency key; four callers recovered the winning receipt and four received
  a conflict. This exercised a real first-use race in the PostgreSQL CP4 quota
  snapshot: concurrent transactions both tried to create its unique row. The
  SQLModel store now seeds a version-zero row inside a savepoint so the loser
  can roll back the uniqueness conflict and lock the committed snapshot. The
  PostgreSQL quota test no longer pre-creates the row. A separate process
  committed durable acceptance and then simulated a lost acknowledgement; the
  caller's retry recovered the original submission and single outbox record.
  AC056-008 is passed. AC056-010 remains pending because the lost-ack case
  covers durable acceptance only, not every CP1/CP3/outbox and worker failure
  boundary.
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
  SQLModel wheel applied migration `009_event_retention_tombstones_0_56`; its
  event store returned the original event after engine disposal/reopen, expired
  a pruned cursor and refused to recreate its keyed event. The installed FastAPI
  wheel constructed and closed the standard SQLModel backend, and its generated
  OpenAPI included the bounded run-event history endpoint.
- Candidate wheel smoke for preview and provisioning (AC056-021/022):
  `uv build --all-packages --wheel --out-dir
  /tmp/etlantic-phase056-actions-final` built all 25 distributions. Core, FastAPI and
  SQLModel wheels were installed in a fresh Python 3.14.3 environment without
  workspace path injection. Migration 010 applied; the installed backend
  executed a redacted preview, cleared its expired result while retaining its
  receipt, then accepted a create-only provision action and a parent-linked
  cleanup action. The provider-neutral mock effect was removed and both
  durable receipts remained queryable.
- Public CLI: sample pipeline validation passed with no diagnostics; plan
  generation returned fingerprint
  `8f3879b301b3b0ea1b87434eef3dd0a58ef0cbe8342ced056323cc9d6d5b19da`.
- Plugin manifests: 16 packages passed.
- Final `scripts/check_adaptive_0_52.py --write` refreshed and verified 10
  artifacts across 18 prior-phase acceptance criteria; its exact CI regression
  test passed afterward.
- `scripts/check_pyright.sh` passed: 781 suppressions matched the locked
  inventory, the strict shadow scan matched its reviewed 10,432-diagnostic
  baseline, and raw Pyright reported zero errors and warnings. No suppressions
  were added. Typing the plan fixture helper removed 19 pre-existing unknown-
  type diagnostics, and the independent consumer imports public owning modules;
  the shadow scan found no new diagnostics.
- `ruff check .`, `git diff --check`, plugin-manifest checks and `uv lock --check`
  passed.

## Open release requirements

- AC056-002, AC056-004, AC056-009–019 and AC056-033: the managed application,
  authorization, specification, admission, worker, result and PostgreSQL
  provider paths have implementation and focused tests, but their full
  criterion-level failure, concurrency and runtime campaigns remain open.
- AC056-017–018: the standard SQLModel backend now persists runtime reports in
  a tenant/workspace-scoped table, and worker recovery reuses a report committed
  before attempt acknowledgment. Explicitly durable JSON artifacts have
  separately authorized bounded HTTP/headless downloads and restart coverage.
  Run-level start/completion events have idempotent scoped persistence, and
  bounded headless and HTTP event history reads share authorization and scoped
  cursor semantics. A transient report-write failure after an external sink
  commit now recovers the durable terminal report without rerunning ETL;
  persistent report-store outage recovery, result retention, and separate
  result and cleanup state machines remain unqualified. Run lineage now links
  reports to executed nodes and records worker result-reconciliation attempts;
  partition results remain unmodeled.
- AC056-007: immutable revision pinning, resource authorization and
  effective-fingerprint policy binding have focused evidence. Complete durable
  resource/version resolution and full disclosure coverage remain open.
- AC056-008 passed with concurrent managed-service retries and changed-intent
  conflict against PostgreSQL 16.13, persisted quota idempotency, restart reads
  and lost-ack receipt recovery. AC056-010 remains open for its full boundary
  fault matrix.
- AC056-039 and AC056-042: PostgreSQL 16.14 migration evidence and PostgreSQL
  16.13 multi-process managed acceptance/quota/restart tests now pass. AC056-042
  is qualified for the tested 0.55 migration chain and legacy incomplete-payload
  guard. AC056-039 remains open for backup/restore and broader failure campaigns.
- AC056-020: durable isolated action jobs, authorization rechecks, bounded
  receipts, a built-in catalog action, and a deployment handler contract now
  have focused evidence. Provider-specific live connection, schema and
  preflight integrations plus the full provider cancellation matrix remain
  open, so this criterion stays pending. AC056-021–022 now have bounded
  preview and explicit create/cleanup contracts with mock-worker evidence;
  provider credential resolution and provider-specific effect qualification
  remain open. AC056-023–024 retain their open resource-isolation and complete
  secret lease/rotation lifecycle requirements.
  AC056-025 has immutable upload, durable lease, bounded cleanup and PostgreSQL
  multiprocess race evidence, but its full worker threat and provider security
  campaign remain open. AC056-026 passed its owner-scoped cleanup,
  accepted/retry/rerun/replay retention and PostgreSQL race case.
- AC056-035 passed its typed CSV, encoding, malformed/empty/over-budget and
  tamper-rejection worker cases plus resource-retention checks; see the selected PostgreSQL-backed suite above.
- AC056-027–029 and AC056-031–032: scheduler admission parity,
  checkpoint-resume/repair/backfill, qualified pause/amendment and complete
  lifecycle qualification remain open. Idempotent rerun and full-snapshot
  replay commands now share the managed worker path.
- AC056-034 and AC056-036: no isolated live Foundry account is configured.
  The required two independent Foundry scopes and all 12 real-worker pairings
  have not been exercised; mock transport tests do not qualify them.
- AC056-038–041 and AC056-043–044: full disclosure campaign, PostgreSQL
  backup/restore/failure, version-skew/rollback,
  complete advanced engine matrix, managed adaptive `/2`, and generic consumer
  evidence remain open. AC056-040 has clean Python 3.14.3 wheel-build/install,
  migration-008, backend-construction and OpenAPI smoke evidence; its complete
  compatibility, version-skew, migration rollback and package matrix remains
  open.

See [`RELEASE_INDEX.json`](RELEASE_INDEX.json) for the per-criterion status,
case references, provider tuple and open reason. These limitations keep the
0.56 release decision open even though the implemented local gates pass.
