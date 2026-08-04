# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.43.0] - 2026-08-04

### Adopter summary

| | |
|---|---|
| Who must act | Anyone pinning `etlantic==0.42.x` or plugins with `<0.43` |
| Breaking | Dependency floor becomes `etlantic>=0.43.0,<0.44` (CP-GA line) |
| Upgrade | `pip install 'etlantic==0.43.0'` and matching plugins / `medallantic==0.43.0`. See [Migration 0.42 → 0.43](docs/11_DEVELOPMENT/MIGRATION_0_42_TO_0_43.md) |
| Rollback | Re-pin 0.42.0 minors together; re-validate SQLModel migrations |
| Security | Production multi-tenant **only** for Supported isolation profiles; community **non-SLA** |

### Added
- CP-GA qualification evidence packs and `scripts/check_cp_ga_*.py` campaigns
- Frozen support / isolation matrices and gate traceability index
- EXIT_GATE_0_43, FINDINGS_0_43, WHATS_NEW_0_43, MIGRATION_0_42_TO_0_43
- CP-GA operator runbook and drill templates
- FastAPI OpenAPI CP-GA operationId snapshot and two-tenant isolation tests

### Changed
- Official package versions align at 0.43.0; plugins require
  `etlantic>=0.43.0,<0.44`
- Supported security release line is 0.43.x
- Production multi-tenant claim published for `isolated-deployment` and
  `dedicated-schema`; `shared-service` remains Experimental
- FastAPI report/lineage/reliability stubs marked Experimental (not CP-GA)
- Capacity envelopes document overload fail-closed + WRR under shared pressure

### Fixed
- Host honesty for experimental stub routes and CP-GA claim boundaries
- Erasure empty-provider vacuous completion; WRR idle-owner starvation;
  attestation scope mismatch on put; SoD issuer-mismatch self-decide bypass;
  definition miss raises `ControlPlaneError.not_found`
- CP-GA campaign evidence honesty (dual-store isolation, fingerprint identity,
  FastAPI opaque definition 404, SQLModel matrices without skip)
- Active docs/roadmap/exit-gate voice for the published 0.43.0 line

## [0.42.0] - 2026-08-04

### Adopter summary

| | |
|---|---|
| Who must act | Anyone pinning `etlantic==0.41.x` or plugins with `<0.42` |
| Breaking | Dependency floor becomes `etlantic>=0.42.0,<0.43` (CP4 policy/audit line) |
| Upgrade | `pip install 'etlantic==0.42.0'` and matching plugins / `medallantic==0.42.0`. See [Migration 0.41 → 0.42](docs/11_DEVELOPMENT/MIGRATION_0_41_TO_0_42.md) |
| Rollback | Re-pin 0.41.0 minors together; re-validate |
| Security | CP4 policy/quota/audit/erasure/attestations; **not** a production multi-tenant isolation claim (**0.43**) |

### Added
- CP4 `PolicyProvider` / `MemoryPolicyProvider`, approvals/SoD, quotas,
  delivery objectives, governed erasure, attestations, `AuditEvidenceStore`
- FastAPI optional CP4 injection and
  `/v1/policy|approvals|quotas|erasure|audit|attestations|objectives`
- Completed `/v1/durable` effects/repair/diagnose/shadow routes (diagnose is
  POST-only)
- SQLModel migration `003_cp4_governance` + durable submission/outbox entity
  dual-write mirrors (snapshot remains canonical)
- CLI `etlantic erasure plan|status` with `--store` scratch round-trip
- ADR-019, EXIT_GATE_0_42, FINDINGS_0_42, WHATS_NEW_0_42, MIGRATION_0_41_TO_0_42
- CP4 conformance/chaos/objective check scripts and outage matrix

### Changed
- Official package versions align at 0.42.0; plugins require
  `etlantic>=0.42.0,<0.43`
- Supported security release line is 0.42.x
- FastAPI submit/promote run CP4 policy/quota/approval/attestation gates when
  providers are configured; missing CP4 providers return Problem Details
  `PMCP501`
- Quota fairness uses weighted round-robin under host-marked `shared_pressure`
- Attestation stores require an explicit signing secret (`for_tests()` only in
  unit suites)
- OPA adapter documented as stub/fallback (no embedded evaluate path)

### Fixed
- SQLModel audit list/verify/export no longer bump snapshot `payload_version`
- Connector `PACKAGE_VERSION` and example pins aligned to 0.42.0
- Active docs/roadmap/exit-gate voice for the published 0.42.0 line

## [0.41.0] - 2026-07-31

### Adopter summary

| | |
|---|---|
| Who must act | Anyone pinning `etlantic==0.40.x` or plugins with `<0.41` |
| Breaking | Dependency floor becomes `etlantic>=0.41.0,<0.42` (CP3 durable-work line) |
| Upgrade | `pip install 'etlantic==0.41.0'` and matching plugins / `medallantic==0.41.0`. See [Migration 0.40 → 0.41](docs/11_DEVELOPMENT/MIGRATION_0_40_TO_0_41.md) |
| Rollback | Re-pin 0.40.0 minors together; re-validate |
| Security | CP3 durable coordination + fencing/outbox evidence; **not** a production multi-tenant isolation claim (**0.43**) |

### Added
- CP3 `DurableWorkStore` / `MemoryDurableWorkStore`: accept/outbox, cancel,
  leases/fencing/heartbeat/release, attempts, checkpoint CAS, effects,
  replay/repair/backfill plans, preview TTL/staleness/shadow, admission
- Optional SQLModel durable provider + migration `002_durable_cp3`
- FastAPI optional `durable_work` injection, dual-write submit, `/v1/durable/*`
- Durable conformance/chaos scripts and chaos matrix evidence
- What's New / Migration / Exit Gate / Findings for 0.42; ADR-018 Accepted

### Changed
- Official package versions align at 0.41.0; plugins require
  `etlantic>=0.41.0,<0.42`
- Durable-work hardening requires fenced checkpoint CAS; cancellation expires
  leases and blocks heartbeat/CAS; control-plane cancellation is durable-first,
  and CP1 compensates when durable acceptance fails
- SQLModel durable storage now covers read-only plan/explain/replay paths;
  FastAPI profile resolution fails closed; Safe I/O preserves numeric zero for
  read budgets and lock timeouts
- Supported security release line is 0.41.x
- GitHub Actions use the current checkout, uv (setup-uv@v9.0.0), Java,
  provenance, SARIF, and artifact action majors; CI runs on uv 0.12.0 and
  covers Airflow 2.11.1 and 3.2.1 (the resolvable final 2.x line and current
  3.x line)

### Security
- Stale fencing tokens cannot publish terminal state or advance checkpoints
- Unknown external effects fail closed without reconciliation evidence
- Durable input snapshots, replay diffs, preview reasons, and CLI diagnostics
  are redacted; secret and Safe I/O failures cannot be bypassed by
  `CONTINUE`/`SKIP` policies
- Explicit docs boundary: CP3 ≠ production multi-tenant

## [0.40.0] - 2026-07-31

### Adopter summary

| | |
|---|---|
| Who must act | Anyone pinning `etlantic==0.39.x` or plugins with `<0.40` |
| Breaking | Dependency floor becomes `etlantic>=0.40.0,<0.41` (CP2 registry line) |
| Upgrade | `pip install 'etlantic==0.40.0'` and matching plugins / `medallantic==0.40.0`. See [Migration 0.39 → 0.40](docs/11_DEVELOPMENT/MIGRATION_0_39_TO_0_40.md) |
| Rollback | Re-pin 0.39.0 minors together; re-validate |
| Security | CP2 registry isolation evidence + OpenLineage non-authority; **not** a production multi-tenant isolation claim (**0.43**) |

### Added
- CP2 registry: tenant/workspace directories, immutable revisions, aliases,
  promotions, memory + optional SQLModel providers and migrations
- Metadata-only histories / impact indexes; workspace safe-root resources
- Ops: revision metadata search/pagination, observation retention hooks,
  SQLite registry backup/restore transcript
- Optional Experimental `etlantic-openlineage` outbound exporter (non-authority)
- Isolation-profile matrix fake evidence (isolated / dedicated-schema /
  shared-service + second control)
- What's New / Migration / Exit Gate / Findings for 0.40; ADR-017 Accepted

### Changed
- Official package versions align at 0.40.0; plugins require
  `etlantic>=0.40.0,<0.41`
- Supported security release line is 0.40.x
- PyPI Beta classifier retained on core
- Release inventory is seventeen distributions (adds `etlantic-openlineage`)

### Security
- Two-tenant / two-workspace isolation matrix on supported profiles
- Shared-service WHERE-only filters documented as insufficient without a
  second control (RLS stub / tenant credentials)
- OpenLineage transport failures cannot mutate registry authority
- Explicit docs boundary: CP2 ≠ production multi-tenant

## [0.39.0] - 2026-07-31

### Adopter summary

| | |
|---|---|
| Who must act | Anyone pinning `etlantic==0.38.x` or plugins with `<0.39` |
| Breaking | Dependency floor becomes `etlantic>=0.39.0,<0.40` (CP1 control-plane line) |
| Upgrade | `pip install 'etlantic==0.39.0'` and matching plugins / `medallantic==0.39.0`. See [Migration 0.38 → 0.39](docs/11_DEVELOPMENT/MIGRATION_0_38_TO_0_39.md) |
| Rollback | Re-pin 0.38.0 minors together; re-validate |
| Security | CP1 authz-before-lookup + redaction on errors/SSE/reports; **not** a production multi-tenant isolation claim (**0.43**) |

### Added
- Public `etlantic.control_plane` identity, authz, memory fakes, and error envelopes
- Embeddable CP1 FastAPI surface (`ETLanticAPI`, `include_router`, `create_app`)
  with durable `202` submit, run observation stubs, schema/reliability stubs,
  and resumable SSE (`cp_stream_run_events`)
- Landing-zone watch submitter outside core (`LandingWatchSubmitter`)
- Optional SQLModel request-scoped control-plane reference stores
- What's New / Migration / Exit Gate / Findings for 0.39; ADR-016 Accepted

### Changed
- Official package versions align at 0.39.0; plugins require
  `etlantic>=0.39.0,<0.40`
- Supported security release line is 0.39.x
- PyPI Beta classifier retained on core

### Fixed
- Generated agent guidance includes the 0.39 connector/control-plane public
  surfaces and preserves the FastAPI CP1 versus reference-app boundary
- Medallantic migration goldens align with the 0.39 version-tagged adapter
  metadata
- Plugin trust-isolation coverage authorizes the installed release candidate
  version instead of a stale prior-minor pin

### Security
- Non-enumeration matrix across CP operationIds × two tenants
- Problem Details / event / report bodies redact secret-like keys
- Path/header tenant claims remain routing-only (never authority)
- Explicit docs boundary: CP1 ≠ production multi-tenant

## [0.38.0] - 2026-07-31

### Adopter summary

| | |
|---|---|
| Who must act | Anyone pinning `etlantic==0.37.x` or plugins with `<0.38` |
| Breaking | Dependency floor becomes `etlantic>=0.38.0,<0.39` (connectivity line) |
| Upgrade | `pip install 'etlantic==0.38.0'` and matching plugins / `medallantic==0.38.0`. See [Migration 0.37 → 0.38](docs/11_DEVELOPMENT/MIGRATION_0_37_TO_0_38.md) |
| Rollback | Re-pin 0.37.0 minors together; re-validate |
| Security | Connector plans/checkpoints remain secret-free and row-free; production allowlist still fails closed before connector import |

### Added
- Public connector protocols `etlantic.source/1`, `etlantic.sink/1`,
  `etlantic.storage/1` under `etlantic.connectors`
