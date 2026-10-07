---
status: experimental
---

# Phase 0.56 Local Qualification

**Decision: all 44 acceptance criteria are qualified; release review remains open.** This record reports local implementation evidence; it does not claim publication.

Current index: 44 criteria passed, 0 open, 0 pending, and 0 blocked.

## Candidate environment

- Date: 2026-10-02
- Host: macOS 25.5.0, arm64
- Python: 3.11.15
- Live databases: earlier isolated PostgreSQL 16.14 container evidence; the
  current input-resource race and migration qualification used a temporary
  loopback PostgreSQL 16.13 Homebrew cluster.
- Workspace base: `e7fd6b866dbecab646cf68b73405ee06ea4437e5`
- Candidate packages: core and companions build as 0.56.0 in lockstep. This is an unpublished qualification candidate against the published 0.55.x compatibility baseline.

## Requalification against the current candidate tree

- Date: 2026-10-06. Source candidate: `bbdd4a27` before this evidence refresh.
- The full default non-optional regression command above was rerun against the
  current source tree: 3,260 passed, 120 skipped, and 739 deselected in 8m10s.
  This covers the current managed admission, runtime recovery, input lease
  ordering, profile boundary, and compatibility-reader changes.
- SQLModel local-store regression:
  `uv run pytest -q tests/sqlmodel/test_control_plane_stores.py
  tests/sqlmodel/test_durable_work_0_41.py
  tests/sqlmodel/test_input_resource_postgresql_0_56.py` — 25 passed, 1
  skipped because the live PostgreSQL lease/cleanup race requires a database
  URL. That race was then rerun against an isolated temporary PostgreSQL 16.13
  cluster:
  `ETLANTIC_SQLMODEL_TEST_URL=postgresql+psycopg://... uv run pytest -q
  tests/sqlmodel/test_input_resource_postgresql_0_56.py` — 1 passed. The test
  covers six multiprocess lease-versus-cleanup trials, including both forced
  orderings and simultaneous races. The temporary cluster was removed after
  the run.
- `git diff --check` and `uv run python scripts/check_docs.py` passed after the evidence refresh.

The release index candidate hash and qualification artifact checksums were
refreshed after these results. All 44 criteria are qualified; the release
decision remains open pending the separate final release review.

## Foundry bounded-batch requalification (2026-10-06)

Requalified the current implementation at source revision `20e71c32` after
Foundry source reads changed to emit bounded batches. The simulator suite
`uv run pytest -q tests/foundry/test_simulator.py
tests/foundry/test_connectors_0_56.py
tests/connectors/test_resource_overlap_0_56.py` passed 42 tests across two
independent loopback scopes. The managed provider matrix
`ETLANTIC_SQL_TEST_URL=postgresql+psycopg://postgres@127.0.0.1:55439/postgres
ETLANTIC_PHASE056_MATRIX_EVIDENCE=<temporary path> uv run pytest -q
tests/fastapi/test_managed_provider_matrix_0_56.py` passed all 20 source /
destination pairing and mode cases against a disposable PostgreSQL 16.13
cluster and two Semblance 0.9.0 scopes. The matrix artifact was regenerated
from this run; the temporary database cluster was stopped and removed.

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
- CP1 and CP-GA OpenAPI snapshots were refreshed for the managed rerun, replay
  and checkpoint-resume endpoints; both stable-operation snapshot tests passed.
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
- PostgreSQL provider and overlap acceptance (AC056-033):
  `ETLANTIC_SQL_TEST_URL=postgresql+psycopg://postgres@127.0.0.1:64986/postgres
  uv run pytest -q tests/sql/test_postgresql_live_0_56.py
  tests/connectors/test_resource_overlap_0_56.py` — 10 passed. This run covered
  append/upsert/replace, keys, bounded schema inspection, permission denial,
  staged rollback, lost-ack reconciliation, canonical table aliases, managed
  same-table overlap rejection, fail-closed unknown identities, and disjoint
  resource acceptance against isolated PostgreSQL 16.14.
- Semblance-backed Foundry API simulator (AC056-034):
  `uv run pytest -q tests/foundry/test_simulator.py
  tests/foundry/test_connectors_0_56.py
  tests/connectors/test_resource_overlap_0_56.py` — 26 passed. Two independent
  loopback simulator scopes used separate dataset RIDs, pinned transactions,
  namespaces, bearer tokens and seed data. Both scopes passed append, replace
  and snapshot writes; a lost commit acknowledgement independently reconciled
  to committed in each scope. Managed execution rejected a same-file
  source/replace overlap before opening a sink transaction in both scopes. The
  suite verified pinned reads, branch/file
  isolation, wrong-dataset 404, cross-scope-token 401, redaction, and opaque
  source/sink identity equality for the same file with different identities for
  another branch or dataset. `SIMULATOR_QUALIFICATION_0_56.json` records the
  Semblance version and simulator matrix without recording credential values.
  AC056-034 is qualified without a live Foundry account.
- Managed connector overlap guard:
  `uv run pytest -q tests/connectors/test_resource_overlap_0_56.py` — 4 passed.
  The runtime rejects matching opaque source/target identities before opening a
  sink session, fails closed when same-provider identities are unavailable,
  permits proven disjoint resources, and does not serialize identity tokens in
  reports. PostgreSQL normalizes table aliases and adds the live server address
  to compare distinct endpoint aliases. The live PostgreSQL test exercised the
  guard through the standard managed runtime and is included in the passing
  AC056-033 evidence above. The source/destination pairing matrix is tracked
  separately by AC056-036.
- Managed-worker provider matrix (AC056-036):
  `ETLANTIC_SQL_TEST_URL=postgresql+psycopg://... uv run pytest -q
  tests/fastapi/test_managed_provider_matrix_0_56.py` — 20 passed against
  PostgreSQL 16.13 (Homebrew) and two simultaneously running, independently
  configured Semblance 0.9.0 loopback scopes. The matrix covers all 12 source /
  destination pairings among Foundry A, Foundry B, PostgreSQL and finalized
  immutable CSV uploads, with append, upsert and replace PostgreSQL modes (20
  pairing/mode cases total). Every case accepted and completed a real managed
  worker transfer, recorded its provider effect receipt, then accepted a
  second run with a post-acceptance source failure. The failure produced a
  stable provider diagnostic and left the previously committed destination
  unchanged. The checked-in `MANAGED_PROVIDER_MATRIX_0_56.json` captures exact
  non-secret dataset, transaction, upload, table and effect identities, package
  and server versions, status/diagnostic codes, and output digests. It contains
  neither credentials nor row contents. AC056-034's two-scope overlap,
  cross-scope credential denial, pinned-read isolation and lost-ack recovery
  tests provide the associated provider security and reconciliation evidence.
