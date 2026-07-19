# Security Model

ETLantic coordinates contracts, Python code, plugins, credentials, data
artifacts, and external execution systems. Security is therefore a
cross-cutting architectural constraint, not a feature delegated to one plugin.

This chapter defines the proposed ETLantic 1.0 threat model, trust
boundaries, required controls, and production-readiness gates.

## Principles

1. Treat contracts, configuration, plugins, metadata, and generated artifacts
   as untrusted input.
2. Do not execute transformation or runtime plugin callables during loading,
   validation, inspection, or planning. Loading a Python pipeline target or
   discovering an installed entry point still runs trusted module-level import
   code—use curated environments and process isolation.
3. Keep resolved secrets out of contracts, plans, caches, logs, reports, and
   generated artifacts.
4. Make filesystem, network, subprocess, plugin, and credential authority
   explicit.
5. Apply least privilege to providers and execution units.
6. Preserve authorization and security domains during optimization.
7. Redact sensitive information before it leaves the core boundary.
8. Prefer bounded data-only formats over executable serialization.
9. Fail closed when mandatory security semantics cannot be preserved.
10. Make security decisions inspectable and auditable.

## Threat Model

ETLantic may process input from repository contributors, registries, CI
artifacts, third-party plugins, environment configuration, remote
orchestrators, data sources, and notification destinations.

Relevant threats include:

- arbitrary code execution during discovery or deserialization
- malicious or compromised plugins
- path traversal and unsafe file writes
- server-side request forgery through remote references or webhooks
- SQL, shell, template, HTML, and Graphviz injection
- credential leakage through plans, logs, diagnostics, reports, or caches
- artifact reuse across runs, environments, tenants, or security domains
- privilege escalation through overpowered resource providers
- integrity loss in generated plans or backend artifacts
- unsafe fallback that weakens validation or authorization
- denial of service through oversized documents, graphs, recursion, logs, or
  retries

## Trust Boundaries

```text
Untrusted authoring inputs
    contracts, config, Python modules, plugin metadata
                       │
                       ▼
Analysis boundary
    loading, validation, diagnostics, planning
                       │
                       ▼
Privileged runtime boundary
    user code, plugins, providers, credentials
                       │
                       ▼
External systems
    databases, storage, Spark, Airflow, APIs, queues
```

The analysis boundary must not require runtime privileges.

## Security Evaluation

| Area | Main risk | Required control | Design status |
|---|---|---|---|
| Contract loading | parser abuse, traversal, SSRF | bounded safe loaders and approved resolvers | Partial |
| Python discovery | import-time execution | static discovery or explicit trusted import | Gap |
| Planning | code or secret resolution | pure, secret-free planning | Strong |
| Plugins | supply-chain execution | curated installs, allowlists, pins, provenance | Partial (allowlists/pins select already-discovered plugins; provenance Gap) |
| Resource providers | excessive authority | scopes, least privilege, cleanup | Strong concept |
| SQL | injection and query leakage | structured compilation and parameters | Strong |
| PySpark | remote code and cluster overreach | isolation and provider policy | Partial |
| Artifacts | cross-run or cross-tenant exposure | identity, authorization, integrity, expiry | Gap |
| Caching | unauthorized reuse | security-domain-aware cache keys | Gap |
| Logging and reports | secret or regulated-data leakage | central redaction | Strong |
| HTML and docs | script or template injection | escaping and safe renderers | Strong |
| Outbound events | SSRF and exfiltration | bound destinations and payload policy | Gap |
| CLI | shell injection and unsafe writes | argument lists and approved roots | Partial |
| Serialization | arbitrary object construction | prohibit executable formats | Gap |
| Denial of service | unbounded work | configurable budgets | Gap |
| Audit | incomplete evidence | immutable security events and provenance | Partial |

## Loading and Parsing

Portable artifacts should use data-only formats such as JSON, TOML, safely
configured YAML, or justified schema-based binary formats.