- Built-in `local-files` landing-zone source (Preview): snapshot +
  incremental ledger, checkpoint schema `etlantic.landing_checkpoint/1`
- Connector CDK helpers and public `etlantic.testing` connector conformance
- Optional Experimental packages: `etlantic-s3`, `etlantic-iceberg`,
  `etlantic-snowflake`; PostgreSQL source/sink connectors on `etlantic-sql`
- Capability matrix, What's New / Migration / Exit Gate / Findings for 0.38
- Connector SDK and landing-zone execution docs

### Changed
- Official package versions align at 0.38.0; plugins require
  `etlantic>=0.38.0,<0.39`
- Supported security release line is 0.38.x
- StorageBinding remains via compatibility adapter (no silent connector claims)
- PyPI Beta classifier retained on core; cloud connector packages use Alpha

### Security
- Static plans record identity scheme only (no live file lists)
- Physical landing-root paths excluded from new plans/reports
- Publication barriers: cursor/ledger advance only after committed outcomes

## [0.37.0] - 2026-07-30

### Adopter summary

| | |
|---|---|
| Who must act | Anyone pinning `etlantic==0.36.x` or plugins with `<0.37` |
| Breaking | Dependency floor becomes `etlantic>=0.37.0,<0.38` (stable-foundation line). Remaining demoted root aliases and `DataContractModel` removed |
| Upgrade | `pip install 'etlantic==0.37.0'` and matching plugins / `medallantic==0.37.0`. See [Migration 0.36 → 0.37](docs/11_DEVELOPMENT/MIGRATION_0_36_TO_0_37.md) |
| Rollback | Re-pin 0.36.0 minors together; re-validate |
| Security | Compatibility fixtures and reports remain secret-free; production allowlist pins fail closed; security verification matrix ships with automated checks |

### Added
- Stable-foundation acceptance suite evidence for items 1–21
  (`tests/stable_foundation/` + `scripts/check_stable_foundation.py`)
- Security verification matrix with owner + automated check per control
  (`docs/02_FOUNDATIONS/SECURITY_VERIFICATION_MATRIX.md`,
  `scripts/check_security_matrix.py`)
- Diagnostic-code stability tiers inventory
  (`docs/10_REFERENCE/DIAGNOSTIC_STABILITY_TIERS.md`,
  `scripts/check_diagnostic_stability.py`)
- Release baseline / burn-in fixtures for `v0_37` under
  `tests/fixtures/releases/` and `tests/fixtures/burn_in/`
- What's New / Migration / Exit Gate / Findings documentation for 0.37

### Changed
- Official package versions align at 0.37.0; plugins require
  `etlantic>=0.37.0,<0.38` (external echo reference pin
  `etlantic>=0.37,<0.38`)
- Supported security release line is 0.37.x
- `etlantic.testing` graduates from preview freeze to stable
  application-pipeline testing foundation
- Public surface / protocol freeze inventories align to the 0.37 reference
  envelope; first-party packages declare `etlantic>=0.37.0,<0.38`
- `etlantic.scheduler/1` remains stable MVP; `etlantic.quality/1` remains
  provisional; DataFusion remains experimental; Arrow stays Gate A only
- PyPI Beta classifier retained on core and first-party packages

### Removed
- Remaining demoted root facade aliases (`_DEMOTED_ALIASES` empty;
  `_REMOVED_0_37` raises with migration guidance)
- `DataContractModel` root / contracts compatibility alias; use
  `etlantic.Data` / `ContractModel`

### Fixed
- Root removal regressions covered by
  `tests/unit/test_root_removals_0_37.py` and testing-foundation suites
- Docs / release-facts / artifact verification contract pointed at v0.37.0
  (expected after tag; digests filled at publish)

### Upgrade notes
- Pin core and matching plugins / `medallantic` together at `==0.37.0`
- Replace demoted root imports and any `DataContractModel` usage before
  upgrade
- Plugin authors: raise the floor to `etlantic>=0.37.0,<0.38` and re-run
  public conformance
- Prefer graduated public `etlantic.testing` for application pipeline cases

## [0.36.0] - 2026-07-30

### Adopter summary

| | |
|---|---|
| Who must act | Anyone pinning `etlantic==0.35.x` or plugins with `<0.36` |
| Breaking | Dependency floor becomes `etlantic>=0.36.0,<0.37` (no wire-schema reset). Bare run-report metadata keys migrate to namespaced keys. Production allowlists require non-empty version pins. Soft-continued runs report `PARTIAL`. Missing implementations fail at plan (`PMPLAN301`). Reliability `partition-check` / `quality-trends` require evidence flags |
| Upgrade | `pip install 'etlantic==0.36.0'` and matching plugins / `medallantic==0.36.0`. See [Migration 0.35 → 0.36](docs/11_DEVELOPMENT/MIGRATION_0_35_TO_0_36.md) |
| Rollback | Re-pin 0.35.0 minors together; re-validate |
| Security | Compatibility fixtures and reports remain secret-free; production allowlist pins + outbound default-deny fail closed; schema history / authoring / Safe I/O hardened; digests/attestations as shipped |

### Added
- Joint compatibility burn-in evidence for `0.34 → 0.35` and `0.35 → 0.36`
  (current-reader and isolated-wheel reader/writer paths)
- Release baseline manifests and known-defect fixtures under
  `tests/fixtures/releases/`
- Burn-in goldens for `v0_34`–`v0_36` alongside historical `v0_24`–`v0_27`
- Application-pipeline testing burn-in against the frozen preview minimum
  contract (`etlantic.testing`; foundation graduation remains 0.37)
- What's New / Migration / Exit Gate / Findings documentation for 0.36

### Changed
- Official package versions align at 0.36.0; plugins require
  `etlantic>=0.36.0,<0.37`
- `etlantic.scheduler/1` promoted to stable MVP (Prefect bounds) on the
  foundation path
- `etlantic.quality/1` remains provisional (outside the full stable-foundation
  claim)
- Run-report bare metadata keys migrate to namespaced keys without silent
  field loss
- Production `plugin_allowlist` entries require non-empty version pins;
  package names are canonicalized for matching
- Reliability CLI: `partition-check` requires `--observed`; `quality-trends`
  requires `--values` (preview-only)

### Fixed
- Forward compatibility for 0.35.0 bare-key run-report metadata via documented
  migration and known-defect fixture
  (`tests/fixtures/releases/v0_35/known_defects/run_report_bare_metadata.json`)
- `SecretValue` is no longer a dataclass (blocks `dataclasses.asdict` plaintext
  leaks)
- Schema history rejects list-of-lists, nested cells, and JSON-string row
  payloads
- Authoring serialization rejects DSN keys and URL userinfo in definition
  values
- Safe I/O: empty `approved_roots` fail closed; `symlink_policy=reject` denies
  any symlink component; invalid profile `safe_io` no longer silently dropped;
  lock/append files use `0o600`
- Production outbound requires `default_deny` and non-empty `allowed_hosts`
- Profile warns when `name` looks like production without
  `security_mode=production`
- Planner fails closed (`PMPLAN301`) without a real implementation; plan graphs
  are frozen after build
- Contract validation requires schema fingerprint match for shared published
  [ODCS](docs/03_DATA_CONTRACTS/ODCS.md) ids; mixed typed/untyped ports fail
  closed
- `FailureAction.CONTINUE` soft-skips report `PARTIAL` (never pure `SUCCEEDED`)
- Spark sinks no longer coerce Delta for `overwrite_partition` / bare
  `pyspark` provider
- LazyFrame record counts report unknown (`None`) instead of a false zero
- OPS examples, FastAPI OpenAPI version, and Medallantic ROADMAP release header
  aligned to 0.36.0
- Package READMEs, optional-API metadata, planning status, and Beta maturity
  language aligned to 0.36; release-artifact docs no longer predict an SBOM
  outcome before the tag workflow runs
- Documentation checks now reject stale `current_minor` / current-boundary
  markers, contradictory package maturity text, and premature release-asset
  claims
- Log redaction covers `auth`/`jwt`/`bearer` keys and JWT-shaped tokens

## [0.35.0] - 2026-07-30

### Adopter summary

| | |
|---|---|
| Who must act | Anyone pinning `etlantic==0.34.x` or plugins with `<0.35` |
| Breaking | Dependency floor becomes `etlantic>=0.35.0,<0.36` (no wire-schema reset) |
| Upgrade | `pip install 'etlantic==0.35.0'` and matching plugins / `medallantic==0.35.0`. See [Migration 0.34 → 0.35](docs/11_DEVELOPMENT/MIGRATION_0_34_TO_0_35.md) |
| Rollback | Re-pin 0.34.0 minors together; re-validate |
| Security | Migration analysis remains secret-free; digests/attestations as shipped |

### Added
- Public authoring helpers: `inspect_definition`, `rewrite_definition`,
  `definition_provenance`
- Application-pipeline testing preview in `etlantic.testing`
- Medallantic M7 SparkForge project inventory and safe native generation
- What's New / Migration / Exit Gate 0.35 documentation

### Changed
- Package versions and plugin pins advance to the 0.35.x line; plugins require
  `etlantic>=0.35.0,<0.36`

## [0.34.0] - 2026-07-30

### Adopter summary

| | |
|---|---|
| **Who must act** | Anyone on 0.33.x upgrading to M6 observability / run-history surfaces; production profiles that will use `durable_audit` or new provider keys; plugin authors pinning `etlantic>=0.34.0,<0.35` |
| **Breaking** | No wire-schema reset (`pipeline/1`, `plan/1` unchanged). Behavior hardenings: production allowlist / trust denials fail closed more consistently; secret-like values rejected from plans/reports/assets; Delta/SQL merge fail-closed without Delta; Airflow compile stubs on ERROR diagnostics |
| **Upgrade** | `python -m pip install --upgrade 'etlantic==0.34.0'` and matching plugins / `medallantic==0.34.0`. See [Migration 0.33 → 0.34](docs/11_DEVELOPMENT/MIGRATION_0_33_TO_0_34.md) |
| **Rollback** | Reinstall prior pins (core + plugins same minor), restore allowlist pins, re-validate / re-plan. Keep a `.etlantic/` workspace backup. [Rollback and recovery](docs/06_EXECUTION/ROLLBACK_RECOVERY.md) |
| **Security impact** | Stronger fail-closed trust, secret redaction, and merge/identifier safety. Review production profiles after upgrade. CycloneDX SBOM generation failed for the v0.34.0 GitHub Release; SHA-256 digests + attestations shipped |

### Security and reliability hardening
- Phase-aware ``PMPLUG402``: authorize/selected-engine denials block
  ``ensure_plugins`` / run / compile / doctor / execute (discovery siblings stay
  non-blocking); ``run`` maps all raised ``PMPLUG*`` to ``TRUST_FAILURE``; doctor
  plugin trust failures exit ``11``
- Manual overlays cannot spoof builtin ``local``/``env`` allowlist exemption;
  secret / observability / run-history / event-consumer / storage registers are
  production-allowlist gated; authorize path no longer exempts engine-name spoofs
- ``Profile`` constructor rejects plaintext secrets; plan/profile serialization
  refuses non-``SecretRef`` values
- Profile assets / binding deserialize reject URL userinfo so credential URLs
  cannot enter plan snapshots; report nested metadata bags and extension keys
  (including ``dsn`` / ``connection_string`` / ``jdbc_url`` and URL values) fail
  closed; CLI ``emit_payload`` redacts before echo
- Delta ``merge_keys`` validated as safe identifiers; non-Delta MERGE/UPSERT
  fails closed (no overwrite fallback); Delta capabilities require
  ``delta.tables.DeltaTable``
- SQL executor diagnostics redact exception text; PostgreSQL MERGE without
  update columns fails closed unless explicit insert-ignore intent