- Clean installed-wheel smoke:
  rebuilt core, FastAPI and SQLModel 0.56.0 candidate wheels were installed
  into a fresh Python 3.14.3 virtual environment without workspace path
  injection. Migration 009 applied, idempotent event replay survived engine
  disposal/reopen, pruning rejected stale cursors and duplicate replay, the
  standard managed backend constructed and closed, and generated OpenAPI
  included `/v1/runs/{run_id}/events/history`. Exact wheel sizes and SHA-256
  values are recorded in `WHEEL_MANIFEST.json`. This contributes to AC056-040 alongside the final isolated-wheel
  export/schema, version-skew, and migration rollback qualification recorded in
  `PACKAGE_COMPATIBILITY_0_56.json`. The latest
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
- Managed authorization and disclosure parity (AC056-002):
  `uv run pytest -q tests/fastapi/test_phase_0_56_authorization_order.py
  tests/fastapi/test_cp1_full_authz_matrix.py tests/fastapi/test_cp1_authz_matrix.py
  tests/fastapi/test_managed_application_0_56.py
  tests/control_plane/test_control_plane.py` — 103 passed. The generated
  authorization-order campaign exercised all 89 protected operations among
  the 91 public CP OpenAPI operations. It recorded authorization and configured
  store-call order, verified denied definition requests do not read/write the
  definition repository, and checked that the CP1 run existence probe occurs
  only after authorization. Explicit `not_found` and `forbidden` decisions on
  seeded runs returned matching status/code pairs through the headless managed
  service and HTTP adapter under concurrent calls, with no existence probe.
  Existing cross-tenant and cross-workspace service cases were combined with
  owner, tenant and workspace input-resource attacks; each foreign caller was
  authorized for the operation, yet headless-store and HTTP adapter outcomes
  matched as opaque 404s, and the upload remained intact for its owner. The
  dynamic campaign also exposed and fixed register/edit routes that returned
  501 before authorization when managed services were not configured.
- Resolved-plan admission and revision/resource binding (AC056-007):
  `uv run pytest -q tests/fastapi/test_managed_application_0_56.py
  tests/fastapi/test_managed_backend_0_56.py::test_managed_worker_executes_finalized_upload_and_lease_outlives_staging_ttl`
  — 21 passed. Submission resolves and pins the definition revision before
  computing the verified plan and effective fingerprint; the policy decision
  records that exact effective fingerprint and revision. The approval test
  proves a matching reviewer-approved decision admits the run, while the same
  approval cannot authorize a changed revision. Forged caller plan hashes and
  unknown revisions are rejected before durable acceptance. Resolved resources
  are authorized before acceptance, and an immutable finalized input's exact
  version is included in the durable execution envelope and protected by its
  owner-scoped lease. The test also confirms revision alias changes after an
  accepted retry do not change the original resolved revision. Combined with
  AC056-002's tenant/workspace/owner campaign, this closes the cross-scope
  authorization dependency for this criterion.
- CP public control and field coverage (AC056-004):
  `uv run python scripts/check_phase_0_56_control_coverage.py --write` reported
  96 operations and 978 parameter/schema fields mapped. The generated inventory
  records each CP OpenAPI operation, path/query parameter, and request/response
  schema field against its storage authority and runtime consumer, or records
  the explicit reason a control has no ETL runtime effect. The check verifies
  all referenced source anchors and evidence modules. The focused qualification
  `uv run pytest -q tests/fastapi/test_phase_0_56_control_coverage.py` passed 5
  tests, including mutations proving an omitted operation, downgraded control,
  or removed public field fails the gate, and checking that managed schedule
  revision/workload/reference policy appears in OpenAPI. The inventory is
  `PUBLIC_CONTROL_COVERAGE_0_56.json`.
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
  Explicit tombstone-prune calls now share a 1,000-row maximum and reject
  non-integer or out-of-range batch sizes. With the isolated PostgreSQL 16.13
  URL set, the focused PostgreSQL cursor-retention, per-scope policy and
  bounded tombstone-prune tests passed alongside the full memory/SQLite
  idempotency-retention suite. A new PostgreSQL case verified bounded pruning,
  retries after expiry, sequence continuity, scope isolation and restart
  durability. Owner-scope tests compared headless and HTTP status, event,
  report, artifact-list and artifact-content denials; a foreign owner could not
  read a private event marker and denial happened before report-store access.
  Existing SSE reconnect/Last-Event-ID, duplicate suppression, cursor-gap,
  pagination and durable artifact-content authorization cases also passed.
- Durable run-artifact content (AC056-017/019 subrequirement): the managed
  worker writes only explicitly durable JSON outputs into hashed per-run
  directories. Artifact listings report content availability; HTTP and
  headless reads require `run.artifact.content` at both the run and artifact
  resource, and reads use the bounded `SafeIoPolicy`. The focused application
  and standard SQLModel backend tests cover denied discovery, per-artifact
  denial, download headers, and retrieval after reopening the service. The
  combined run of the managed application/backend, CP1 authorization matrices,
  and CP1/CP-GA OpenAPI tests passed 98 cases. Broader result-publication and
  cleanup-failure recovery remains tracked under AC056-018; AC056-019's event
  and artifact authorization cases are now qualified.
- Attempt and execution-node lineage (AC056-017 subrequirement):
  `uv run pytest -q tests/fastapi/test_managed_application_0_56.py
  tests/fastapi/test_managed_backend_0_56.py
  tests/fastapi/test_cp1_full_authz_matrix.py` — 89 passed. Lineage queries now
  return stable run-to-attempt and attempt-to-executed-node edges, including
  attempt roles. If a worker dies after report publication and the durable
  completion acknowledgment is recovered after restart, the report and lineage
  retain both the original executing attempt and the result-reconciliation
  attempt. The worker does not yet emit sink/output partition execution
  records. Runtime reports now link source
  nodes to bounded, run-scoped opaque IDs for partitions actually observed
  during completeness checks; the summary includes key names and counts without
  serializing partition values. Sink/output partition result records and the
  result-retention campaign remain open, and this code has not had a focused
  regression run.
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
  [`ACTION_WORKERS_0_56.md`](../../ACTION_WORKERS_0_56.md). The Foundry
  package now exposes saved-connection action handlers. Its worker integration
  test passed connection testing, one-field schema inspection, and deployment
  preflight against the Semblance loopback API. Receipts omit the token and
  dataset/file metadata, and simulator state confirms the handlers performed
  no transaction or upload. Receipt reads, lists, idempotency, and
  provision-parent verification also enforce environment and security-domain
  scope in addition to tenant, workspace, and owner. New pagination cursors
  carry that same scope; legacy cursors query only the current scoped receipt
  set. The focused action suite passed 25 tests, covering worker deadline
  cancellation, authorization rechecks, redaction, bounded results,
  scope-bound receipts and the provider handler path without a live Foundry
  account. AC056-020 is qualified.
  Receipt environment/security-domain scope and cursor binding were also
  qualified through headless and HTTP adapters.