ETLantic must not deserialize untrusted:

- `pickle`
- `dill`
- `cloudpickle`
- marshal data
- arbitrary Python objects
- YAML Python object tags or custom constructors

Loaders should enforce limits for:

- source bytes
- nesting depth
- collection size
- reference count and depth
- total resolved bytes
- diagnostics produced

Recursive references must terminate with a diagnostic.

### Filesystem safety

File resolvers should:

- restrict reads and writes to configured roots
- normalize paths before authorization
- reject traversal outside approved roots
- define symlink behavior
- reject special and device files
- use atomic writes for generated artifacts
- avoid overwriting source files without explicit authorization

### Remote references and SSRF

Remote resolution is disabled by default. When enabled, require:

- allowed schemes and host allowlists
- resolved-address checks
- rejection of loopback, link-local, metadata, and private targets unless
  explicitly approved
- validation after every redirect
- TLS verification
- request timeouts and response-size limits
- no ambient credential forwarding
- optional digest or signature verification

## Python Discovery

Importing a Python module executes top-level code.

Commands such as `inspect`, `validate`, `docs`, and `plan` should use static
discovery where practical. Commands that import user modules must state that
clearly and run with minimum privileges.

Pipeline definitions must not acquire resources, access networks, or execute
pipeline work during import.

A subprocess can improve containment and cleanup, but a subprocess alone is not
a security sandbox.

## Planning

Planning is a pure analysis operation. It must not:

- execute transformations, validators, callbacks, middleware, or lifespan code
- acquire resources
- resolve secrets
- materialize or sample data
- contact execution backends except through an explicitly requested,
  read-only, isolated capability probe

Plans may contain secret reference identifiers and logical authorization
requirements. They must not contain secret values, bearer tokens,
credential-bearing URLs, live clients, sessions, or executable closures.

Serialized plans require a versioned schema and canonical representation.
Providers should support digest or signature verification when plans cross
trust boundaries.

### Portable transformation definitions

The published DTCS 3.0 Transformation Plan adds an analysis input for
ETLantic's planned compiler boundary. Portable definitions must normalize to
closed, bounded, data-only `dtcs.transform-plan/2` expression graphs
(v1 remains readable).

Python `@Transformation.portable` authoring invokes trusted definition code
with symbolic values during an explicit trusted import. Static loading,
validation, inspection, planning, and compilation from serialized artifacts
must reconstruct data-only IR without importing or invoking that code.

Portable definition controls include:

- prohibit arbitrary Python objects, callables, modules, native dataframe
  expressions, raw SQL, and executable serialization
- enforce expression depth, node count, string size, literal size, collection
  length, and diagnostic budgets
- represent runtime parameters and secrets by typed references, never captured
  values
- reject actions, resource acquisition, data reads, network access, and
  collection during definition building and planning
- validate column and relation identifiers before backend lowering
- require bound parameters for SQL lowering
- include IR and compiler fingerprints in cache and artifact identities
- preserve security-domain, validation, retry, and materialization boundaries
  during expression and region optimization
- require production plugin allowlists and compiler version policy

Compilers are trusted plugins with host-process authority. A portable IR is not
a sandbox for its compiler. Capability negotiation and conformance testing make
compiler behavior inspectable but do not replace operating-system isolation.

See the proposed
[Portable Transformation IR specification](../specifications/PORTABLE_TRANSFORM_IR_SPEC.md)
and [compiler protocol](../07_PLUGIN_SDK/PORTABLE_TRANSFORM_COMPILER.md).

## Plugins

Python plugins execute with host-process privileges. Entry-point discovery is a
trust decision, not a sandbox.

**Important:** `Profile.plugin_allowlist` filters which discovered plugins may
be *selected* for planning and execution. Discovery still loads entry-point
factories at runtime construction time, so an installed malicious package can
run import-time code before the allowlist is applied. Install only trusted
packages, prefer locked environments, and isolate untrusted evaluation.