- Airflow compile preserves schedule timezone (``ScheduleIntent.from_mapping``
  no longer invents UTC), stubs on any ERROR diagnostic (not only schedule),
  refuses unsupported schedules with a non-schedulable stub, and secret-scans
  rendered source (including URL userinfo)
- Trusted-SQL profile mismatch uses ``PMEXEC353`` and is CONTINUE/SKIP hard-fail;
  ``redact_message`` redacts full URL userinfo
- CSV/JSON sinks honor ``write_mode`` and optional ``SafeIoPolicy``; memory
  merge/upsert fails closed; ``FileStateStore.commit`` reads previous inside
  locked RMW; durable_audit event consumers fail closed
- Medallantic: missing validation/artifact status fail closed; run status
  reconciled when steps failed; empty SparkForge write mode rejected
- ``FileStateStore`` fails closed on corrupt state; schema history verifies
  stored fingerprints; file schema/run-history providers default
  ``fail_closed=True``

### Added
- Lifecycle event correlation (`etlantic.lifecycle_event/1`) with plan/region/backend fields
- Observability provider protocol (`etlantic.observability/1`) and runtime bridge
- Run history provider protocol with file and in-memory reference implementations
- Event consumer protocol with reference trend consumer
- Profile keys: `observability_providers`, `run_history_provider`, `event_consumers`, `observability_delivery`
- Conformance suites: observability, run history, event consumer, production profile
- Medallantic M6: `explain_medallion_plan`, lifecycle views, medallion profile templates
- CLI `etlantic report query` and workspace file run history (`.etlantic/history/`)
- What's New / Migration / Exit Gate 0.34 documentation

### Changed
- Official package versions align at 0.34.0; plugins require `etlantic>=0.34.0,<0.35`
- Terminal run reports may include `metadata.observability` event/delivery summary
- `etlantic reliability quality-trends` uses event consumer summary when `--values` omitted

### Fixed
- Selected-engine ``PMPLUG402`` now maps validate/plan CLI exit to ``TRUST_FAILURE`` (sibling discovery 402s remain non-blocking)
- Plugin registry descriptors retain package identity (``distribution_name`` / ``package``) after authorize-before-load
- Manual ``register_*_plugin`` refuses unauthorized overlays when a production profile is active
- Missing selected engines under production emit blocking ``PMPLUG404`` trust diagnostics
- Plan snapshots with ``name=production`` require ``security_mode=production``
- PySpark provider/plugin advertise Delta/merge capabilities only when delta-spark is importable; declared cache/checkpoint failures fail closed
- Medallantic missing run/step statuses fail closed; live IR scrubbing covers non-metadata secret keys; ``transform_ref`` imports support deny-by-default allowlists
- ``FileStateStore`` uses locked read-modify-write; schema/run history can fail closed on corrupt durable files
- Schema-drift / trust failures cannot be CONTINUE/SKIP'd; plan ``allow_trusted_sql`` is intersected with the live profile
- Polars/Pandas advertise only append/overwrite write extras; Airflow fails closed on non-cron/manual schedules; keyring capability ads match sync lookup; mounted-file secret errors omit absolute paths
- Structured run logs can fan out to observability providers via runtime bridge
- `durable_audit` fail-closed on run-history event append (not only terminal reports)
- File run-history JSONL append uses locked O_APPEND (cross-process safe; no full-file read)
- Run history query/list: orphan reports, idempotent `create_run`, UTC filter coercion, sorted report queries
- Production conformance requires `run_history_provider` when `observability_delivery` is `durable_audit`
- `etlantic report query` supports `--since` / `--until`; documentation drift for 0.34 M6 surfaces
- SQL temp-table materialization validates column identifiers (injection fail-closed)
- Asset URLs with userinfo credentials rejected from plan bindings (secret-free plans)
- Builtin allowlist exemption no longer trusts third-party `engine`/`name` spoofs
- Mounted-file secrets confined under mount root (path traversal fail-closed)
- Schema history scans field metadata, denies list-of-row bags, and uses collision-resistant subject paths
- Manual `register_*_plugin` overlays gated by production `plugin_allowlist`
- Non-blocking `PMPLUG402` ignored consistently in trust exit, validation discovery, run/compile/doctor, and transform dispatch
- Quality membership fails closed on null; uniqueness skips null keys and rejected rows
- `PipelinePlan.from_dict(verify=True)` requires a non-empty fingerprint; production snapshot mode/name consistency checked
- Airflow artifact secret scan covers every strategy; plan snapshots keep only referenced secrets
- Airflow reference operator fails closed unless `ETLANTIC_AIRFLOW_REFERENCE_STUB=1`
- `etlantic run` maps validation/trust failures to documented exit codes; compile uses trust exit
- Nested pipeline definitions upgrade/validate to `etlantic.pipeline/1`
- Contract-diff toolkit exceptions fail closed as BREAKING drift
- `--quiet` still emits JSON/SARIF on trust gate failures
- Outbound emit payloads redacted in reports; authoring/redaction vocab includes `pwd` / AWS access keys
- Step `TimeoutError` is not retried under the default retry policy
- Spark cancel surfaces failures; PySpark advertises Delta only when `delta` is importable
- Strict production extension metadata rejects nested secret-like keys

## [0.33.0] - 2026-07-29

### Added
- SQL dialect Tier A/B matrix in `etlantic-sql` (SQLite + PostgreSQL live; others gated)
- PostgreSQL `sql_merge` via `INSERT … ON CONFLICT`; model DDL + primary-key validation
- Lazy SQL transform claim + planner `sql_fusion` / transaction-scope evidence
- Async SQLAlchemy execution path when the URL uses an async driver
- Medallantic live `from_sql_pipeline_builder` bridge (`PMSQ350+`)
- Moltres / SQLAlchemy-native rules (`quality.moltres_expr`, `MDL132`)
- `etlantic.testing.run_sql_builder_differential_suite` with classified fixtures
- What's New / Migration / Exit Gate 0.33 documentation

### Changed
- Official package versions align at 0.33.0; plugins require `etlantic>=0.33.0,<0.34`
- `SqlTransformCompiler` advertises `lazy=True` alongside `eager=True`

### Fixed
- Authorize plugins on package/distribution identity only (engine short names can no longer spoof allowlists); emit `PMPLUG403` for invalid pins in the authorize path; exempt builtins in lifecycle policy
- Validation/`ensure_plugins` no longer fail closed on sibling `PMPLUG402` denials for non-selected engines; CLI trust exit ignores non-blocking 402s
- `PlanningContext` rediscovers and clears non-builtin plugins when the profile allowlist key changes; empty production discovery clears the registry
- Spark cancel treats capability-probe failures as not advertised (fail closed)
- Preserve `env` builtin registry stubs across profile switches; `etlantic profile validate` maps all `PMPLUG*` errors to trust exit
- Portable SQL transform compiler enables merge compile for PostgreSQL dialects; Cockroach-via-`postgresql://` URLs classify as Tier B without merge
- SQL hello PyPI companion reuses the plugin engine (`examples/sql_hello_pypi.py`); production sample banner/links/docs gates hardened
- SQL merge capability tests are dialect-aware; dialect-tier suite skips cleanly without SQLAlchemy so non-SQL CI jobs collect