- Bounded preview and explicit provisioning action contracts (AC056-021/022):
  The same 16-test action suite exercises preview requests containing only
  opaque provider, connection and resource references, bounded row/byte limits
  and redaction fields; inline credential fields are rejected. The separate
  action host applies its own caps, requires declared columns, redacts
  sensitive columns and caller-selected values, and marks truncation. Preview
  result TTL is configurable and constrained to 60–86,400 seconds at the
  managed-config, action-host, and durable-store boundaries; SQLite-backed
  SQLModel qualification cleared the expired payload, preserved the successful
  receipt and expiry timestamp, and recovered that state after backend restart.
  The store rejects retention for failed and timed-out jobs. The Foundry
  package now optionally accepts a trusted preview-resource resolver and reads
  exactly one pinned CSV file through the public source connector. The handler
  constrains the announced/downloaded file size before reading, returns no more
  than the requested row count, marks truncation, and applies provider-marked
  sensitive-column and caller-selected redaction in the action worker. The
  local action integration and oversized-file rejection ran against Semblance.
  The combined Foundry/action/SQLModel action regression passed 42 tests,
  including preview expiry, restart recovery, unsuccessful-result expiry,
  credential isolation, row/byte bounds and truncation. AC056-021 is qualified.
  Provisioning uses a separate permission, returns the same action receipt on
  an idempotent retry, forces create-only/if-exists-fail behavior, and validates
  a backend-derived schema fingerprint and matching effect receipt. The schema
  parser rejects nullable primary-key columns before provider I/O. A SQLAlchemy
  provider handler creates PostgreSQL tables only when absent, records the
  trusted scope/action/effect/schema binding transactionally, recovers a
  provider commit after lost receipt publication, and refuses a second action
  from replacing the target. Cleanup is separately authorized and tied to the
  successful same-owner parent; its tombstone makes compensation retry-safe.
  The SQLite-backed action test plus isolated PostgreSQL 16.13 loopback run
  passed 3 tests. The PostgreSQL case created a unique table through the action
  worker, recovered the same receipt on retry, inspected its schema through the
  public storage connector without changing the database table set, and
  compensated the exact effect. The Foundry simulator worker separately
  confirms ordinary schema inspection performs no transaction or upload.
  AC056-022 is qualified.
- Candidate wheel build and isolated action-worker smoke (AC056-020 / 040):
  `uv build --all-packages --wheel` built all 25 workspace distributions.
  Their exact candidate wheel sizes and SHA-256 digests are recorded in
  `WHEEL_MANIFEST.json`. Core, FastAPI and SQLModel candidate wheels were
  installed in a clean Python 3.14.3 environment without workspace path
  injection. That install applied SQLModel migration 010, imported the public
  action execution exports, accepted a durable action through the managed
  service, executed it in a separate worker, and returned a redacted scoped
  receipt. It also exercised first-write SQLModel quota admission and read back
  the single persisted concurrency charge. This is package-install evidence.
  AC056-040's full package/export compatibility and version-skew matrix remain
  pending. A seven-head SQLite rollback/re-upgrade matrix now verifies that
  definitions, accepted submission identity and event history survive each
  supported rollback boundary.
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
  — 69 passed. A packaged worker performed both accepted child transfers from
  the immutable parent snapshot, and tests cover explicit rerun after a
  committed effect, full-snapshot replay intent, unknown-effect rejection,
  idempotency, action discovery and OpenAPI registration. At the earlier
  qualification checkpoint, resume was blocked by the missing runtime restore
  path; the current implementation and qualification are recorded in the
  AC056-031 sections below.
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
  AC056-008 is passed. The expanded AC056-010 CP1/CP3/outbox boundary campaign
  is recorded in the completed criterion summary below.
- Durable managed preparation operations (AC056-009):
  `uv run pytest -q tests/control_plane/test_action_jobs_0_56.py
  tests/fastapi/test_managed_application_0_56.py
  tests/fastapi/test_managed_action_jobs_0_56.py
  tests/sqlmodel/test_preparation_operation_recovery_0_56.py
  tests/fastapi/test_phase_0_56_control_coverage.py
  tests/fastapi/test_phase_0_56_authorization_order.py
  tests/fastapi/test_cp1_openapi.py
  tests/fastapi/test_cp_ga_openapi_0_43.py` — 66 passed. The SQLModel-backed
  managed API persisted preparation by operation ID; after the backend was
  closed with a claimed operation and its lease expired, a newly constructed
  backend queried the same operation, took over with a new fence and completed
  one managed submission and outbox command. Replaying the idempotency key
  returned the same operation. The SQL-backed route also canceled a queued
  operation; the managed memory integration exercised in-flight cancellation
  before acceptance and verified no run submission or outbox command was
  created. A 1.5-second preparation under a one-second worker lease renewed its
  lease, preventing a competing worker from claiming it. Secret-like request
  content was rejected before persistence and did not appear in the stored
  operation. The API authorization-order and OpenAPI coverage suites include
  the operation query, cancel and start routes.
- Worker leases, cancellation, fencing and resource budgets (AC056-013):
  the targeted worker/resource campaign passed 86 tests across schedule loops,
  CP3 fencing, SQLModel lease recovery, preparation workers, managed execution,
  local/adaptive concurrency, bounded storage materialization, local-file
  limits, DuckDB memory configuration and backend TTL validation. The broader
  runtime/resource regression passed 329 tests with 3 optional skips across
  local and adaptive orchestration, DuckDB, Parquet, inference budgets,
  managed cancellation/timeouts, preparation deadline handling and scheduler
  recovery. A long-running run renewed its lease before a competing worker
  could claim it; running cancellation stopped the managed runtime before its
  sink write, and stale fencing tokens could not update state. Row, byte and
  time checks rejected over-budget materialization; profile concurrency capped
  local parallel work; a DuckDB session reported its configured 16 MiB limit,
  and malformed memory limits failed before session publication. Worker,
  scheduler and action-worker constructors rejected boolean, nonpositive,
  floating-point and missing TTLs; the managed action lease must exceed the
  maximum preparation deadline. Preparation deadlines now finish as
  `timed_out` after a cooperative checkpoint rather than a generic failure.
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
  envelopes. The managed input-resource path now records its deterministic
  durable lease ID in accepted and lifecycle-command envelopes; the lease ID
  now binds principal issuer/kind/subject and environment along with its
  existing domain, tenant, workspace, owner, operation, and idempotency key.
  This prevents same-owner requests in separate environments or principal
  identities from sharing a lease. Lifecycle-command idempotency recovery
  still accepts an already stored legacy lease identity without rewriting the
  accepted envelope. Standard workers require lease-authorized
  reads; the memory and SQLModel stores check the exact finalized owner-bound
  reference, tenant/workspace scope, active lease, and content digest while
  allowing a different worker owner identity. At the time of this initial
  implementation run, the scope change and action executors still needed
  focused qualification; the completed campaign is recorded below.
- Secret version selection and audit:
  `uv run pytest -q tests/secrets/test_secrets.py tests/runtime/test_bugfixes.py`
  — 24 passed. Environment and mounted-file providers reject unsupported
  version selectors; managed resolution rejects an unsupported or mismatched
  exact version and records a versioned provider's resolved version in the
  security event without the value. Managed resolution now also rejects a
  provider result whose provider/name/key differs from the requested
  reference, before it reaches a binding. This code change has not received a
  focused regression run. Secret-cache invalidation now clears the matching
  reference across trusted-scope partitions, and a zero-second TTL expires
  immediately rather than falling back to the default. The cache also rejects
  non-finite or negative TTLs and non-positive entry limits, including mutated
  limits at insertion; zero TTL removes any prior entry without caching the
  new value. These cache changes have not received a focused regression run.
  AC056-024 remains open for
  authorized late binding, rotation, revocation, expiry, outage and lease
  qualification.
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