**Shipped in 0.9+:** production profiles fail closed unless
`Profile.plugin_allowlist` is set. Configure allowlists in Python (ETLantic
does **not** load `etlantic.toml` today):

```python
from etlantic import Profile

production = Profile(
    name="production",
    security_domain="production",
    dataframe_engine="polars",
    portable_transform_policy="require",
    plugin_allowlist={
        "etlantic-polars": "==0.14.0",
        "etlantic-airflow": "==0.14.0",
    },
)
```

See [Runtime configuration](../10_REFERENCE/RUNTIME_CONFIGURATION.md).

!!! note "Future design (1.0)"
    A proposed `etlantic.toml` `[plugins.security]` block may eventually mirror
    the same allowlist semantics. Do not configure TOML as if it is loaded in
    0.14—use `Profile.plugin_allowlist`.

Controls should include:

- explicit allowlists
- pinned or constrained versions
- package provenance in plans and reports
- capability conflict detection
- explicit approval for high-risk capabilities
- advisory and revocation procedures
- refusal of silent fallback to unapproved plugins

Plugin descriptors should declare requested privileges such as:

```text
filesystem.read
filesystem.write
network.outbound
subprocess.spawn
secrets.read
database.execute
cluster.submit
```

Enforcement belongs to operating-system, container, orchestrator, or cloud
controls. Descriptors make authority visible to planning and policy.

## Resources and Secrets

Resource providers resolve credentials as late as possible.

They must:

- issue least-privileged resources
- honor runtime, run, region, step, and attempt scopes
- prefer short-lived credentials
- revoke or release temporary credentials
- prevent secrets from entering `repr`, serialization, logs, exceptions, and
  reports
- expose authorization failures without credential contents

Secret values should use a sensitive wrapper that redacts string
representation, blocks serialization, avoids plan hashing, and permits explicit
reveal only inside an authorized provider boundary.

Callables receive only declared resources. Middleware and callbacks must not
acquire undeclared privileged services.

ETLantic uses a dedicated Secret Provider protocol rather than treating
plaintext environment variables as its universal secrets API. Profiles and
plans contain `SecretRef` identifiers only. Resolution occurs after the
execution boundary begins, and only the Resource Provider constructing the
authorized dependency receives the `SecretValue`.

Remote providers should authenticate with workload, managed, pod, task, or
instance identity rather than another long-lived secret whenever possible.
Cross-provider fallback must be explicit; production resolution must never
silently fall back to environment variables or plaintext files.

Secret caching must be bounded, in-memory, scoped, and short-lived. Provider
implementations must define rotation, version, lease, renewal, revocation, and
cleanup behavior without claiming that immutable Python strings can be
reliably zeroized.

See [Secrets Management](../06_EXECUTION/SECRETS_MANAGEMENT.md) and the
[Secret Provider SDK](../07_PLUGIN_SDK/SECRET_PROVIDER.md).

## Executable User Code

Transformations, validators, callbacks, middleware, lifespan handlers, and
provider functions are trusted executable Python unless run behind an external
isolation boundary.

ETLantic cannot safely sandbox arbitrary Python in-process.

Production execution should use:

- dedicated identities
- filesystem and network restrictions
- CPU, memory, and time limits
- isolated environments for separate tenants or trust domains
- separate analysis and execution workers

## SQL

SQL plugins must:

- parameterize values
- validate identifiers separately
- quote identifiers through dialect APIs
- reject untrusted SQL-fragment concatenation
- limit multi-statement execution
- use read-only connections for read-only work
- scope write authority to declared sinks
- keep compiled SQL artifacts secret-free (no live bound parameter values in
  serializable metadata; redact DSN credentials in diagnostics)
- redact parameters and sensitive query text
- preserve row- and column-level security

