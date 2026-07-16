# Security Model

Pipelantic coordinates contracts, Python code, plugins, credentials, data
artifacts, and external execution systems. Security is therefore a
cross-cutting architectural constraint, not a feature delegated to one plugin.

This chapter defines the proposed Pipelantic 1.0 threat model, trust
boundaries, required controls, and production-readiness gates.

## Principles

1. Treat contracts, configuration, plugins, metadata, and generated artifacts
   as untrusted input.
2. Never execute code during loading, validation, inspection, or planning.
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

Pipelantic may process input from repository contributors, registries, CI
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
| Plugins | supply-chain execution | allowlists, pins, provenance | Gap |
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

Pipelantic must not deserialize untrusted:

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

## Plugins

Python plugins execute with host-process privileges. Entry-point discovery is a
trust decision, not a sandbox.

Production profiles should support:

```toml
[plugins.security]
discovery = "allowlist"
allowed = [
  "pipelantic-polars",
  "pipelantic-airflow",
]
require_pinned_versions = true
```

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

Pipelantic uses a dedicated Secret Provider protocol rather than treating
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

Pipelantic cannot safely sandbox arbitrary Python in-process.

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
- redact parameters and sensitive query text
- preserve row- and column-level security

Pushdown and fusion may not cross authorization, tenancy, residency, masking,
or policy-enforcement boundaries.

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

Pipelantic-generated skills, rules, commands, context bundles, and MCP tools
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
- keep model-vendor SDKs and credentials outside Pipelantic core.

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

Pipelantic must not claim in-process tenant isolation.

Strong isolation requires separate identities, artifact namespaces, cache
namespaces, secret scopes, quotas, and execution environments. Context
variables help correctness but are not a security boundary.

## Configuration

Conceptually:

```toml
[security]
mode = "strict"
allow_remote_references = false
allow_user_code_during_planning = false
allow_unsafe_serialization = false
require_plugin_allowlist = true
require_pinned_plugins = true

[security.limits]
document_bytes = 10485760
reference_depth = 20
graph_nodes = 10000
diagnostics = 1000

[security.filesystem]
read_roots = ["contracts", "src"]
write_roots = ["build"]

[security.network]
allowed_hosts = ["contracts.example.com"]
allow_private_addresses = false
```

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

Pipelantic is not production-ready until:

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

These sources inform Pipelantic's controls; Pipelantic is not itself a
web application framework.

## Key Principle

> Pipelantic may coordinate privileged execution, but analysis stays
> unprivileged, authority stays explicit, exposure stays minimal, and no
> optimization or fallback may weaken a declared security boundary.

## References

- [OWASP Top Ten](https://owasp.org/www-project-top-ten/)
- [OWASP Application Security Verification Standard](https://owasp.org/www-project-application-security-verification-standard/)
- [OWASP Deserialization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Deserialization_Cheat_Sheet.html)
- [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