### Managed engine and quality semantics (AC056-041)

`uv run pytest -q
tests/fastapi/test_managed_backend_0_56.py::test_managed_worker_preserves_native_transform_quality_and_quarantine
tests/fastapi/test_managed_backend_0_56.py::test_managed_worker_explains_continuous_streaming_boundary
tests/unit/test_extensions_0_19.py::test_bounded_plugin_authorization_status_is_not_a_credential
tests/unit/test_extensions_0_19.py::test_plugin_authorization_credential_remains_rejected`
— 6 passed. The managed worker executed an accepted CSV pipeline on Local,
Pandas 2.3.3 and Polars 1.42.1. Each engine cast identifiers, normalized names,
applied a portable quality expression through the selected engine's native
implementation, and published accepted and rejected rows to separate sinks.
This exposed and fixed plan/envelope rejection of the harmless bounded plugin
trust status `authorization=allowed`; bearer or other credential-bearing
authorization values remain rejected. Managed continuous Spark streaming now
fails with a concrete reason: this worker owns finite runs and has no streaming
trigger runner or checkpoint owner. The detailed rows and current evidence
limits are in `MANAGED_EXECUTION_MATRIX_0_56.json`. Managed workers now attach
a durable cursor file scoped by security domain, tenant, workspace and pipeline
when the accepted plan declares incremental strategies; persistence and scope
isolation passed, alongside the standalone atomic publication-barrier tests.

The managed matrix now also demonstrates end-to-end incremental cursor
advancement: an accepted run declares an `etlantic.incremental.strategies`
cursor and supplies the candidate in trusted submitter request metadata. The
cursor commits only after accepted and rejected outputs publish. This managed
adapter persists the declared cursor but does not extract source watermarks;
the source or orchestration submitter must provide the candidate.

Managed dynamic expansion and continuous Spark streaming fail closed with the
actual runtime-owner boundary: the worker runs frozen finite batches and has
no child scheduler/ledger or streaming trigger/checkpoint owner. SQL, PySpark,
DataFusion and DuckDB portable transform requests are also rejected during
planning with capability diagnostics (unsupported requirement lowering for
SQL/PySpark/DataFusion; no registered DuckDB engine capabilities). These are
recorded as unavailable combinations rather than qualified execution. The
matrix therefore qualifies the runnable Local, Pandas and Polars native paths,
the managed incremental publication barrier, and explicit rejection behavior
for the combinations the managed worker cannot run.

### Managed adaptive `/2` runtime (AC056-043)

`tests/fastapi/test_managed_backend_0_56.py::test_managed_adaptive_local_chain_is_admitted_and_observed`
qualified one exact tuple through the managed service: plan schema
`etlantic.plan/2`, support row `local-static:chain/1:local`, local engine,
implicit process-local memory bindings, and ETLantic 0.56.0 on Python 3.11.15.
The service admitted the plan during both planning and submission, and a durable
worker completed the run and published the seeded row to its memory sink.

Only that candidate row is pinned to 0.56.0. Every other packaged candidate
row retains its 0.54.0 pin and fails exact runtime version admission in this
environment. External or partial binding snapshots remain rejected. The
candidate remains Experimental with graduation pending; this observed managed
execution does not claim an Available maturity or independent graduation.
Detailed tuple and test evidence is recorded in
`MANAGED_ADAPTIVE_QUALIFICATION_0_56.json`.

## Incremental qualification notes

The following notes record focused evidence gathered as implementation landed;
open-scope language in this chronological log reflects those intermediate
checkpoints. The final release index and disposition below record the completed
qualification state.
- AC056-043 passed for the exact local-memory tuple documented above;
  candidate graduation and other package tuples remain pending or fail closed.
  checked against finalized owner-bound references and live operation leases,
  including tamper rejection, alternate principal/environment lease isolation,
  legacy retry receipt recovery, and PostgreSQL lease/cleanup races. Action
  workers were covered by scoped receipt tests and the Semblance simulator
  integration. The combined focused scope, secret, action, worker, and simulator
  runs passed 88 tests, including 9 PostgreSQL resource cases. AC056-024
  retains its complete secret lease/rotation lifecycle requirements.
  AC056-025 passed: immutable uploads bind exact version, checksum, length,
  tenant/workspace and owner; forged digest/length/scope/owner references,
  physical paths and alternate resource locators are rejected. The managed
  worker matrix rejected empty, malformed, over-budget and same-length
  tampered CSV resources before sink publication. Unsupported media/format and
  invalid references were rejected, cross-tenant/workspace/owner reads stayed
  opaque, and the PostgreSQL 16.13 multiprocess lease/cleanup race passed all
  six forced and simultaneous trials. The combined selected qualification
  command passed 37 tests. AC056-026 passed its owner-scoped cleanup,
  accepted/retry/rerun/replay retention and PostgreSQL race case.
- AC056-035 passed its typed CSV, encoding, malformed/empty/over-budget and
  tamper-rejection worker cases plus resource-retention checks; see the selected PostgreSQL-backed suite above.
- AC056-027–028 and AC056-031–032: scheduler admission parity,
  checkpoint-resume/repair/backfill, qualified pause/amendment and complete
  lifecycle qualification remain open. Firing claims now recheck the current
  schedule revision and active state in the store transaction, preventing a
  stale due-schedule scan from admitting new scheduled work after pause or
  deletion. The focused paused-after-scan regression now passes for the memory
  and SQLite stores. Schedule clock and catch-up calculations treat naive
  datetime inputs as UTC, independent of the scheduler host timezone; clock,
  loop, SQLite pause-race, and firing-scope tests passed in the latest focused
  run. The expanded outage, DST, catch-up, overlap, and persistence campaign
  now passes as recorded below for AC056-029; manual/scheduled admission
  equivalence and the complete schedule lifecycle remain open. AC056-004's CP OpenAPI field and operation coverage
  map now passes its drift and downgrade gate. AC056-033's isolated PostgreSQL
  provider and overlap cases are qualified as described above. Idempotent
  rerun and full-snapshot replay commands
  now share the managed worker path.
- AC056-038: `LogRecord.to_dict()` now reapplies recursive message, inline
  credential and sensitive-key redaction at serialization, including when
  extras have changed after record creation. The new mutation-at-serialization
  regression, HTTP/headless resource-authorization parity case, control-plane
  redaction, action redaction, event/SSE redaction, and durable-artifact
  authorization regressions passed in the focused and default suites. The
  complete cross-owner sentinel campaign across every resource owner, tenant,
  environment, and security-domain combination remains open.
- AC056-036: the complete 12 source/destination pairings through the managed
  worker, all required destination modes, and success/failure evidence remain
  open. AC056-034 now passes the Semblance-backed dataset/branch/file, all-mode,
  overlap and effect/reconciliation matrix in two independent loopback scopes;
  live Foundry access is not required.