Pushdown and fusion may not cross authorization, tenancy, residency, masking,
or policy-enforcement boundaries.

### SQLModel integration

Optional SQLModel persistence and model-generation integrations must:

- keep control-plane credentials separate from pipeline-data credentials;
- expose provider protocols rather than sessions, engines, metadata, or ORM
  instances through ETLantic core;
- use separate request, persistence, and response models when protected or
  database-only fields exist;
- prevent mass assignment of identity, tenant, policy, approval, secret
  reference, and administrative fields;
- enforce tenant and workspace filters inside repository operations;
- bound pagination, relationship traversal, eager loading, and query results;
- prohibit automatic production `create_all()` and require reviewed migrations;
- treat generated SQLModel and migration source as a proposal requiring review;
- avoid serializing ORM state into contracts, plans, reports, events, or
  generated context.

## PySpark and Distributed Execution

Remote Spark execution can submit privileged code to a cluster. Providers must
validate:

- approved endpoints and clusters
- execution identity
- artifact provenance
- dependency allowlists
- driver and executor environments
- network and storage permissions
- temporary credential lifecycle
- job and tenant isolation

Python UDF use should be visible in plans and reports because it changes trust,
portability, and optimization characteristics.

Job names, tags, Spark configuration, and submitted arguments must not include
secrets.

## Artifacts and Previous-Step Results

Artifacts require:

- producer and run identity
- security-domain identity
- contract identity
- classification metadata
- integrity metadata where practical
- lifetime and expiry
- allowed consumers
- encryption requirements

An `OutputRef` may remain in memory or lazy only inside a compatible security
boundary. Durable `ArtifactRef` resolution must prevent cross-run,
cross-environment, cross-tenant, expired, or revoked reuse.

Unguessable artifact identifiers are not a substitute for authorization.

## Schema Observations and Drift History

Schema metadata can expose confidential field names, system topology, tenant
identities, classifications, and business behavior even when no source rows
are stored.

Schema inspection and tracking must:

- require explicit source, profile, workspace, and environment authority;
- avoid reading source records when catalog metadata is sufficient;
- store no source values in observations by default;
- bound backend metadata, nested schemas, samples, and history queries;
- isolate histories and baselines by tenant and security domain;
- redact or classify sensitive field and system metadata;
- prevent observations from one environment satisfying another environment's
  policy gate;
- integrity-protect production observations used as approval or audit evidence;
- audit inspection, acknowledgement, approval, baseline, and remediation
  actions;
- keep live inspection out of loading, static validation, planning, editor
  startup, and rich display methods.

Acknowledgement is an auditable operational decision, not authorization to
rewrite an authoritative data contract.

## Reliability Observations and Recovery Operations

Freshness checks, partition inspection, reconciliation, repair, backfills,
quality profiling, and statistical drift analysis can scan sensitive data or
perform high-impact writes.

These capabilities must:

- separate inspect, plan, approve, execute, and acknowledge authority;
- prefer metadata and manifests over source-row scans;
- bound partitions, rows, bytes, fields, categories, history, time, and cost;
- require explicit approval for destructive writes, large backfills, checkpoint
  replacement, unsafe retry overrides, and broad downstream invalidation;
- keep idempotency keys, reconciliation snapshots, and repair identities scoped
  to tenant, environment, source revision, and security domain;
- exclude secret values and unrestricted source values from fingerprints,
  plans, reports, and quality histories;
- require privacy policy for statistical profiling and prohibit sensitive
  exemplars or unrestricted categorical values;
- integrity-protect evidence used to authorize repair, publication, backfill,
  or deployment;
- record audit events for retry overrides, destructive writes, reconciliation
  waivers, repair execution, backfill approval, and drift acknowledgement;
- fail closed when write, retry, transaction, reconciliation, or privacy
  semantics are unknown.

An estimated repair scope, cost, or statistical anomaly is evidence for a
decision, not authority to execute it.

## Cache Security