### Upgrade notes
- Pin core and official plugins to `==0.33.0` (matching 0.x minors).
- Read [Migration 0.32 → 0.33](docs/11_DEVELOPMENT/MIGRATION_0_32_TO_0_33.md)
  and [What's new in 0.33](docs/01_GETTING_STARTED/WHATS_NEW_0_33.md).
- SQL merge requires PostgreSQL (`sql_merge`); SQLite remains fail-closed.
- Prefer `medallantic.migrate.sql.from_sql_pipeline_builder` for live SQL builders.
- Moltres-only rules fail closed with `MDL132` until an evaluator exists.
- Out-of-monorepo plugins: bump core pins to `etlantic>=0.33.0,<0.34`
  (see `etlantic-plugin-echo` 0.33.0).

## [0.32.0] - 2026-07-28

### Added
- `storage.delta.*` capability extras and plan-time fail-closed `PMPLAN440` / `PMPLAN441`
- Catalog mutation policy (`PMCAT100`) and JDBC/asset binding refs
- Spark protocol: cancel, storage ops, cache/checkpoint points, logical-step identity
- `etlantic-pyspark` Delta optimize/vacuum/history/time-travel/schema-evolution paths
- Medallantic live `from_pipeline_builder` bridge and Column-rule path (`MDL130`)
- Real PySpark df→df callable transforms; fluent builder `rules=` on silver/gold
- Runtime map `implementation_overrides` + `invalidation`
- `etlantic.testing.run_sparkforge_differential_suite` with classified fixtures
- What's New / Migration / Exit Gate 0.32 documentation

### Changed
- Official package versions align at 0.32.0; plugins require `etlantic>=0.32.0,<0.33`
- Medallantic Delta capability map uses fine-grained `storage.delta.*` extras
- `etlantic-pyspark` claims `dataframe=True` (lazy implication honesty)

### Fixed
- Spark region compile/execute records cache points and logical identities

### Upgrade notes
- Pin core and official plugins to `==0.32.0` (matching 0.x minors).
- Read [Migration 0.31 → 0.32](docs/11_DEVELOPMENT/MIGRATION_0_31_TO_0_32.md)
  and [What's new in 0.32](docs/01_GETTING_STARTED/WHATS_NEW_0_32.md).
- Local / Polars / Pandas-only adopters can skip most M4 Spark/Delta notes;
  re-pin plugins and continue.
- SparkForge / Delta users: prefer
  `medallantic.migrate.sparkforge.from_pipeline_builder` for live builders;
  expect `storage.delta.*` capability negotiation (`PMPLAN440` / `PMPLAN441`).
- Non-portable Column rules need `quality.pyspark_column` or fail closed
  (`MDL130`).
- Out-of-monorepo plugins: bump core pins to `etlantic>=0.32.0,<0.33`
  (see `etlantic-plugin-echo` 0.32.0).

## [0.31.0] - 2026-07-28

### Added
- `IncrementalStrategy` and `StateStore` (`MemoryStateStore`, `FileStateStore`) with commit-after-materialization
- `WriteMode.SKIP_IF_EXISTS` and write capability extras (`write.*`) with `PMPLAN430` / `PMPLAN431`
- Run-intent write-mode resolution (VALIDATE / INITIALIZE / INCREMENTAL / REFRESH / STANDARD)
- Lifecycle policy helpers and Medallantic bronze/silver/gold facade defaults
- Medallantic live `transform_ref` execution (`medallantic.callables`) composed with quality gates
- `enforce_accept_rates` / `MDL120` for threshold failures
- `etlantic.testing.run_lifecycle_conformance_suite`
- What's New / Migration / Exit Gate 0.31 documentation

### Changed
- Official package versions align at 0.31.0; plugins require `etlantic>=0.31.0,<0.32`
- Local memory storage honors `append` and `skip_if_exists` write modes
- Medallantic `skip`/`ignore` write modes map to `SKIP_IF_EXISTS`
- Orchestrator records `state_transitions` on run reports when state commits

### Fixed
- VALIDATE / no-write runs no longer advance incremental state

## [0.30.0] - 2026-07-28

### Added
- Provisional `etlantic.quality/1` portable quality-expression AST + JSON Schema
- `etlantic.quality` helpers: serialize/fingerprint, ContractModel mapping, analyze, evaluate, `make_quality_gate`
- Plan metadata for quality gates (cost, capabilities, fallback evidence, `validation_boundary`)
- Plan-time fail-closed diagnostics `PMPLAN420` / `PMPLAN421` for unsupported required quality capabilities
- Portable quality conformance suite: `etlantic.testing.run_quality_conformance_suite`
- Polars / Pandas advertise portable quality rule capabilities
- Medallantic rule DSL (`parse_rules_shorthand`) and real quality-gate lowering (replaces `MDL110` passthrough)
- Medallantic `evaluate_accept_rates` for layer threshold comparison
- What's New / Migration / Exit Gate 0.30 documentation

### Changed
- Official package versions align at 0.30.0; plugins require `etlantic>=0.30.0,<0.31`
- Local stub registry advertises portable quality capabilities for plan-time negotiation
- Medallantic bronze steps with rules insert `{name}__ingest` + gate nodes
- Surface inventory marks `etlantic.quality/1` provisional and adds `quality` lazy namespace

### Fixed
- Quality gate factory resolves ContractModel port types and invalid-role rejected outputs
- Name-only `custom_contract` rules fail closed at evaluate time (no silent pass)
- Quality capability asserts run before native implementation selection so SQL/PySpark profiles emit `PMPLAN420`/`421` instead of `PMPLAN302`
- Plan metadata recomputes quality fingerprints so embedded hashes cannot drift
- Optional `required=False` quality rules skip rejection while recording soft diagnostics
- Regex / range / length DSL evaluation no longer crashes the gate on bad inputs
- `field_constraints_dict` projects `nullable`, compare ops, and composite `unique_fields`
- Medallantic quality gates attach `{step}__rejected` sink Loads (invalid→sink wiring allowed)
- PySpark stops advertising `invalid_row_separation` without `dataframe`
- Surface / agent / capability / diagnostics catalogs reflect `etlantic.quality` for 0.30

## [0.29.0] - 2026-07-28

### Added
- Medallantic M1 native authoring: `MedallionPipeline`, `MedallionBuilder`, `Bronze` / `Silver` / `Gold`
- Declarative medallion documents and stable `MDL1xx` construction/graph diagnostics
- `medallantic.migrate.sparkforge` migration namespace (shared lowering with native path)
- Facade conformance kit: `etlantic.testing.run_facade_conformance_suite`
- Definition extension-bag validation on codec write; namespaced facade extensions copied onto plans
- `etlantic.extensions.facade_provenance` helper
- What's New / Migration / Exit Gate 0.29 documentation

### Changed
- Official package versions align at 0.29.0; plugins require `etlantic>=0.29.0,<0.30`
- Medallantic IR adapter reuses shared `lower_document` path
- [Facade packages](docs/11_DEVELOPMENT/FACADE_PACKAGES.md) documents the shipped conformance kit
- Plugin lifecycle allowlists accept engine/entry short names consistently with trust filtering
- Discovery APIs expose `last_diagnostics` when trust blocks loads

### Fixed
- Medallantic `LoweringError` / `AdapterError` codes now match the primary ERROR diagnostic
- Native `MedallionDocument.from_dict` preserves explicit `0.0` accept rates
- Unknown medallion layers fail closed (`MDL107`) instead of coercing to gold
- Validation policies are unique per pipeline name + schema (no same-schema clobber)
- Document metadata and step description/tags survive definition extensions
- SparkForge IR cycle detection handles `"step.result"` source references
- `etlantic_sparkforge` submodule imports (`adapt` / `ir` / `compat` / `reports` / `runtime_map`)

## [0.28.0] - 2026-07-28

### Added
- Quadruple-minor burn-in fixtures (`v0_27/`) proving 0.27→0.28 upgrade without wire-schema reset
- Plugin SDK `/1` freeze for core protocol families; `scripts/check_protocol_freeze.py` CI gate
- [External plugin feedback](docs/11_DEVELOPMENT/EXTERNAL_PLUGIN_FEEDBACK.md) record for freeze closure
- Third-wave root alias removals (`sql`, `profile`, `lifecycle` clusters)
- Final `etlantic-sparkforge` compatibility redirect wheel (depends on `medallantic`)
- [Facade packages](docs/11_DEVELOPMENT/FACADE_PACKAGES.md) release category documentation
- What's New / Migration / Exit Gate 0.28 documentation

### Changed
- Official package versions align at 0.28.0; plugins require `etlantic>=0.28.0,<0.29`
- Plugin SDK `/1` declared **frozen** in 0.28.0 (was re-scoped in 0.27)
- `medallantic` classified as facade package in release gates
- Wire schema ranges document the quadruple-minor window

## [0.27.0] - 2026-07-28

### Added
- Triple-minor burn-in fixtures (`v0_26/`) proving 0.26→0.27 upgrade without wire-schema reset
- Extended CI gates for pipeline and sibling codec burn-in across `v0_24`, `v0_25`, and `v0_26`
- What's New / Migration / Exit Gate 0.27 documentation
- `medallantic` package (replaces `etlantic-sparkforge`) for SparkForge migration adapter

### Changed
- Official package versions align at 0.27.0; plugins require `etlantic>=0.27.0,<0.28`
- Plugin SDK `/1` freeze re-scoped to 0.28+ (external feedback blocker remains open)
- Wire schema ranges document the triple-minor window
- Rename `etlantic-sparkforge` to `medallantic`; optional extra is `etlantic[medallantic]`

### Fixed
- Close `Profile.__init__` metadata validation bypass for production profiles
- Validate plan graph, region, boundary, and artifact metadata on decode; apply
  production strict mode from `profile_snapshot.security_mode`
- Whitelist first-party core plan metadata keys to stop spurious bare-key warnings
- Map `etlantic plan` trust-phase failures to exit code 11 (`TRUST_FAILURE`)
- Correct plugin pin in Migration 0.24→0.25 guide
- Refresh active docs, issue template, and examples README to 0.27.0
- Harden `check_removed_root_imports` and extend `check_docs` stale-pin detection
- Update burn-in script docstrings for `v0_26` coverage

### Removed
- Second-wave root facade aliases: reliability declarations (12), schema_drift helpers (8), registry descriptors (6); import from owning modules per Migration 0.26→0.27
- `etlantic-sparkforge` distribution (superseded by `medallantic`)

## [0.26.0] - 2026-07-27

### Added
- Dual-minor burn-in fixtures (`v0_25/`) proving 0.25→0.26 upgrade without wire-schema reset
- Extended CI gates for pipeline and sibling codec burn-in across `v0_24` and `v0_25`
- What's New / Migration / Exit Gate 0.26 documentation

### Changed
- Official package versions align at 0.26.0; plugins require `etlantic>=0.26.0,<0.27`
- Plugin SDK `/1` freeze re-scoped to 0.27+ (external feedback blocker remains open)
- Wire schema ranges document dual-minor window and authoring-catalog N/A rationale

### Fixed
- Preserve manually registered plugins across ``ensure_plugins_for_profile`` discovery replaces (SQL/dataframe tests and app wiring)
- Allowlist denials (`PMPLUG402`) of sibling packages no longer abort discovery when other allowlisted plugins load
- Replace (not merge) runtime plugin maps and prune non-builtin registry entries on profile switch so tighter allowlists cannot leave unauthorized plugins resident
- Authorize plugins only on distribution/package identity (not engine/entry short names); exempt in-tree builtin stubs from package allowlist checks; drop `"local": null` from prod examples
- Compiler/differential tests import `RunStatus` from `etlantic.runtime` after 0.26 root removal; cover all `_REMOVED_0_26` symbols and guard tests/examples imports in CI
- `discover_planning_plugins` returns immediately on empty-production `PMPLUG401` (no duplicate trust loops)
- `require_plugin_probe` fail-closes in all security modes (not only production)
- Warn when programmatic `security_domain` looks like production but `security_mode` is not
- CLI maps `timed_out` / `cancelled` run status to exit `13` (`EXECUTION_FAILURE`); reserve `14` for partial success
- Validate trust exit selection includes all `plugin_*` phases (authorize/evaluate/load/probe)
- Split overloaded `PMPLUG421` into `PMPLUG421`–`PMPLUG424` (group / spark provider / transform compiler / load)
- Demoted-alias warnings point at Migration 0.25→0.26 and removal candidates
- Docs/check_docs pin hygiene for 0.26 (LEARNING_PATH, CONFIGURATION_TODAY, FIRST_PIPELINE, COMPATIBILITY, EXCEPTIONS, API_REFERENCE, FAQ, SURFACE_INVENTORY, RELEASE_PROCESS)
- DataFusion stub messages retargeted to 0.26.0; PySpark local provider declares `etlantic.spark/1` protocol
- Log (debug) instead of silent swallow on legacy plan decode and plugin compatibility distribution scan failures

### Removed
- First-wave root facade aliases: protocol consts, exceptions, storage, runtime, interchange helpers (37 symbols); import from owning modules per Migration 0.25→0.26

## [0.25.1] - 2026-07-27

### Fixed
- Skip plugin discovery/load when static manifest load fails (fail closed)
- Discovery helpers fail closed on trust ERROR diagnostics instead of returning loaded plugins silently
- Reject empty/whitespace `security_mode` (no silent coerce to development)
- Stop inferring `staging` profile names as `security_mode=production`
- Deduplicate empty production allowlist `PMPLUG401` across discovery groups (CLI no longer emits 7× copies)
- `etlantic profile validate` maps empty production allowlist (`PMCFG200`) to exit `11` (`TRUST_FAILURE`)
- Enrich `PMPLUG401` / `PMCFG200` remediation messages (allowlist + prod.example.json guidance)
- Split colliding `PMEXEC420`/`421`/`430`/`431` into distinct storage vs engine codes
- Trust failures raise coded `PipelineValidationError` / `PipelineExecutionError` instead of bare `ETLanticError`
- Canonicalize plugin package names for manifest identity (`PMPLUG414`)
- Invalid allowlist version pins emit `PMPLUG403` instead of looking like denials
- Callable `plugin.info` resolved in dataframe discovery/register paths
- Transform compiler discovery propagates allowlist trust diagnostics

### Changed
- Official package versions align at 0.25.1; plugins still require `etlantic>=0.25.0,<0.26`
- Docs: Troubleshooting splits `PMPLUG401` vs `PMPLUG402`; PRODUCTION_PROFILES bare-production fence clarified; CONTRIBUTING CI markers include `datafusion`; check_docs patch-pin hygiene

### Upgrade notes
- Pin core and official plugins to `==0.25.1`.
- No authoring API breaks from 0.25.0; diagnostic code splits may require CI allowlists that matched colliding `PMEXEC42x`/`43x` meanings to update.

## [0.25.0] - 2026-07-27

### Added
- Compatibility burn-in golden fixtures for `etlantic.pipeline/1` (0.24→0.25 old↔new reader/writer)
- CI gate `scripts/check_pipeline_codec_burn_in.py` (fingerprint lock + load verify)
- Cross-artifact burn-in matrix: plan, run_report, profile, capabilities, interchange
- Wire schema ranges and unsupported downgrade documentation
- Plugin SDK `/1` freeze decision record (remaining blockers published; not frozen)
- Published 0.37 stable-foundation removal candidates inventory (no removals executed)
- Docs: What's New 0.25, Migration 0.24→0.25, Exit Gate 0.25
- Docs adoption hubs: Learning path, Profiles hub, Portable hub, Security howto,
  Documentation audit 0.25

### Changed
- Official package versions align at 0.25.0; plugins require `etlantic>=0.25.0,<0.26`
- Protocol evolution status documents freeze blockers carried to 0.26
- Docs adoption remediation: green-path honesty, Learn/How-to/Maintainers nav,
  Evaluate packet roles, Capabilities/Security/SUPPORT trust stamps, freeze
  glossary, SURFACE_INVENTORY completion, EXCEPTIONS hierarchy, `deep_freeze`
  honesty, expanded plan docstring gate, contributor `mkdocs serve` notes

### Fixed
- Resolve dataframe `plugin.info` as property or callable so Polars/Pandas
  ownership uses advertised `thread_safe` (default COPIED when caps missing)
- Manifest parsing with `verify_digest=True` fails closed when `digest` is absent
- Split colliding `PMEXEC411`/`PMEXEC412` meanings: callable missing writer/reader
  are now `PMEXEC415`/`PMEXEC416`; document resilience codes `408`–`414`
- SQL keyed `dtcs:deduplicate` fails closed instead of silently emitting full-row
  `DISTINCT`
- `etlantic init` / `write_minimal_etlantic_toml` stamps current `__version__`
- `etlantic validate` exits `11` (`TRUST_FAILURE`) for trust/discovery errors
- Reliability CLI commands use documented exit codes
- `PipelineDefinition.from_dict` requires an explicit `schema`
- Interchange burn-in golden aligns with `select_mechanism`; sibling burn-in
  fingerprint/content gate added
- `VALIDATION_PHASES` includes `plugin_discovery`; `deep_freeze` freezes sets
- Stale 0.24 install pins / current-minor docs stamps; `check_docs` hardening

### Upgrade notes

- Pin core and official plugins to `==0.25.0` (matching 0.x minors).
- Read [Migration 0.24 → 0.25](docs/11_DEVELOPMENT/MIGRATION_0_24_TO_0_25.md)
  and [What's new in 0.25](docs/01_GETTING_STARTED/WHATS_NEW_0_25.md).
- Production fail-closed trust still requires `security_mode="production"` plus
  a non-empty `plugin_allowlist` (not the profile name alone).

## [0.24.0] - 2026-07-27

### Added
- Canonical `PipelineDefinition` and lossless `etlantic.pipeline/1` codecs/schema
- Functional authoring builders (`etlantic.authoring`) with class/JSON parity
- Definition-aware lifecycle: validate, plan, run, inspect without originating classes
- CLI JSON TARGET support and `etlantic generate --kind definition`
- Authoring catalog, immutable `EditCommand`s, structural/plan previews
- Transport-neutral `etlantic.service.AuthoringService`
- Optional `etlantic-fastapi` reference adapter + OpenAPI fixture
- Docs: What's New 0.24, Migration 0.23→0.24, Exit Gate 0.24, programmatic authoring guide
- Docs adoption: cheatsheet, runnable `examples/pipeline_definition_json.py`, Diátaxis nav cleanup

### Changed
- Official package versions align at 0.24.0; plugins require `etlantic>=0.24.0,<0.25`
- Lazy namespaces include `authoring` and `service`
- Surface inventory lists `etlantic.pipeline/1` and authoring catalog as wire-stable

### Fixed
- Fail-closed definition codecs, fingerprint verify, and secret filtering
- Definition/class lifecycle parity (cycles, nested graphs, policy allowlists, callable registry)
- Sync-honest FastAPI reference `submit_run` / `cancel_run` semantics

### Upgrade notes

- Pin core and official plugins to `==0.24.0`.
- Read [Migration 0.23 → 0.24](docs/11_DEVELOPMENT/MIGRATION_0_23_TO_0_24.md)
  and [What's new in 0.24](docs/01_GETTING_STARTED/WHATS_NEW_0_24.md).
- Prefer `import etlantic as etl` and programmatic authoring via
  `PipelineDefinition` / `etlantic.authoring` when not using classes.

## [0.23.0] - 2026-07-27

### Added
- Performance benchmark baselines (`etlantic.benchmark_baseline/1`) and CI gate (`scripts/check_benchmarks.py`)
- Public fault injection API (`etlantic.testing.faults`) with orchestrator/report/store hooks
- Interchange evidence reconciliation (`reconcile_interchange_evidence`, planned `evidence_refs`)
- Resilience test suites: fault injection, cancellation, timeout, store concurrency, write-mode matrix
- Real PySpark CI job and Airflow import version matrix (`airflow-runtime` dependency group)
- Docs: What's New 0.23, Migration 0.22→0.23, Exit Gate 0.23

### Changed
- Artifacts, schema history, and reliability file providers use `SafeIoPolicy` consistently
- Orchestrator terminal paths persist exactly one report; publication/report gap → `PMEXEC410`
- Official package versions align at 0.23.0; plugins require `etlantic>=0.23.0,<0.24`
- Fault injection requires `ETLANTIC_FAULT_INJECTION` to arm (in-process specs alone no longer fire)
- DataFusion experimental stub advertises no graduated dataframe/Arrow/lazy capabilities

### Fixed
- Cancel/timeout reports finalize incomplete steps (no leftover `running`/`pending`)
- CLEANUP fault no longer skips real cleanup or the terminal report (`PMEXEC412`)
- `FileReportStore` writes durably before updating the in-memory index (no false SUCCEEDED)
- Attempt cleanup failures after a successful step body no longer trigger retries (`PMEXEC414`)
- Resource scope cleanup attempts every entry before aggregating failures
- PMEXEC410 recovery marks `report_persisted` when the failed report write succeeds
- `step_failed` callback faults are isolated (`PMEXEC413`)
- Unsupported `CancellationPolicy` knobs fail closed (`PMEXEC411`)
- `etlantic plugin compatibility` discovers packaged manifests and honors allowlist pins
- Compatibility reports reject entry protocols that do not match core (even under `*`)
- Trust failures with `--format sarif` emit SARIF instead of JSON
- Step report metadata is redacted; `profile migrate` infers production `security_mode`
- `SafeIoPolicy.from_dict` rejects invalid symlink/overwrite policy enums
- Builtin stub registry versions track core `__version__`

### Upgrade notes

- Pin core and official plugins to `==0.23.0`.
- Read [Migration 0.22 → 0.23](docs/11_DEVELOPMENT/MIGRATION_0_22_TO_0_23.md)
  and [What's new in 0.23](docs/01_GETTING_STARTED/WHATS_NEW_0_23.md).
- Fault injection requires `ETLANTIC_FAULT_INJECTION` to arm.

## [0.22.0] - 2026-07-21

### Added
- Capability-driven engine identity (`ExecutionFamily`) — third-party engines no longer need first-party name privileges
- Versioned capability vocabulary `etlantic.capabilities/1` with implication/conflict validation
- Typed protocol metadata: `ExecutionContextMeta`, `CompileArtifactMeta`, extension-namespace bags
- Public Spark conformance suite (`run_spark_conformance_suite`) and capability-truthfulness helpers
- `etlantic plugin compatibility` report CLI (`PMPLUG44x` findings)
- Curated `import etlantic as etl` root facade with lazy namespaces and typed stub
- Out-of-monorepo reference plugin `etlantic-plugin-echo` + CI clone/conformance workflow
- Docs: What's New 0.22, Migration 0.21→0.22, Exit Gate 0.22, Capability Vocabulary, Protocol Evolution

### Changed
- Official package versions align at 0.22.0; plugins require `etlantic>=0.22.0,<0.23`
- Root `__all__` slimmed to curated stable symbols + lazy namespaces; demoted specialists warn once
- Dataframe conformance suite is capability-driven (removed `engine == "pandas"` special cases)
- Surface inventory bidirectional ownership check for curated facade
- Plugin SDK docs recommend `import etlantic as etl`

### Deprecated
- Specialist root imports demoted to 0.x compatibility aliases (prefer owning namespace / lazy attribute)

## [0.21.0] - 2026-07-20

### Added
- Cohesive CLI journey: `init`, `doctor`, `profile validate/show/diff/migrate`
- Durable workspace defaults (`.etlantic/reports`, `.etlantic/artifacts`) with `--ephemeral` escape hatch
- Optional `etlantic.toml` project config with `profiles/` fallback
- Structured profile assets (`json://path` and `{provider, location}` objects)
- `plan diff` and human `plan explain --format human`
- `report list`; cross-invocation `report show`/`export` from file store
- Global CLI options: `--verbose`, `--quiet`, `--color`, `--non-interactive`, `--workspace`
- Documented exit code taxonomy; mutation preamble via `--preview`
- Library modules: `etlantic.workspace`, `etlantic.project`, `etlantic.bindings`
- Docs: What's New 0.21, Migration 0.20→0.21, Exit gate 0.21, Best Practices, Documentation Audit 0.21

### Changed
- Official package versions align at 0.21.0; plugins require `etlantic>=0.21.0,<0.22`
- Legacy profile JSON `bindings` fail closed unless `--accept-legacy-bindings`
- Production profile metadata uses strict extension namespaces by default
- `FileReportStore` exported from `etlantic.reports`
- CLI refactored into shared `CliContext` with unified output helpers
- Docs golden path converges on `etlantic init`; in-memory demo renamed to `examples/memory_customers.py`
- Public agent CLI list includes `init`, `doctor`, and `profile`

### Fixed
- SECURITY / SUPPORT version banners and plugin-minor troubleshooting advice
- Evaluator / Production Readiness / Security residual-risk narrative consistency
- README CLI default profile (`development`) and docs build link to AGENTS.md

### Deprecated
- `reliability plan-diff` in favor of `plan diff`

### Migration
- See `docs/11_DEVELOPMENT/MIGRATION_0_20_TO_0_21.md`

## [0.20.0] - 2026-07-19

### Added
- Pre-import plugin lifecycle: `discover → evaluate → authorize → load`
- Static `etlantic.plugin_manifest/1` for first-party plugins (no entry-point import)
- Optional isolated capability probe with time/output budgets
- Unified `SafeIoPolicy` (roots, symlinks, special files, atomic writes, locks, digests)
- Artifact/cache isolation dimensions: tenant, environment, authorization, run, contract version
- Default-deny `OutboundPolicy` for Emit/webhook/remote-reference destinations
- Unsafe-serialization prohibitions (`PMSEC060`)
- Versioned `SecurityEvent` schema (`etlantic.security_event/1`) for auth/I/O/network/probe
- Profile fields: `tenant`, `environment`, `safe_io`, `outbound`, `require_plugin_probe`
- Release SBOM digests, GitHub build provenance attestations, OIDC-preferred publish
- Docs: What's New 0.20, Migration 0.19→0.20, Exit gate matrix

### Changed
- Official package versions align at 0.20.0; plugins require `etlantic>=0.20.0,<0.21`
- Discovery modules authorize before `ep.load()`; production requires manifests
- Report and schema-history file stores write through `SafeIoPolicy`

### Fixed
- Allowlisted plugins can no longer be selected after an unauthorized import
- Cross-domain artifact/cache identity collisions fail closed

### Migration
- See `docs/11_DEVELOPMENT/MIGRATION_0_19_TO_0_20.md`

## [0.19.0] - 2026-07-19

### Added
- Contract and configuration freeze: deep plan immutability helpers, fingerprint
  verification at deserialize/compile/run trust boundaries
- Explicit `Profile.security_mode` (`development` | `test` | `production`)
- Strict named profile resolution with `--allow-adhoc-profile` / `allow_adhoc_profile`
- Diagnosed legacy profile JSON `bindings` loads; nested wire schema tightening
- Extension metadata namespace/budget helpers; public surface inventory
- 0.x deprecation schedule for remaining provisional surfaces
- Optional experimental `etlantic-datafusion` package (non-blocking Gate B)

### Changed
- Official package versions align at 0.19.0; plugins require
  `etlantic>=0.19.0,<0.20`
- Production fail-closed trust/drift uses `security_mode == "production"` only
- Unknown bare profile names fail closed unless ad hoc is explicitly allowed
- Plan and run-report loaders reject missing or unknown wire `schema` values

### Fixed
- Nested plan-owned mappings can no longer be mutated after construction
- Tampered plan fingerprints fail before compilation or execution

### Migration
- See `docs/11_DEVELOPMENT/MIGRATION_0_18_TO_0_19.md`

## [0.18.0] - 2026-07-19

### Added
- Gate A versioned tabular interchange with immutable
  `etlantic.interchange/1` plan descriptors
- Capability-driven mechanism selection for Arrow C Data/C Stream, Arrow IPC,
  Parquet artifacts, and explicit records/native fallbacks
- Bounded fidelity, ownership, copy, cleanup, and run-report evidence models
- Polars↔Pandas cross-engine conformance coverage and public testing helpers
- What's New 0.18 and Migration 0.17 → 0.18

### Changed
- Cross-engine dataframe boundaries can be planned and validated independently
  of hard-coded engine-name pairs
- Stored 0.17 plans must be regenerated to obtain interchange descriptors
- Official package versions align at 0.18.0; plugins require
  `etlantic>=0.18.0,<0.19`
- Arrow-assisted conversion remains available only as a legacy best-effort
  helper; Gate A descriptors are the versioned contract

### Fixed
- Interchange execution now fails closed when a selected mechanism, fidelity
  bound, or ownership requirement cannot be honored
- Plan explain and runtime evidence consistently report Gate A selection and
  fallback decisions without embedding rows or secrets
- Spark MERGE/UPSERT fails closed when Delta is unavailable, `merge_keys` are
  missing, or `delta-spark` is not installed (no parquet overwrite fallback);
  the local orchestrator raises on Spark write error diagnostics
- Production schema-drift BLOCK uses the same production-profile detection as
  plugin trust (`prod` / `staging` / security-domain aliases)
- Schema history refuses row-like payloads in observation and schema metadata,
  on disk load, and in in-memory history
- CLI `generate --sqlmodel` emits real SQLModel source; `reliability freshness`
  fails closed without `--observed-age`; `diff` reports per-side load errors;
  `plugin info` honors profile allowlists and supports scheduler plugins
- Documentation, contributor checks, and ROADMAP status aligned for 0.18.0
  (including `asset=` authoring and current install pins)
- Restore `examples/quickstart.py` `run_example()` entry point required by CI

## [0.17.0] - 2026-07-19

ETLantic 0.17.0 is production/stable within the documented single-tenant
reference envelope. Experimental features and adopter-owned deployment,
compliance, and supply-chain controls remain outside that support claim. See
See `docs/11_DEVELOPMENT/MIGRATION_0_16_TO_0_17.md`.

### Added
- Graduated portable families on Polars and PySpark: string-advanced,
  conversion, statistics, window/1, complex-types, complex-values, reshape
- Executable rich-family public conformance fixtures and coverage enforcement
- `etlantic plugin list --kind transform_compiler` capability inventory
- `scripts/check_transform_compiler_drift.py` packaging/guide drift gate
- What's New 0.17 and Migration 0.16 → 0.17
- Example `examples/portable_wave17.py`

### Changed
- Window V1 authoring emits `portable-window/1` only (V2 functions stay V2)
- Complex-type accessors no longer force complex-values requirements; `explode`
  emits reshape only
- Transform-compiler discovery uses entry-point names as stable keys; validate,
  plan, and run all respect profile allowlists
- Distinct missing/invalid literals fail closed without `three_state_distinct`
- Explicit window frames and windowed aggregates fail closed at analyze
- SQL portable compiler advertises `lazy=False` and honors action `target`
- Package versions aligned at 0.17.0; plugins require `etlantic>=0.17.0,<0.18`

### Fixed
- Validate-path unfiltered transform-compiler discovery bypass of allowlists
- PySpark Wave 1/2 function inventory and lowering parity with matrix claims
- PySpark `explode` empty/null row parity (`explode_outer`)
- Polars multi-key rank truncation, bare rank placeholder, soft `to_integer`,
  and over-broad null-safe join `TypeError` fallback
- Pandas 2-arg `substr` first-row-only start index
- SQL analyze/execute gaps for predicate joins and byPosition
  `allowMissingColumns`
- Documentation and release-checklist drift for the published 0.17.0 support
  envelope (bounded production/stable posture, install pins, Prefect status,
  MkDocs navigation, and docs/release drift checks)

## [0.16.0] - 2026-07-19

### Added
- Optional `etlantic-prefect` `ExecutionScheduler` plugin (Prefect 3.x local MVP)
- `etlantic.scheduler_plugins` discovery and `Profile(orchestrator=...)` run dispatch
- Public `etlantic.testing.run_scheduler_conformance_suite`
- Migration guide 0.15 → 0.16

### Changed
- Removed public `Source` / `Sink` / `binding=` / `Profile(bindings=...)` /
  `RunRequest(binding_overrides=...)` authoring aliases (Gate A)
- Profile public JSON emits `assets` only; plan snapshots keep wire `bindings`
- Package versions aligned at 0.16.0; plugins require `etlantic>=0.16.0,<0.17`

### Fixed
- Embedded plugin/compiler `__version__` values that still advertised `0.15.0`
  (broke production allowlist pins and plan plugin metadata)
- Clear `AttributeError` migration messages for `etlantic.Source` / `etlantic.Sink`
- Prefect wave runner no longer blocks the event loop on sync `Future.result()`
- Host `run_id` is threaded through `SchedulingContext` into Prefect/local hosts
- Documentation, SECURITY support table, and release checklist drift after the
  0.16 ship (including Prefect in published package lists)

### Migration
- Prefer `Extract` / `Load` / `asset=` / `Profile(assets=...)`. See
  `docs/11_DEVELOPMENT/MIGRATION_0_15_TO_0_16.md`.
- Use `Profile(orchestrator="prefect")` only with `etlantic-prefect` installed.

## [0.15.0] - 2026-07-19

### Added

- Safe SQL Lowering: `etlantic-sql` portable transform compiler claiming
  kernel + `portable-relational/1`, lowering
  [DTCS](docs/04_TRANSFORMATIONS/DTCS.md) plans into typed
  `etlantic.sql/1` IR with bound parameters and `PMXFORM*` analyze findings
- Expanded SQL IR (joins, unions, group/order, CTEs, call/case/unary exprs)
  and dialect compiler coverage for the relational `/1` surface
- Public SQL portable conformance + Polars differential suite; portable SQL
  security corpus (no interpolation; trusted fragments forbidden)
- Built-in `LocalScheduler` (`etlantic.scheduler/1`) as the
  `Pipeline.run` / `arun` entrypoint; private scheduler conformance corpus;
  Prefect feasibility spike notes (package deferred to 0.16)
- Canonical `Extract` / `Load` / `asset=` authoring with warned
  `Source` / `Sink` / `binding=` compatibility through 0.16
- `Profile.assets` and `RunRequest.asset_overrides` (legacy aliases warned);
  fingerprint-stable bindings-only `profile_snapshot`
- `docs/01_GETTING_STARTED/WHATS_NEW_0_15.md` and SQL column in the portable
  compiler matrix

### Changed

- Package version set to 0.15.0 across core and optional plugins
- Official plugin dependencies bound to `etlantic>=0.15.0,<0.16`
- Clarified that advanced portable profile graduation remains **0.15
  continuation** (not part of this exit gate)

### Upgrade notes

- Pin `etlantic==0.15.0` and matching plugins. Prefer `Extract`/`Load`/
  `asset=` / `Profile.assets`. See
  `docs/11_DEVELOPMENT/MIGRATION_0_14_TO_0_15.md`.
- Portable SQL requires `etlantic-sql`; use
  `run_portable_transform_conformance_suite` for third-party SQL compilers.

## [0.14.0] - 2026-07-18

### Added

- `etlantic-pandas` portable transform compiler claiming kernel +
  `portable-relational/1` (eager-only, index-neutral) with
  `etlantic.transform_compilers` entry point `pandas`
- Public `etlantic.testing.portable_transform_conformance` suite with
  capability-selected fixtures and
  `run_portable_transform_conformance_suite`
- Hypothesis property tests for capability matching, null-aware boolean
  semantics, and compile fingerprint stability
- Expanded Polars ↔ Pandas differentials (Unicode/ordering, unequal-key joins)
- CI runs pandas compiler suites, public conformance for Polars/Pandas/PySpark,
  and three-engine differentials
- `python -m etlantic` entry via `src/etlantic/__main__.py`
- Profile JSON path loading for `--profile ./profiles/prod.json`
- `py.typed` markers for core and every official plugin package

### Fixed

- Durable `PipelineRunReport.from_dict` round-trips lineage, diagnostics,
  validations, schema observations, step timings, and duration
- Soft-skip no longer clears unrelated pending sibling branches; `CONTINUE`
  allows dependents while `SKIP` abandons only transitive consumers
- Step timeouts invoke failure callbacks / retry policy instead of bypassing them
- Profile JSON loading rejects plaintext secrets, missing `.json` paths, and
  unknown `with_updates` keys; string capability lists are not character-split
- Validate/plan/exec honor `plugin_allowlist` for selected engines and
  transform compilers (`PMPLUG402` when listed plugins are rejected)
- Pandas unequal-key joins preserve left columns named like `rightKey`;
  semi/anti use stable suffixes; cross joins use native `how="cross"`
- PySpark unequal-key joins rename colliding right keys before coalesce
- PySpark substring lowering passes integer bounds on real Spark as required by
  PySpark 3.x while preserving DTCS zero-based indexing

### Documentation

- Full 0.14 published-alpha docs overhaul: What’s New, migrations, pilot /
  production-profile / durable-reports cookbooks, compiler matrix, optional
  packages page, honest CLI/file-storage claims, and MkDocs nav restructure
- Marked roadmap 0.14 shipped; updated capabilities, Pandas, testing plugins,
  and compiler protocol docs for the public conformance SDK

### Changed

- Package version set to 0.14.0 across core and optional plugins
- Official plugin dependencies bound to `etlantic>=0.14.0,<0.15`
- `etlantic-pandas` requires `pandas>=2.2,<3` (matches `include_groups=`)

### Upgrade notes

- Pin `etlantic==0.14.0` and matching plugins. Extras pins use `==0.14.0`.
- Third-party transform compilers should run
  `run_portable_transform_conformance_suite` against their advertised claims.
- Pandas portable plans that previously required native `@implementation`
  under `portable_transform_policy="require"` now compile when they fit
  kernel + relational `/1`.

## [0.13.0] - 2026-07-18

### Added

- Polars compiler claims `dtcs:profile/portable-relational/1` (join, union,
  aggregate, sort, distinct, deduplicate, limit) with mode-exact `analyze()`
  findings and expression/action paths
- `etlantic-pyspark` `etlantic.transform_compilers` entry point claiming kernel
  + relational `/1`; native Column/DataFrame lowering with portable-path UDF deny
- Orchestrator support for `portable_compiled` Spark steps (provider session,
  outside region UDF fusion)
- Private Polars↔PySpark differential corpus and gated `real_pyspark`
  Catalyst/no-UDF acceptance marker
- Relational `/1`↔`/2` capability alias matching (metadata compatibility; no
  candidate `/2` extensions)

### Documentation

- Refined roadmap 0.13 into locked decisions + 0.13a (Polars relational) /
  0.13b (PySpark + differentials); deferred public conformance to 0.14
- Updated capabilities, compatibility, Polars/PySpark, and compiler protocol
  docs for shipped relational claims

### Changed

- Package version set to 0.13.0 across core and optional plugins

### Fixed

- PySpark portable joins coalesce unequal keys like Polars (drop right key cols)
- Join `collisionPolicy` fail-closed to `fail` only (suffix/coalesce deferred)
- PySpark `with_fields` replaces existing columns instead of duplicating them
- Polars `unionByName` aligns by name (and fills missing when allowed)
- Semi/anti joins no longer false-fail on non-key column name overlap
- PySpark `substr` uses 0-based portable offsets; `replace` is literal
- Empty Spark DataFrames use an empty `StructType` instead of `schema=None`
- Analyze rejects `with_fields` windows and `allowMissingColumns` on byPosition
- CI runs `polars_compiler`, `pyspark_compiler`, and portable differentials

### Upgrade notes

- Pin `etlantic==0.13.0` and matching plugins (`etlantic-polars`,
  `etlantic-pyspark`, …). Extras pins use `==0.13.0`.
- Portable join/union/aggregate/sort/dedupe/limit plans that failed planning in
  0.12 under `portable_transform_policy="require"` now compile on Polars and
  PySpark when they fit `portable-relational/1`.
- PySpark portable compilation forbids automatic UDF fallback; keep native
  `@implementation("pyspark")` when you need UDFs or unclaimed profiles.
- Public `etlantic.testing.portable_transform_conformance` remains deferred to
  0.14; private differential fixtures live under `tests/`.

## [0.12.0] - 2026-07-17

### Added

- `etlantic.transform-compiler/1` protocol types, discovery
  (`etlantic.transform_compilers`), and capability matching
- `Profile.portable_transform_policy` (`prefer` / `require` / `native`) with
  fail-closed unsupported diagnostics (`PMXFORM3xx`)
- `ImplementationDescriptor.kind` (`portable_compiled` | `native`) with
  embedded bounded IR, fingerprints, compiler identity, and fallback reason
- `plan explain` fields for compiler selection, IR fingerprint, and requirements
- Polars kernel compiler (`create_transform_compiler`) claiming
  `dtcs:profile/portable-relational-kernel/1` with `pl.Expr` / LazyFrame lowering
- Runtime path executing portable_compiled dataframe steps without a native
  transformation callable
- `examples/portable_polars_kernel.py` runnable portable kernel quickstart

### Documentation

- Refined roadmap 0.12: planning (0.12a) + Polars kernel-only compiler (0.12b);
  locked prefer policy, embedded IR, and 0.13/0.14 deferrals
- Marked compiler protocol and Polars kernel execution as shipped in 0.12
- Treated 0.12.0 as the published current line across guides, banners, support,
  navigation, migration, and examples
- Added Migration 0.11 → 0.12, maintainers / CODEOWNERS / issue+PR templates,
  and release smoke-before-publish ordering

### Changed

- Package version set to 0.12.0 across core and optional plugins
- Release publish paces only brand-new PyPI project creates (existing projects
  upload immediately) so partial releases can finish without multi-hour sleeps

### Fixed

- Polars lowering unwraps DTCS typed literals (avoid Struct `pl.lit` payloads)
- `concat_ws` / `round` / string search helpers require Python constants, not Expr
- Reject unclaimed `dtcs:cast` in kernel compiler (no silent no-op)
- Capability matching fail-closes on empty action/function claims
- Planner defers native auto-pick until after portable analyze (no phantom natives)
- Validate `require` policy analyzes portable IR instead of fail-opening on compiler presence
- Compiler `analyze` unions plan-derived requirements; compile collects parameter fieldRefs
- Warn when multiple transform compilers register the same engine
- Accept authored DTCS op names (`not_eq`/`subtract`/`multiply`/`divide`, unary `expr`)
- Registry natives no longer bypass prefer/require portable analyze
- Window metadata on kernel plans fail-closed (profile + runtime reject)
- Project expression fields require aliases; authoring mints `_col_N` when missing
- Output schemas preserve contract field types when subsetting by `schema_fields`
- Runtime resolves planned `compiler_name`/`version`; portable_compiled requires dataframe engine

## [0.11.0] - 2026-07-17

### Added

- `@Transformation.portable` symbolic authoring over `etlantic.transform`
  (`FrameExpr`, `ColumnExpr`, `functions as F`, `Window`, complex/lambda helpers)
- Emission of validated, fingerprint-stable `dtcs.transform-plan/2` plans for
  Portable Relational and Rich Portable Analytics profile families
- `Transformation.to_transform_plan()` / `portable_fingerprint()` APIs
- `PMXFORM` authoring diagnostics and definition budgets
- Golden portable fixtures under `tests/fixtures/portable/`

### Fixed

- Portable join/union/set-ops no longer drop sibling actions via colliding
  `aN_*` IDs; unequal ID collisions fail closed (`PMXFORM210`)
- `sort` / `orderBy` / `Window.orderBy` treat bare strings as fieldRefs, not
  string literals
- Window metadata survives wrappers such as `F.to_string(... .over(w))`
- `to_transform_plan()` returns a deep copy so callers cannot mutate the cache
- COM parameter types map from `Parameter` annotations (not always `string`)
- Window frame bounds coerce expression nodes to JSON-safe values
- Production `plugin_allowlist` enforced on validate / run / compile; bare
  version pins accepted as `==version`; `plugin list` exits non-zero on ERROR
- Declared vs observed schema type aliases (`int`/`integer`, …) no longer
  report false breaking drift
- Planner and SparkForge adapter metadata versions track 0.11.0

### Documentation

- Marked portable authoring as shipped in 0.11; compilers remain 0.12–0.15
- Refined roadmap 0.11 to full authoring scope and marked the milestone shipped
- Rolled current-facing docs and install pins from 0.10 → 0.11; hardened
  `scripts/check_docs.py` stale-version gates
- Adoption pass: portable authoring SSOT, Current 0.11 nav, Quickstart CLI
  continuation, Migration 0.10→0.11, Ops Pilot, FAQ positioning, transform API
  / CLI gaps, check_docs gates

### Changed

- Package version set to 0.11.0 across core and optional plugins
- Raised the DTCS toolkit dependency floor from 0.12 to 0.13 (carried from
  unreleased 0.10 docs integration)

## [0.10.0] - 2026-07-17

### Added

- Optional `medallantic` migration adapter (IR → Pipeline / Profile)
- SparkForge debug/run-mode mapping to `RunSelection` / `RunIntent` / `DebugSession`
- SparkForge-shaped result normalization to `PipelineRunReport` with redaction
- Write / Delta capability compatibility helpers (fail closed)
- Representative ecommerce IR fixture and semantic parity suite
- Migration guide `docs/11_DEVELOPMENT/MIGRATION_0_9_TO_0_10.md`
- Runnable docs guides for Airflow compile and SparkForge adapter
- Docs status SSOT via CAPABILITIES + expanded `scripts/check_docs.py` guards

### Changed

- Package version advances to 0.10 (SparkForge Migration Preview)
- Plugin packages require `etlantic>=0.10.0,<1.0`
- SparkForge adoption checklist prerequisites marked complete
- Release workflow paces PyPI uploads (10 minutes between packages)
- Install docs are pip-first now that `0.10.0` is on PyPI
- Agent guidance lists `etlantic.viz` and optional `etlantic-airflow` for compile

### Fixed

- Schema history refuses row-like metadata by key (no substring false positives)
- Core `redact_message` / `redact_value` cover HTTPS basic-auth and string leaves
- SparkForge report adapter redacts free-text errors, Bearer tokens, and DSNs
- `strict_delta=False` emits warnings for missing Delta capabilities (PMSF323)
- SparkForge IR missing step names emit `PMSF310` instead of raising `KeyError`
- Retry policy mapping clamps `max_attempts` to at least 1
- Unknown validation policy names fail closed (`KeyError`) instead of inventing
  empty policies
- Testing helpers harden write-semantics, orchestrator secret scans, and missing
  secret fail-closed behavior
- Adapter stops importing private `_PipelineNamespace`
- Docs SSOT: Graphviz/HTML/lineage, Spark, Airflow, and Mermaid status drift

### Upgrade notes

- Install `medallantic` (or `etlantic[medallantic]`) for the adapter
- ETLantic core remains free of bronze / silver / gold types
- Full SparkForge engine retirement remains a progressive path (see migration guide)
- Prefer `git tag v0.10.0 && git push origin v0.10.0` (not `git push --tags`)

## [0.9.0] - 2026-07-17

### Added

- CLI wrappers: `compile`, `generate`, `diff`, `plugin list|info`, schema family,
  reliability ops, viz exporters, and `report compare`
- `Profile.plugin_allowlist` with version pins; production fail-closed trust
- `FileSchemaHistoryProvider`, SARIF/GitHub diagnostic renderers
- Reliability provider protocols (quality, statistical, reconciliation, env)
- Observability protocols, JSON console logger, optional OpenTelemetry adapter
- `FileReportStore` and report comparison helpers
- Graphviz DOT / HTML lineage / JSON lineage exporters (`etlantic.viz`)
- Optional packages `etlantic-keyring` and `etlantic-sqlmodel`
- IDE command/result JSON schemas (`etlantic.ide`)
- Notebook / IPython display helpers (`etlantic.notebook`)
- Agent guidance generators + `scripts/check_agent_guidance.py`
- Expanded `etlantic.testing` (orchestrator, secrets, write-semantics parity)
- Migration guide `docs/11_DEVELOPMENT/MIGRATION_0_8_TO_0_9.md`

### Changed

- Package version advances to 0.9 (Tooling, SDK, and Ecosystem Readiness)
- Plugin packages require `etlantic>=0.9.0,<1.0`
- Graphviz / HTML / lineage docs promoted out of Future Design

### Upgrade notes

- Production profiles should set `plugin_allowlist` explicitly
- Schema history stores fingerprints only — never source rows
- Core remains free of Airflow, Spark, SQL drivers, SQLModel, keyring, and OTel
  unless extras / optional packages are installed

## [0.8.0] - 2026-07-17

### Added

- Versioned orchestration protocol (`etlantic.orchestration/1`) with compile,
  artifact transport, retry-safety, and lifecycle correlation models
- Independently installable `etlantic-airflow` reference compiler
- `compile_plan(...)` and `PipelinePlan.compile(target=...)`
- `Profile.schedule`, `Profile.execution`, and
  `required_orchestrator_capabilities`
- Entry-point group `etlantic.orchestrator_plugins`
- Runnable example `examples/airflow_compile.py`
- Migration guide `docs/11_DEVELOPMENT/MIGRATION_0_7_TO_0_8.md`

### Changed

- Package version advances to 0.8 (External Orchestration)
- Plugin packages (polars/pandas/sql/pyspark/airflow) require
  `etlantic>=0.8.0,<0.9`

### Upgrade notes

- Install `etlantic-airflow` to enable Airflow DAG compilation
- Core remains free of Airflow, PySpark, and SQL driver dependencies
- Unsupported orchestrator semantics fail compilation visibly (`PMORCH3xx`)

## [0.7.0] - 2026-07-17

### Added

- Versioned Spark execution protocol (`etlantic.spark/1`) with dataset refs,
  lazy region compile/execute, write intents, and UDF policy
- `Profile.spark_engine`, `spark_udf_policy`, `spark_streaming`, and
  `required_spark_capabilities`
- Independently installable `etlantic-pyspark` plugin with local Spark provider
- Lazy Spark region fusion preserving logical step identities
- Contract ↔ Spark schema mapping that diagnoses lossy/unknown mappings
- Delta-compatible append/overwrite/merge write intents (fail-closed)
- Structured Streaming foundation types marked **experimental**
- Entry-point groups `etlantic.spark_plugins` and `etlantic.spark_providers`
- Migration guide `docs/11_DEVELOPMENT/MIGRATION_0_6_TO_0_7.md`

### Changed

- Package version advances to 0.7 (Distributed Spark Execution)
- Planner prefers `spark_engine` over `sql_engine` / `dataframe_engine` when set
- Plugin packages (polars/pandas/sql/pyspark) require `etlantic>=0.7.0,<0.8`

### Upgrade notes

- Install `etlantic-pyspark` to enable Spark execution
- Core remains free of PySpark and Delta dependencies
- Streaming APIs are experimental; batch Spark is the production path

## [0.6.1] - 2026-07-16

### Changed

- Renamed the project, Python package, CLI, plugins, documentation, and
  distribution artifacts from Pipelantic to ETLantic
- Updated package discovery, plugin entry points, schemas, environment
  variables, examples, and repository URLs to use the `etlantic` namespace

## [0.6.0] - 2026-07-16

### Added

- Versioned SQL execution protocol (`etlantic.sql/1`) with relation refs,
  typed expressions, write intents, and dialect capability negotiation
- `Profile.sql_engine` for selecting a SQL backend during planning
- Independently installable `etlantic-sql` PostgreSQL reference plugin
  (SQLAlchemy Core; SQLite usable for local demos)
- SQL→SQL execution without intermediate Python row fetches when fusion is
  preserved
- Fail-closed merge and capability checks when a dialect cannot honor required
  semantics
- Entry-point discovery group `etlantic.sql_plugins`
- Conformance helpers under `etlantic.testing` for SQL expressions

### Changed

- Package version advances to 0.6 (SQL-Native Execution)
- Planning contexts for `sql` auto-require SQL capabilities when
  `Profile.sql_engine` is set

### Upgrade notes

- Install `etlantic-sql` separately; core stays driver-free
- Register SQL implementations with
  `@TransformationClass.implementation("sql")`
- Set `Profile(sql_engine="sql")` to select the SQL backend
- Configure connections via `ETLANTIC_SQL_URL` (or plugin-specific wiring)
- Missing plugins or unsupported capabilities (e.g. MERGE without keys) fail
  at validation/planning

## [0.5.0] - 2026-07-16

### Added

- Versioned dataframe execution protocol (`etlantic.dataframe/1`) with
  materialize → invoke → normalize → validate → metrics → cleanup phases
- Expanded capability vocabulary: eager, lazy, Arrow import/export, zero-copy,
  schema inspection, invalid-row separation, cancellation, thread-safety
- Planner recording of engine, plugin version, capabilities, collection points,
  conversion boundaries, ownership, and validation policy on `PipelinePlan`
- Runtime delegation of Polars/Pandas steps through the dataframe protocol
  without reselecting engines
- Independently installable `etlantic-polars` (eager + LazyFrame preservation)
  and `etlantic-pandas` (eager, CoW/ownership isolation)
- Optional Arrow interchange helpers (PyArrow imported only when available)
- Entry-point discovery group `etlantic.dataframe_plugins`
- Conformance helpers in `etlantic.testing`
- uv workspace packaging for core + dataframe plugins

### Changed

- Package version advances to 0.5 (Dataframe Execution)
- Built-in `local` registry plugin is a runtime/records path (`dataframe=False`),
  not a dataframe engine
- Planning contexts for `polars`/`pandas` auto-require dataframe capabilities

### Upgrade notes

- Install `etlantic-polars` or `etlantic-pandas` separately; core stays
  engine-free
- Register dataframe implementations with
  `@TransformationClass.implementation("polars")` or `"pandas"`
- Set `Profile.dataframe_engine` to `"polars"` or `"pandas"` to select a backend
- Missing plugins or unsupported capabilities (e.g. Pandas + lazy) fail at
  validation/planning

### Fixed

- Default `Pipeline.run` / CLI planning now uses plugins discovered on
  `PipelineRuntime` (and entry-point discovery for plan-only contexts)
- Fan-out / unconsumed / cross-engine ports map to in-memory strategies instead
  of durable records; durable conversion only follows durable strategies
- Per-port collect and validation; quarantine/reject populate invalid artifacts
  and metrics
- Schema observation uses plugin `inspect_schema` for native frames
- Durable `ArtifactStore` refuses native frames/LazyFrames (fail closed)
- Discovery load failures emit warnings; LazyFrame dtype checks without row
  collect; invoke kwargs prefer inputs over colliding parameters
- Core `from_arrow_table` no longer imports Polars/Pandas

## [0.4.0] - 2026-07-16

### Upgrade notes

- Register local executable transformations with
  `@TransformationClass.implementation("local")`.
- Use the `development` profile for the built-in local runtime examples.
- Pandas, Polars, SQL, Spark, and Airflow plugins are not part of this release.

### Known limitations

- The local report store is process-scoped.
- The package remains alpha and 0.x releases may contain breaking changes.

### Added

- Local async-first runtime that executes `PipelinePlan`s in-process
- `Pipeline.run` / `Pipeline.arun` / `Pipeline.debug` entry points
- `RunIntent`, `RunSelection`, `RunRequest`, and materialization/retry/timeout
  policies
- `PipelineRuntime` with lifespan, middleware, resource injection, callbacks,
  and outbound event types
- Runtime-only `SecretValue` with env and mounted-file `SecretProvider`s,
  bounded cache, and fail-closed resolution (planning remains secret-free)
- Storage bindings: `memory`, `callable`, `json`, `csv`, and `null` (no-write)
- Versioned `PipelineRunReport` with text/JSON/HTML renderers and in-process
  report store
- Structured logging with central secret redaction and lifecycle/security events
- `SchemaDriftPolicy` observation hooks and local reliability helpers
  (freshness, partition completeness, retry-safety, backfill/repair/no-write)
- CLI: `etlantic run` and `etlantic report show|export`
- Hard dependency on `anyio` for structured concurrency

### Fixed

- Durable materialization no longer always writes workspace files; strategy
  comes from the plan/request
- Missing transformation implementations fail closed (no silent identity
  fallback or engine swap)
- Cancellation uses `anyio` cancelled-exc handling and returns a partial report
- Exception and diagnostic messages are redacted before entering reports/logs
- Binding `SecretRef` values are passed into storage context; unresolved
  secrets still fail closed
- Plan `retry_max_attempts` / `timeout_seconds` merge into default `RunRequest`
  policies
- Planner default binding provider is `memory` (`local`/`python` remain aliases)
- Binding overrides resolve registry descriptors for provider/location/secret
- Retry honors backoff/`retry_on` and retry-safety declarations; `CONTINUE`
  soft-skips without failing the step status as hard failure
- Schema observations fingerprint observed data (not only the contract class)
- CLI `run` prints embedded reports on `PipelineExecutionError`
- Debug session invalidation clears shared artifact/memory state across reruns
- Resource `Inject` wiring, outbound `Emit` capture, report lineage, and
  run/region lifespan helpers

### Changed

- Package version and public status advance to 0.4 (Local Runtime and
  Operational Model)
- `SecretRef` lives under the `etlantic.secrets` package alongside runtime
  secret resolution types

## [0.3.0] - 2026-07-16

### Added

- `Data` as the preferred thin facade over ContractModel (`DataContractModel`
  remains as a deprecated alias)
- Multi-phase validation (structural, reference, semantic, policy, capability)
  with diagnostic actions and source symbols
- `Profile` templates, `SecretRef`, scoped registries, and capability negotiation
- Immutable secret-free `PipelinePlan` IR (`etlantic.plan/1`) with slicing,
  explain output, and canonical fingerprints
- Schema-drift models (`NormalizedSchema`, observations, changes, `DriftImpact`)
- Portable reliability/intent models (freshness, write/materialization intents,
  idempotency, evidence schemas)
- JSON Schemas for profiles, project config, and PipelinePlan
- `etlantic` CLI: `validate`, `inspect`, `plan`, and `plan explain`
  (plus `plan --explain` alias, `--nodes`, and mutual exclusion for
  `--run-one` / `--run-until`)
- `Pipeline.plan()` / `Pipeline.explain_plan()`

### Fixed

- `run_until` selects declaration-order prefix (not only upstream closure)
- Unknown plan selections fail closed with `PMPLAN501`
- Multi-engine regions and cross-engine durable artifact strategies
- Profile snapshot included in plan fingerprint
- Strict policy requires registered transformation implementations
- Subpipeline validation inherits parent planning context
- Plan JSON round-trip restores `secret_ref` and verifies fingerprints
- Schema-only DTCS ports map `datetime`/`decimal`/`binary` correctly
- Diff APIs return diagnostics for malformed toolkit input

### Changed

- Package version and public status advance to 0.3 (Validation and Pipeline Plan IR)
- Explicit `click` dependency for the CLI plan command group (Typer 0.15+ no
  longer pulls it in transitively)

## [0.2.0] - 2026-07-16

### Added

- Contract interoperability for
  [ODCS](docs/03_DATA_CONTRACTS/ODCS.md) (via ContractModel), DTCS, and
  [DPCS](docs/05_PIPELINES/DPCS.md)
- `Transformation.to_dtcs` / `from_dtcs` and `Pipeline.to_dpcs` / `from_dpcs`
- Deterministic `ContractBundle` generation via `generate_contracts` /
  `write_contracts` / `load_bundle`
- ODCS facades `load_data_contract` and `write_odcs`
- Diff hooks: `diff_data_contracts`, `diff_transformations`, `diff_pipelines`
- Supported-version policy, bounded safe loaders, and source-aware diagnostics
- Dependencies on the published `dtcs` and `dpcs` toolkits

### Fixed

- Map ContractModel `number`/`datetime` fields to DTCS `decimal`/`datetime`
- Emit transformation parameters as `etlantic:parameters` (toolkit-valid)
- Round-trip DPCS step parameter overrides
- Treat matching published ODCS ids as compatible in `PMPIPE210` checks
- Recursively validate nested subpipelines
- Clear stale cyclic graph-build errors on fresh `build_graph()`
- Fail closed on DPCS diff incompatible categories and bad DTCS parse input
- Detect published-id / filename slug collisions during bundle generation
- Resolve `odcs:`-prefixed contract registry keys in `from_dtcs`
- Expose `ValidationReport.has_errors` for the documented validation UX
- Correct getting-started imports to use `etlantic.DataContractModel`
  (ContractModel does not export `DataContractModel`)

## [0.1.0] - 2026-07-16

### Added

- First public release as **ETLantic** (PyPI package `etlantic`)
- Typed modeling kernel for authoring pipelines without an execution backend
- `Transformation`, `Input`, `Output`, and `Parameter` port annotations
- `Pipeline`, `Source`, `Step`, `Sink`, and subpipeline composition
- Typed `OutputRef` wiring with stable node and port identities
- Structural validation diagnostics (cycles, missing refs, incompatible ports)
- Logical graph inspection and Mermaid diagram generation
- ContractModel integration boundary via `DataContractModel` alias
- uv + ruff toolchain, MkDocs documentation site, shared GitHub Actions
  checks, and tag-triggered PyPI release

[0.43.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.43.0
[0.42.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.42.0
[0.41.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.41.0
[0.40.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.40.0
[0.39.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.39.0
[0.38.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.38.0
[0.37.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.37.0
[0.36.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.36.0
[0.35.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.35.0
[0.34.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.34.0
[0.33.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.33.0
[0.32.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.32.0
[0.31.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.31.0
[0.30.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.30.0
[0.29.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.29.0
[0.28.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.28.0
[0.27.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.27.0
[0.26.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.26.0
[0.25.1]: https://github.com/eddiethedean/etlantic/releases/tag/v0.25.1
[0.25.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.25.0
[0.24.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.24.0
[0.23.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.23.0
[0.22.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.22.0
[0.21.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.21.0
[0.20.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.20.0
[0.19.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.19.0
[0.18.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.18.0
[0.17.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.17.0
[0.16.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.16.0
[0.15.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.15.0
[0.14.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.14.0
[0.13.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.13.0
[0.12.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.12.0
[0.11.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.11.0
[0.10.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.10.0
[0.9.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.9.0
[0.8.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.8.0
[0.7.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.7.0
[0.6.1]: https://github.com/eddiethedean/etlantic/releases/tag/v0.6.1
[0.6.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.6.0
[0.5.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.5.0
[0.4.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.4.0
[0.3.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.3.0
[0.2.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.2.0
[0.1.0]: https://github.com/eddiethedean/etlantic/releases/tag/v0.1.0