- AC056-038–041 and AC056-044: full disclosure campaign, PostgreSQL
  backup/restore/failure, and complete advanced engine matrix remain open.
  AC056-043 passes for one exact managed adaptive `/2` tuple; other candidate
  tuples stay version-gated and the candidate remains Experimental.
  AC056-044 passed: a standard-library consumer ran through register,
  checkpointed revision, validate, plan, review and submit against an API built
  from fresh core/FastAPI wheel installs. Rejection prevented submit and webhook
  delivery; approval reused the same revision and sent one idempotent event to
  an external loopback webhook. The clean environment imported both packages
  from site-packages with workspace import paths disabled. Core and FastAPI
  wheel hashes are recorded in the release index. The earlier AC056-040 wheel
  smokes are superseded by the all-package compatibility qualification below.

## Latest candidate verification (2026-09-30)

- Default non-optional regression:
  `uv run pytest -q -m "not medallantic and not polars and not pandas and not sql and not spark and not real_pyspark and not airflow and not prefect and not keyring and not sqlmodel and not datafusion"`
  — 2,856 passed, 72 skipped, and 609 deselected. This clean rerun includes
  the adaptive-evidence regeneration guard and the firing-scope revisions
  described above.
- Cursor, artifact/event retention, and scheduler barriers:
  `uv run pytest -q tests/schedule/test_clock.py tests/schedule/test_loops.py
  tests/sqlmodel/test_schedule_store_0_47.py tests/schedule/test_firing_scope.py
  tests/runtime/test_incremental_cursor_staging_0_56.py
  tests/runtime/test_artifact_retention_0_56.py
  tests/control_plane/test_event_idempotency_retention_0_56.py`
  — 57 passed, 1 skipped. The skip is the PostgreSQL-only schedule scope case;
  no database test URL is configured in this environment. The new two-sink
  cursor tests prove that both sinks observe the old cursor before commit and
  that a failure in the second sink preserves it. Artifact cleanup tests cover
  bounded batches, retries, missing files, safe symlink handling, and managed
  SQLite scope/restart. Event tombstone pruning is bounded and scope-isolated
  for memory and SQLite stores.
- Broader implemented-feature regression batch — 236 passed, 5 skipped. It
  covered core/managed artifact retention, event idempotency retention, report
  stores and migrations, managed HTTP/headless behavior, redaction and the
  authorization matrix, action jobs, scheduler races, and local-files cursor
  publication. The skips are PostgreSQL-only cases because database URLs were
  not configured.
- Strict static qualification: `scripts/check_pyright.sh` passed. The
  suppression inventory remained at 781 entries, the strict shadow scan
  verified the reviewed reduction from 10,432 to 10,425 diagnostics, and the
  regular Pyright run reported zero errors, warnings, or informational
  diagnostics. Ruff checks and formatting checks passed for the changed
  qualification files.

See [`RELEASE_INDEX.json`](RELEASE_INDEX.json) for the per-criterion status,
case references, provider tuple and open reason. These limitations keep the
0.56 release decision open even though the implemented local gates pass.


- Output partition result lineage (AC056-017): `uv run pytest -q
  tests/runtime/test_reliability_runtime.py
  tests/fastapi/test_managed_application_0_56.py` — 38 passed. A committed
  managed CSV sink is visible through public lineage as a produced partition
  linked from its stable sink node. Runtime reports include only partition key
  names, counts, and bounded run-scoped opaque IDs; a sentinel check confirms
  source partition values are absent from serialized reports. Worker request
  reconstruction also passed for immutable nested request metadata.


- Cross-scope disclosure and redaction matrix (AC056-038):
  `uv run pytest -q tests/fastapi/test_phase_0_56_authorization_order.py
  tests/fastapi/test_cp1_full_authz_matrix.py
  tests/fastapi/test_cp1_authz_matrix.py
  tests/fastapi/test_managed_application_0_56.py
  tests/fastapi/test_managed_action_jobs_0_56.py
  tests/control_plane/test_control_plane.py` — 117 passed. Run queries,
  events, reports, artifacts, and connector-action receipts returned equivalent
  opaque outcomes across owner, tenant, workspace, environment, and
  security-domain variants. The issue #150 existing/absent ID disclosure case
  preserved explicit 404 behavior under concurrent HTTP/headless reads without
  an existence probe.

- PostgreSQL run-artifact cleanup durability (partial AC056-018 evidence):
  `ETLANTIC_CP_TEST_URL=... uv run pytest -q
  tests/sqlmodel/test_run_artifact_retention_postgresql_0_56.py` — 1 passed
  against isolated PostgreSQL 16.14. A filesystem cleanup error persisted a
  failed cleanup state while preserving the successful run status; retry
  completed cleanup, and the expired artifact plus complete state remained
  queryable after disposing and reopening the SQLModel report store. Persistent
  persistent report-store outage recovery is now covered by the restarted-worker campaign recorded below.


- Worker death, lease expiry and report recovery (AC056-014):
  `uv run pytest -q
  tests/fastapi/test_managed_backend_0_56.py::test_standard_backend_worker_persists_queryable_report_in_sqlmodel` —
  1 passed. A simulated worker death after report publication left the outbox
  recoverable. After lease expiry and SQLModel backend restart, a new worker
  reconciled the stored report with distinct stable attempt identities, emitted
  linked lifecycle events, and did not re-read changed source contents or
  write the target a second time.


- PostgreSQL CP3 failure atomicity and backup/restore (AC056-039):
  `ETLANTIC_CP_TEST_URL=... uv run pytest -q
  tests/sqlmodel/test_phase_0_56_backup_restore.py` — 1 passed against isolated
  PostgreSQL 16.14. An injected pre-outbox insert failure rolled back the
  acceptance transaction completely. A custom-format `pg_dump` restored into
  an independent database with the accepted snapshot and single pending
  outbox row intact. Combined with the existing PostgreSQL multi-process
  acceptance/quota and managed retry/race cases, this qualifies persistence,
  restart, failure, backup, and restore behavior.

- Effective-plan admission and attestation freshness (AC056-011):
  `uv run pytest -q tests/control_plane/test_policy_0_42.py
  tests/fastapi/test_cp4_routes_0_42.py
  tests/control_plane/test_action_jobs_0_56.py
  tests/fastapi/test_managed_application_0_56.py` — 55 passed. Static
  validation/planning remained source-pure; bounded preflight action execution
  canceled at its deadline; policy, approval, and quota checks used the resolved
  revision/effective fingerprint; signed attestation time is freshness-checked
  before quota admission. Focused Ruff and Pyright checks passed.

- Multi-cursor publication and control lifecycle (AC056-016):
  `uv run pytest -q tests/runtime/test_incremental_cursor_staging_0_56.py
  tests/runtime/test_artifact_retention_0_56.py tests/schedule/test_loops.py
  tests/runtime/physical/test_qualification_0_53.py` — 32 passed; 53 physical
  cases skipped because the packaged adaptive candidate is not qualified for
  this ETLantic version. Those skips are not counted as physical-executor
  evidence. Cursor candidates commit atomically in a single memory transaction
  or one locked file-backed update after every sink publishes; partial
  publication leaves all prior cursors intact. Separately, the native
  interruption, retention, and scheduler-drain batch passed 36 tests with 17
  gated physical cases skipped. Owned native work drains before return, and
  scheduler drain stops polling.