Cache identity should include:

- pipeline and transformation versions
- input artifact identities
- contract versions
- parameters
- implementation and plugin versions
- profile or security-domain identity
- relevant policy versions

Secret values should not appear directly in keys.

Sensitive caches require access control, appropriate encryption, retention
limits, explicit invalidation, tenant isolation, and secure cleanup.

## Logs, Diagnostics, and Reports

Redaction occurs before information leaves the core boundary.

Do not include by default:

- credentials or authorization headers
- credential-bearing URLs
- complete environment snapshots
- raw input or rejected records
- secret-backed parameters
- unlimited SQL, Spark, Airflow, or backend logs

Contract classification metadata should drive field-level redaction.

Security events include:

- denied plugin or resource use
- failed authorization
- rejected remote resolution
- integrity failures
- unsafe fallback refusal
- policy overrides
- artifact access denial
- redaction failures

Security logs require their own access and retention policies.

## Generated Documentation

Names, descriptions, diagnostics, backend metadata, and contract fields are
untrusted text.

Generators must:

- escape HTML
- prevent template and script injection
- validate URLs
- avoid unsafe remote assets
- support restrictive Content Security Policy
- redact physical endpoints and sensitive metadata
- prevent formula injection in CSV and spreadsheet exports
- prevent command injection in external renderers

Subprocesses should receive argument lists without shell interpolation.

## Outbound Events and Webhooks

Outbound destinations are profile bindings, not arbitrary URLs derived from
pipeline data.

Providers require:

- destination allowlists
- TLS verification
- resource-provider authentication
- payload classification checks
- size and rate limits
- redirect restrictions
- idempotency keys
- bounded retry and dead-letter behavior
- response time and size limits

An event schema does not authorize sending every source field. Payload
construction must be explicit.

## CLI

The CLI must:

- avoid `shell=True`
- separate command arguments from data
- redact configuration and environment output
- confirm destructive operations
- offer dry-run and `--check`
- restrict generated output paths
- use secure temporary files
- keep remote resolution opt-in
- return nonzero status for security-policy failures

Debug verbosity must not weaken redaction.

## AI Coding Assistants and Agent Skills

Codex, Claude Code, Cursor, and similar tools may read repository files, edit
code, invoke commands, and connect to external tools. Their instruction files
are guidance, not a security boundary, and never prove that an action is
authorized.

ETLantic-generated skills, rules, commands, context bundles, and MCP tools
must:

- use one vendor-neutral workflow definition as their source;
- treat contracts, documentation, comments, logs, diagnostics, artifacts, and
  reports as untrusted and potentially prompt-injecting input;
- distinguish instructions from quoted project data with explicit provenance;
- default agent-facing APIs and MCP tools to read-only inspection, validation,
  planning, explanation, and report queries;
- require human approval for mutation, command execution, run submission,
  plugin installation, secret access, or external communication;
- exclude secret values, credentials, protected artifact contents, and
  unrestricted environment variables from generated context;
- bound context by files, bytes, graph size, rows, columns, diagnostics, and
  events;
- preserve user-authored instruction regions and report generation conflicts;
- record workflow versions, selected inputs, tool calls, validation results,
  and proposal provenance;
- route changes through ordinary files, semantic diff, validation,
  compatibility analysis, and policy checks;
- prohibit generated guidance from weakening sandbox, network, plugin,
  resolver, or secret-provider policies;
- keep model-vendor SDKs and credentials outside ETLantic core.

Agent output remains an untrusted proposal until normal validation, testing,
security review, and human approval succeed.

## Denial-of-Service Budgets

Configurable budgets should cover:

- document bytes and nesting
- graph nodes and edges
- reference depth and count
- plugin discovery time
- validation findings
- log and report size
- artifact samples
- concurrent runs and steps
- middleware and callback duration
- request timeouts
- retry attempts

Limit violations produce stable diagnostics, not unbounded work.