- Unknown and partial sink-effect reconciliation (AC056-015):
  `ETLANTIC_SQL_TEST_URL=... uv run pytest -q
  tests/sql/test_postgresql_live_0_56.py::test_live_failed_stage_rolls_back_and_effect_ack_reconciles` —
  1 passed against isolated PostgreSQL 16.14. The managed/simulator/runtime
  selection passed 8 tests. A lost PostgreSQL or Semblance commit acknowledgement
  reconciled against provider state; unresolved transaction creation remained
  unknown. A partial two-sink failure retained its first committed output
  without pretending to roll it back, preserved both old cursors, and blocked
  a new retry/rerun until effect reconciliation.


- Secret lease lifecycle and cache bounds (AC056-024): `uv run pytest -q
  tests/runtime/test_bugfixes.py tests/secrets/test_secrets.py
  tests/fastapi/test_managed_application_0_56.py` — 81 passed. Exact-version
  and authorized current-alias modes use run-scoped provider leases; alias
  rotation records the actual version without caching secret values. Leases
  renew while work is active, expire closed, and are revoked on completion;
  renewal/provider outage cancels work, and failed revocation produces a
  redacted `etlantic.cleanup_obligations` entry. Provider capability mismatch
  fails before I/O. Reports and events contain no secret sentinel. Cache
  coverage includes scope partitions, invalidation, TTL and capacity bounds.
  Ruff and Pyright passed for all touched source/test modules.

- Persistent report-store outage recovery (AC056-018):
  `uv run pytest -q tests/fastapi/test_managed_backend_0_56.py
  tests/fastapi/test_managed_application_0_56.py
  tests/runtime/test_artifact_retention_0_56.py` — 59 passed. With report reads
  and writes unavailable, a managed CSV sink committed once and its canonical
  report was saved under the active durable-work fence. After backend restart,
  an authorized report query recovered that result from the SQLModel SQLite
  snapshot; changing the source did not change the output. The worker later
  published the pending report and durable metadata advanced from `pending` to
  `published`. Existing PostgreSQL 16.14 cleanup-state failure/retry/restart
  coverage also passed.


- Scheduler timezone and outage recovery (AC056-029): `uv run pytest -q
  tests/schedule` — 49 passed, 1 optional PostgreSQL-scope case skipped because
  `ETLANTIC_SCOPE_TEST_DATABASE_URL` was not configured. The suite covers DST
  gaps and repeated fall-back instants, UTC normalization, bounded catch-up,
  misfire, overlap, dual-replica idempotency, schedule pause races, scoped
  firing-to-submission links, and memory/SQLite restart. A wake transport
  failure after occurrence/outbox commit recovered after simulated process
  replacement without creating another firing or submission.

- Additional AC056-040 wheel and migration checks (2026-10-01): all 25
  workspace wheels built successfully. Core, FastAPI, Foundry, SQL, and
  SQLModel wheels installed with dependency resolution into a fresh Python
  3.11.15 environment under `/tmp`; isolated `python -I` imports resolved from
  that environment's `site-packages`. Public Foundry and SQL connector/action
  factory imports passed. `etlantic_sqlmodel.migrations.apply_migrations`
  reached `012_bounded_event_tombstone_retention_0_56`. The new migration
  round-trip regression also passed: rolling back only migration 012 removed
  the expiry metadata while preserving event history and idempotency keys;
  upgrading to 012 restored expiry data and replay returned the original event.
  The migration suite passed with 19 tests. A separate seven-head SQLite
  rollback/re-upgrade matrix passed, retaining definitions, accepted submission
  identity and event history across every published CP1 rollback boundary.
  Package/schema/OpenAPI compatibility and cross-provider version-skew remain
  pending, so AC056-040 stays open.

- Latest candidate wheel refresh (2026-10-01): `uv build --all-packages
  --wheel --out-dir /tmp/etlantic-phase056-continue-wheels` rebuilt all 25
  workspace wheels and refreshed their hash/size entries in
  `WHEEL_MANIFEST.json`. A clean isolated `uv run --isolated --no-project`
  environment installed the candidate core, FastAPI and SQLModel wheels.
  Public imports, `RunIntent.RESUME`, the generated `/v1/runs/{run_id}/resume`
  OpenAPI path, and migration 012 passed without workspace path injection.

- Managed schedule baseline (AC056-027):
  `uv run pytest -q tests/fastapi/test_managed_application_0_56.py
  tests/schedule/test_loops.py tests/sqlmodel/test_schedule_store_0_47.py
  tests/fastapi/test_schedule_routes_0_47.py
  tests/sqlmodel/test_cp1_migrations_0_51.py` — 69 passed, 6 optional skips;
  Ruff and Pyright passed for touched files. Managed schedule creation resolves
  and persists the exact definition revision. Explicit trigger and configured
  scheduler callback both submit through `ManagedApplicationService.submit_run`
  and persist the resulting plan fingerprint and revision on the firing. A
  same-revision external submission has the same plan and effective fingerprint.
  A scheduler restart after submission commit but before firing-link
  acknowledgement retried the stable occurrence key, linked the original
  submission and retained one outbox item. A concurrent definition edit did
  not change the scheduled revision. The SQLModel store round-trip verified
  durable firing linkage. Embedders
  must configure `SchedulerService(run_submitter=managed_service.submit_scheduled_run)`
  to select this managed path; the legacy scheduler path remains available for
  reference stores.

- External trigger admission parity (AC056-027):
  `uv run pytest -q
  tests/fastapi/test_managed_application_0_56.py::test_external_workload_trigger_matches_manual_and_scheduled_admission`
  — passed. An injected bearer-token verifier authenticated a workload principal
  without contacting an identity service. The request was authorized by the
  same managed service and immutable revision as manual and scheduled work;
  all three durable admissions recorded one plan fingerprint, effective
  fingerprint and revision. Missing and invalid credentials returned 401,
  authenticated but unauthorized workload returned opaque 404, and a forged
  `X-Principal` header could not replace the verified workload identity. The
  rejected attempts created no extra outbox item. AC056-027 is passed.

- Schedule occurrence policy snapshots (AC056-028):
  The focused scheduler/API/SQLModel campaign passed 73 tests. A managed schedule
  selected `latest-approved` at occurrence time after its approval alias moved,
  and the firing durably recorded the chosen immutable revision and verified
  workload principal. The scheduler identity had a separate `run.submit` grant;
  schedule creation separately authorized the author's workload binding.
  Versioned parameter references resolved to the accepted request and a
  fingerprint; the accepted SecretRef retained its immutable version without
  storing secret values. The first firing-link acknowledgement was lost, the
  approval alias then moved back, and scheduler restart linked the already
  accepted run using the original revision and matching parameter/reference
  policy digests. A SQLModel close/reopen regression preserved the schedule's
  revision policy, workload identity, parameter/secret references and firing
  snapshot. AC056-028 is passed.

- Managed worker deadline and resource-bound follow-up (AC056-013 partial):
  the focused managed cancellation case now also runs with an accepted
  0.5-second run deadline. Both the explicit cancellation and timeout stopped
  the real packaged runtime before the sink wrote; the worker renewed its
  durable lease while work was in flight. This probe found that the adapter was
  propagating `PipelineTimeoutError` instead of publishing its terminal report.
  The adapter now persists the report under the active attempt fence. The
  public report retains `timed_out` and `PMEXEC408`; the durable attempt is
  failed with an unknown effect until reconciliation. The focused campaign
  `ETLANTIC_SQL_TEST_URL=postgresql+psycopg://... uv run pytest -q -rs
  tests/fastapi/test_managed_application_0_56.py::test_managed_worker_stops_real_runtime_without_writing_target
  tests/control_plane/test_durable_work_0_41.py::test_fencing_prevents_stale_attempt_from_advancing_checkpoint
  tests/sqlmodel/test_durable_work_0_41.py::test_dual_host_lease_fencing
  tests/connectors/test_local_files_csv_0_56.py::test_local_files_enforces_file_and_row_budgets
  tests/sql/test_postgresql_live_0_56.py::test_live_source_and_storage_inspection_are_bounded_and_read_only
  tests/plan/test_phase_0_52_review_blockers.py::test_adaptive_resource_limits_fail_before_crossing
  tests/runtime/test_local_runtime.py::test_profile_concurrency_caps_local_parallel_pipeline
  tests/storage/test_storage_issue_162.py::test_streaming_provider_rows_obey_cooperative_timeout`
  passed 9 tests against PostgreSQL 16.13 with no skips. PostgreSQL source
  limits now have explicit over-row (`PMCONN855`) and over-byte (`PMCONN856`)
  failure assertions. Four additional secret-lease renewal, expiry, outage and
  revocation-obligation cases passed. The complete AC056-013 resource and
  worker-lifecycle campaign is recorded with the qualified result above.

- Schedule pause/resume and safe amendment boundaries (AC056-032):
  `ETLANTIC_SCOPE_TEST_DATABASE_URL=postgresql+psycopg://... uv run pytest -q
  tests/schedule/test_firing_scope.py tests/schedule/test_loops.py
  tests/fastapi/test_schedule_routes_0_47.py
  tests/sqlmodel/test_schedule_store_0_47.py
  tests/fastapi/test_phase_0_56_authorization_order.py
  tests/fastapi/test_phase_0_56_control_coverage.py` — 39 passed across
  memory, SQLite and PostgreSQL. A due-schedule scan followed by pause rejected
  the stale claim without a firing or durable outbox item; resume admitted that
  same occurrence. Active and stale-revision amendments were rejected. After
  the accepted firing completed, a compare-and-swap amendment advanced the
  schedule revision, preserved the prior firing record and prevented a claim
  against the old revision. The HTTP amendment route requires `schedule.write`,
  accepts only the expected revision and replacement spec, and returned a
  conflict for a stale revision. Public-control inventory and authorization
  campaigns cover the new operation. The CP1 and CP-GA OpenAPI snapshot suite
  also passed after recording the 92-operation contract. Ruff, format and
  Pyright checks passed for the completed change.

## Earlier AC056-040 package compatibility qualification (superseded; 2026-10-01)

- `uv build --all-packages --wheel --out-dir /tmp/etlantic-ac056-040-wheels
  --clear` built all 25 workspace distributions. `WHEEL_MANIFEST.json` records
  each candidate filename, byte length and SHA-256.
- All 25 wheels were dependency-resolved and installed together into a fresh
  Python 3.11.15 virtual environment. Qualification ran with `python -I`; all
  25 public package roots resolved from that environment's `site-packages`.
  Every declared `__all__` export resolved (387 exports total).
- The installed CP1 and CP-GA applications matched their committed OpenAPI 3.1
  path and operation-ID snapshots. Both expose 57 component schemas; all 161
  local schema references resolve. Component-schema SHA-256 is
  `f05f97b9d9a4ae54a96a657f3943b490784a9711131392744a46bfa5d4c6fb70`.
- Installed metadata for all 24 adapters accepts the candidate base package
  and rejects 0.54.99 and 0.56.0 under the declared version constraints. The
  exact 0.56.0 candidate set resolved and installed as one environment. The
  report records the resolved FastAPI, Pydantic, SQLModel, SQLAlchemy, pandas,
  Polars, PyArrow, DuckDB, DataFusion, Prefect and PySpark versions.
- The installed SQLModel migration chain upgraded a fresh database to
  `012_bounded_event_tombstone_retention_0_56`, then rolled back and upgraded
  again from every supported CP1 head from 005 through 011. A definition,
  accepted submission identity and event history survived every round-trip.
- In the isolated wheel environment,
  `tests/sqlmodel/test_cp1_migrations_0_51.py`, both FastAPI OpenAPI snapshot
  tests, and both wire-schema tests passed: 34 passed and 6 PostgreSQL cases
  skipped because no test database URL was configured. The package/version
  compatibility, connector-schema and schema-drift suites passed 87 tests.
  `PACKAGE_COMPATIBILITY_0_56.json` records the environment, wheel-installed
  exports, version ranges, schema hashes and migration heads. The repeatable
  install commands are `uv venv --python 3.11 <venv>` followed by
  `uv pip install --python <venv>/bin/python --find-links <wheel-dir>
  <wheel-dir>/*.whl`; install `pytest==8.4.2` as the harness, then run
  `python -I scripts/qualify_phase056_packages.py --repo-root <workspace>
  --wheel-dir <candidate-wheel-directory> --output <report.json>` from that
  installed environment. The command verifies the wheel directory against the
  checked-in size/hash manifest.
  AC056-040 is passed; this qualification makes no live PostgreSQL migration
  claim.


## Partition repair and backfill qualification (AC056-031)

- Isolated PostgreSQL 16.13 loopback cluster, CPython 3.11.15, macOS arm64.
- `ETLANTIC_SQL_TEST_URL=... uv run pytest -q tests/sql/test_postgresql_partition_plans_0_56.py tests/sql/test_postgresql_live_0_56.py tests/fastapi/test_managed_partition_lifecycle_0_56.py tests/fastapi/test_managed_rerun_http_0_56.py` — 16 passed.
- The managed lifecycle case submits a parent run, edits partition `a`, issues repair through HTTP and backfill through the service, retries the same backfill idempotency key, and verifies both child runs, final selected rows, statuses, report state and parent/submission/attempt lineage. Provider cases verify bounded selector plans, fail-closed configuration, selected-partition replacement, empty replacement, preservation of untouched partitions and rollback for rows outside the selector.
- Detailed observations and safety boundaries are recorded in `PARTITION_REPAIR_BACKFILL_0_56.json`. The temporary database contained only test fixtures and was isolated from application data.

## Managed checkpoint resume qualification (AC056-031)