## Supply Chain

Core and plugin releases should use:

- dependency locks
- vulnerability scanning
- static analysis
- secret scanning
- build provenance
- signed artifacts where supported
- protected release workflows
- minimal publication permissions
- documented supported versions and patch policy

## Multi-Tenancy

ETLantic must not claim in-process tenant isolation.

Strong isolation requires separate identities, artifact namespaces, cache
namespaces, secret scopes, quotas, and execution environments. Context
variables help correctness but are not a security boundary.

## Configuration

**Shipped today:** configure security-relevant controls on `Profile` in Python.
ETLantic does **not** load `etlantic.toml`. See
[Runtime configuration](../10_REFERENCE/RUNTIME_CONFIGURATION.md).

```python
from etlantic import Profile

production = Profile(
    name="production",
    security_domain="production",
    plugin_allowlist={
        "etlantic-polars": ">=0.10.0,<1.0",
        "etlantic-sql": ">=0.10.0,<1.0",
    },
)
```

!!! note "Future design (1.0)"
    A proposed TOML security policy block may eventually participate in
    planning (document size limits, filesystem roots, network allowlists).
    That configuration surface is **not** loaded in 0.10. Proposed names live
    under [Configuration](../10_REFERENCE/CONFIGURATION.md).

Security policy participates in planning. Secret values do not.

## Diagnostics

Security diagnostics use stable `PMSEC` codes:

```text
PMSEC001: Remote references are disabled.
PMSEC010: Resolved path escapes the configured project root.
PMSEC020: Plugin is not in the production allowlist.
PMSEC030: Unsafe serialization format is prohibited.
PMSEC040: Artifact security domain does not match the consumer.
PMSEC050: Outbound destination is not approved.
PMSEC060: Sensitive value was blocked from report serialization.
```

Mandatory security failures cannot be downgraded through ordinary warning
configuration.

## Verification

Before 1.0, automated tests should cover:

- malicious YAML tags and deeply nested inputs
- path traversal and symlink escapes
- SSRF, redirects, DNS changes, and response limits
- planning purity and import-time side effects
- plugin allowlists and conflicts
- secret redaction across every output channel
- SQL value and identifier injection
- shell, Graphviz, HTML, template, and formula injection
- artifact authorization and expiry
- cache isolation across profiles and tenants
- outbound destination enforcement
- cleanup and credential revocation
- denial-of-service budgets

Security-sensitive parsers and resolvers should receive property tests and
fuzzing where practical.

## Incident Response

The repository should publish:

- a root `SECURITY.md`
- supported version policy
- private vulnerability-reporting instructions
- severity and response targets
- coordinated disclosure process
- credential-rotation guidance
- plugin advisory and revocation process

## Security Release Gate

ETLantic is not production-ready until:

- the threat model is reviewed
- mandatory controls have implementation owners and tests
- unsafe serialization is prohibited
- remote resolution is safe and opt-in
- plugin trust policy is implemented
- planning purity is verified
- redaction is centralized and tested
- artifact and cache isolation exist
- outbound destinations are constrained
- supply-chain checks run in release CI
- private vulnerability reporting is available

## Standards Alignment

Verification should draw from the OWASP Top Ten for risk awareness and OWASP
ASVS for testable controls, with specialized guidance for unsafe
deserialization and server-side request forgery.

These sources inform ETLantic's controls; ETLantic is not itself a
web application framework.

## Key Principle

> ETLantic may coordinate privileged execution, but analysis stays
> unprivileged, authority stays explicit, exposure stays minimal, and no
> optimization or fallback may weaken a declared security boundary.

## References

- [OWASP Top Ten](https://owasp.org/www-project-top-ten/)
- [OWASP Application Security Verification Standard](https://owasp.org/www-project-application-security-verification-standard/)
- [OWASP Deserialization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Deserialization_Cheat_Sheet.html)
- [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