- Fixed adaptive admission to receive the scoped artifact workspace during plan, submit, and runtime admission. Managed resume now validates a persisted checkpoint against the accepted plan and the checkpointed output port's contract ID; plan nodes do not always carry that contract directly.
- Managed execution now returns a plan/run-bound failed report from `PipelineExecutionError` for effect classification. The worker records no effect only when there are no committed or ambiguous publications, outbound events, or unresolved cleanup obligations; any such evidence keeps retry and resume blocked for reconciliation. The shared classifier emits `run.failed` for clean failures and reserves `run.reconciliation_required` for unresolved effect evidence.
- The managed resume case interrupts execution immediately after the checkpoint value and CP linkage commit, verifies that the parent fails naturally, then resumes in a new `ExecutionHost`. The child report selects the persisted checkpoint and the downstream transform observes the checkpointed row value. A focused classifier case verifies that an unresolved secret-lease cleanup obligation records an unknown effect.
- `uv run pytest -q tests/fastapi/test_managed_application_0_56.py tests/fastapi/test_managed_partition_lifecycle_0_56.py tests/fastapi/test_managed_rerun_http_0_56.py tests/runtime/physical/test_qualification_0_53.py` — 83 passed, 57 skipped. The suite exercises the persisted-checkpoint resume path and effect classification along with repair, backfill, rerun and physical-operation cases.
- Managed result-publication recovery, unknown-attempt effect gating and checkpoint-link regression batch: 44 passed.
- The same run exercised repair, backfill, rerun and physical-operation qualification cases. PostgreSQL-specific partition tests were not rerun because `ETLANTIC_SQL_TEST_URL` was unset in this environment; the isolated PostgreSQL 16.13 qualification above remains the evidence for those cases.


- Final default non-optional regression after the 0.56 package, checker and repair/backfill changes:
  `uv run pytest -q -m "not medallantic and not polars and not pandas and not sql and not spark and not real_pyspark and not airflow and not prefect and not keyring and not sqlmodel and not datafusion"` — 2,983 passed, 105 skipped, 605 deselected in 4m44s; exit code 0. This includes the refreshed 0.52 adaptive evidence regeneration check.


## Final candidate disposition

The release index records all 44 criteria as qualified. AC056-026 includes a
current-source PostgreSQL 16.13 lease/cleanup race rerun after the
`acquire_leases` change. AC056-031 covers managed checkpoint restoration
alongside the previously qualified PostgreSQL repair and backfill behavior.
Historical regressions, focused provider suites and isolated wheel checks
remain evidence for their recorded source states; current-tree regression
results are listed above. No package tag or publication is
claimed; the published supported line remains 0.55.x.

- Static and documentation gates: `uv run pyright` — 0 errors; `uv run ruff check .` and `uv run ruff format --check .` passed; `uv run python scripts/check_docs.py` passed; `uv run mkdocs build --strict` built the site successfully; `uv run python scripts/check_release.py` passed all in-repository release checks and reported 24 existing candidate distributions missing from PyPI and the new
etlantic-foundry project that will be created on its first upload.

## Superseding AC056-040 qualification after the standalone reset (2026-10-06)

This result supersedes the 2026-10-01 package qualification above. The older
section documented rollback and historical-input support that the current 0.56
release boundary no longer claims.

- Rebuilt all 25 wheels and 25 source distributions from the reviewed candidate
  with `uv build --all-packages`; the current wheel SHA-256 values and sizes are
  in `WHEEL_MANIFEST.json`.
- Installed all 25 wheels together in a fresh CPython 3.11.15 environment.
  The qualifier confirmed all package roots and 387 exports resolve from the
  installed environment and checked the committed wheel manifest, dependency
  constraints, both OpenAPI snapshots, schema references, and migration head
  `014_cp1_complete_principal_idempotency_0_56`.
- The current-schema migration smoke created canonical definition, accepted
  submission, and event records, then verified their identities on the fresh
  current head. It makes no claim that old state can be migrated or rolled back
  into subject-only identity semantics.
- The isolated wheel test subprocess verified all 25 package import origins
  before collecting tests, overrode the repository pytest `pythonpath`, and ran
  with `--import-mode=importlib`. The two suites passed 48 and 88 tests; 6
  PostgreSQL cases were skipped because no test URL was configured.
- Source regressions for canonical request fields, legacy flat intent keys,
  stream-envelope aliases, and unsafe schema rollback passed in the focused
  source run: 38 passed, 6 PostgreSQL cases skipped.
- `PACKAGE_COMPATIBILITY_0_56.json` contains the package, OpenAPI, migration,
  installed-wheel test, and environment results. `RELEASE_INDEX.json` records
  the current hashes and updates AC056-040/042 to the standalone boundary.


## Final release-review remediation (2026-10-06)

Two findings from the final review of `a829ce2a` were reproduced and fixed:

- PostgreSQL effect reconciliation now tries the same advisory transaction lock
  held by the writer. A busy effect remains `unknown`; after acquiring the lock,
  a separate read under `READ COMMITTED` checks the settled ledger state.
  Live regressions cover active writers that subsequently commit or roll back,
  and a deferred constraint trigger that blocks PostgreSQL inside `COMMIT`.
- Connector catalog sensitivity now propagates through nested object properties,
  composition branches and array items. Twenty public-catalog cases cover
  `writeOnly`, `x-sensitive`, `sensitive` and credential-named parents while
  preserving non-sensitive defaults and the provider's original schema.

The initial new regressions failed before the fixes (22 failed). The final
source provider/privacy suite passed all 63 tests against an isolated local
PostgreSQL 16.13 cluster. The same tests passed against installed candidate
wheels with repository source paths disabled: 43 provider/privacy tests, then
20 managed PostgreSQL/Foundry simulator matrix cases after installing the
optional Semblance test dependency. No live Foundry account was used.

All 25 wheels and 25 source distributions were rebuilt. The refreshed wheel
manifest records the changed core and SQL artifacts; the clean-environment
package qualifier passed all 25 package roots and 387 exports, both OpenAPI
snapshots, schema references, fresh current migrations, and suites of 54 and
88 tests with live PostgreSQL migration cases enabled. The independent private
provider qualification was rerun against the rebuilt core wheel and passed.

The adaptive acceptance campaign regenerated its ten artifacts for the updated
source and tests. Ruff lint/format, Pyright (zero errors), documentation
consistency, strict MkDocs and release readiness checks passed. No tag or
publication is claimed; the fresh-store boundary and candidate maturity remain
unchanged.


Final default regression after these fixes:
`uv run pytest -q -m "not medallantic and not polars and not pandas and not sql and not spark and not real_pyspark and not airflow and not prefect and not keyring and not sqlmodel and not datafusion"`
— 3,281 passed, 123 skipped, 731 deselected, 22 warnings in 5m48s; exit code 0.
The new catalog cases are included; live PostgreSQL cases are qualified by the
separate source and installed-wheel provider runs above.

## Connector catalog privacy requalification for issue #269 (2026-10-06)

At source commit `7db7329d`, catalog sample sanitization is schema-aware for
ancestor defaults/examples, object properties, array items, compositions, and
local JSON Schema references. Unresolved and cyclic references fail closed.
Dynamic references fail closed; conditional and unevaluated schemas contribute
sensitivity context. Legacy `dependencies` and tuple `additionalItems` schemas
are also included. The focused catalog regression suite passed 62 tests; Ruff
lint, format, and `git diff --check` passed.

All 25 candidate 0.56 wheels were rebuilt. A fresh Python 3.11.15 virtual
environment installed the rebuilt core wheel, then `python -I` imported the
installed package with workspace paths disabled and passed the four original
reproductions plus `additionalProperties`, `prefixItems`, dynamic-reference,
conditional, unevaluated-property/item, `contains`, malformed-reference, JSON
`contentSchema`, legacy `dependencies`, and tuple `additionalItems` cases from
review (15 synthetic cases total). The updated wheel SHA-256 and size are
recorded in `WHEEL_MANIFEST.json`.
