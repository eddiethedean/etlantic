# TransformationModel Incubation Plan

## Status

Proposed post-foundation 0.39 incubation plan (deferred from 0.20+). The package and APIs
described here are not shipped behavior.

TransformationModel begins as an independently buildable workspace package at
`packages/transformationmodel`. It may become a separately released ETLantic
dependency only after the graduation gates in this plan pass.

## Product outcome

TransformationModel should be the Python-native modeling layer for [DTCS](../04_TRANSFORMATIONS/DTCS.md):

```text
Python annotations and portable expressions
                    ↓
immutable transformation semantics
                    ↓
DTCS validation • interchange • fidelity • compatibility
                    ↓
ETLantic, CI, catalogs, compilers, and independent consumers
```

It is the transformation counterpart to ContractModel. It makes transformation
contracts ergonomic to author and inspect without becoming an execution engine,
pipeline orchestrator, or competing specification.

## Architectural position

The dependency direction is one-way:

```text
dtcs                 ContractModel
  ↓                        ↓
TransformationModel ───────┐
                           ↓
                        ETLantic
                           ↓
               compiler and runtime plugins
```

- `dtcs` owns normative DTCS parsing, canonical representation, validation,
  diagnostics, portable plans, and DTCS-native compatibility semantics.
- ContractModel owns data-contract semantics and runtime data-validation
  requirements.
- TransformationModel owns Python-native transformation declarations,
  immutable introspection, typed expressions, DTCS translation, and fidelity.
- ETLantic owns steps, pipeline wiring, planning, profiles, implementation
  selection, execution policy, and normalized results.
- Plugins own backend compilation and execution.

TransformationModel must never import ETLantic. ETLantic may import it only
through documented public APIs.

## Why extract a package

ETLantic already contains a useful transformation modeling subsystem, but its
reusable semantic pieces currently live beside pipeline and runtime concerns.
Extraction provides:

- reusable Python authoring for DTCS outside ETLantic
- a smaller, independently testable semantic kernel
- clear ownership between standards, modeling, planning, and execution
- independent versioning for DTCS evolution
- a stable target for catalogs, linters, editors, and other orchestrators
- fewer ETLantic-specific extensions in portable artifacts

The package is not justified by naming symmetry alone. It graduates only if an
independent consumer proves that the boundary is useful.

## Extraction inventory

### Strong candidates for TransformationModel

- transformation identity and immutable descriptors
- input, output, and parameter declarations
- portable column, scalar, aggregate, window, lambda, complex-value, and
  relational expressions
- DTCS semantic action and function mappings
- portable-profile and capability declarations
- expression and transformation-definition validation
- deterministic portable-plan construction and fingerprinting
- DTCS import, export, diagnostics, compatibility, and fidelity
- compiler capability protocols containing no runtime objects

Current sources to assess include `src/etlantic/transform/`, the semantic parts
of `src/etlantic/interchange/dtcs.py`, and the declaration and introspection
parts of `src/etlantic/transformation.py`. This is a review list, not permission
for a mechanical move; ownership must be decided symbol by symbol.

### Must remain in ETLantic

- `Step` instances, pipeline node identity, and `OutputRef` wiring
- executable implementation registration and backend/compiler discovery
- implementation selection and capability fallback policy
- profiles, assets, bindings, execution regions, and security domains
- planning, scheduling, retries, materialization, and run reports
- safe operational I/O and plugin authorization

### Must remain in plugins

- Pandas, Polars, PySpark, SQL, DataFusion, and local-Python realization
- backend-native functions outside declared DTCS portability
- data access, pushdown, collection, materialization, and writes
- engine sessions, credentials, resources, and side effects

## Initial package shape

```text
packages/transformationmodel/
├── pyproject.toml
├── README.md
├── CHANGELOG.md
├── src/transformationmodel/
│   ├── __init__.py
│   ├── py.typed
│   ├── model.py
│   ├── descriptors.py
│   ├── ports.py
│   ├── expressions/
│   ├── capabilities.py
│   ├── interchange/dtcs.py
│   ├── diagnostics.py
│   ├── fidelity.py
│   └── compatibility.py
└── tests/
```

The internal layout may change, but the top-level API must remain small.

## Required public contract

Names are illustrative; the capabilities and boundaries are required.

### Declaration and portable authoring

```python
from transformationmodel import Input, Output, Parameter, TransformationModel


class NormalizeCustomers(TransformationModel):
    source: Input[CustomerRaw]
    country: Parameter[str] = "US"
    result: Output[Customer]
```

Declarations describe transformation interfaces. They do not register
executable callables or create ETLantic pipeline steps. Portable definitions
produce bounded, inspectable expression values and never execute user data or
import a backend during declaration, inspection, validation, or serialization.

### Immutable description

```python
descriptor = NormalizeCustomers.describe()

descriptor.identity
descriptor.version
descriptor.inputs
descriptor.outputs
descriptor.parameters
descriptor.capabilities
descriptor.portable_plan
descriptor.fingerprint
```

Descriptors are deeply immutable, canonically serializable, versioned, and free
of executable callables, live engines, secrets, and source rows.

### DTCS interchange and fidelity

```python
artifact = NormalizeCustomers.to_dtcs()
result = TransformationModel.from_dtcs(artifact)

result.model
result.fidelity
result.diagnostics
```

Import and export use public `dtcs` APIs and never silently accept documents
rejected by the supported toolkit version. Every conversion reports `exact`,
`normalized`, `extended`, `lossy`, `unsupported`, or `rejected` with stable
codes and semantic paths. Lossy conversion requires explicit policy.

### Consumer protocols

```python
class TransformationDescriptorProtocol(Protocol):
    identity: str
    version: str
    fingerprint: str
    capabilities: frozenset[str]


def describe_transformation(value: object) -> TransformationDescriptorProtocol: ...
def is_transformation_model(value: object) -> TypeGuard[type[TransformationModel]]: ...
```

ETLantic and ContractModel integration use public descriptors or protocols,
never package internals or Pydantic internals.

## Dependency policy

Core dependencies stay minimal. `dtcs` uses an explicitly tested compatible
range. ContractModel becomes a direct dependency only if its stable descriptor
protocol is essential to core authoring; otherwise it is an optional extra.

The package must not depend on ETLantic, dataframe or SQL engines, orchestrator
SDKs, plugin frameworks, secret managers, or storage clients.

## Diagnostic and identity contracts

Diagnostics include a stable code, severity, phase, category, bounded path,
optional source location, toolkit origin, and remediation. They never contain
secret values or source rows. Upstream DTCS diagnostic IDs remain visible and
are not replaced by parsed message text.

Before release, the package specifies:

- its descriptor wire-schema identifier and upgrade rules
- canonical JSON, ordering, Unicode, and scalar representation
- extension namespaces and size limits
- exact fingerprint participation rules
- separate DTCS artifact, portable-plan, and authoring fingerprints
- treatment of documentation-only metadata

Callables, memory addresses, environment state, timestamps, and backend
sessions never participate in semantic fingerprints.

## Implementation phases

### TM-0 — Boundary audit and fixtures

Deliver:

- classify candidate symbols as model, integration, pipeline, runtime, or
  plugin concerns
- freeze representative authoring, DTCS, portable-plan, diagnostic, and
  fingerprint fixtures
- inventory public imports from `etlantic.transform` and
  `etlantic.transformation`
- classify ETLantic extensions as DTCS proposals, namespaced metadata, or
  removal candidates
- establish performance and import-time baselines

Exit: representative behavior is protected and every proposed move has an
explicit ownership rationale.

### TM-1 — Package skeleton and semantic kernel

Deliver an independently buildable typed package, declaration types, immutable
descriptors, canonical serialization, fingerprints, diagnostics, fidelity, and
package documentation without ETLantic or backend imports.

Exit: a transformation can be declared, described, serialized, loaded, and
fingerprinted without importing ETLantic.

### TM-2 — DTCS conformance

Deliver DTCS interchange and compatibility through public `dtcs` APIs, a DTCS
and Python support matrix, upstream positive and negative fixtures, diagnostic
mapping, round-trip suites, and parser/expression property tests where useful.

Exit: unsupported semantics never disappear silently, generated documents pass
the upstream validator, and canonical results agree across platforms.

### TM-3 — Portable authoring extraction

Deliver portable expression/dataframe authoring, profile and capability
requirements, deterministic lowering, complexity budgets, and the shared
ETLantic portable corpus.

Exit: the portable kernel and graduated rich profiles pass without weakened
semantics, and inspection/lowering execute no backend or user data.

### TM-4 — ETLantic bridge

Deliver public adapters from descriptors to ETLantic steps and plans,
compatibility re-exports where required, ETLantic-owned implementation
registration, parity tests, and documented deprecations.

Exit: supported transformations retain semantic plan identity or receive an
explicit wire migration, and ETLantic imports no private package modules.

### TM-5 — Independent release and graduation

Deliver independent builds, wheels, SBOM/provenance, trusted publication,
cross-platform Python CI, semver and support policies, isolated install tests,
performance results, and one independent consumer.

Exit: all graduation gates pass and a separately released version succeeds in
ETLantic CI before maintainers approve required-dependency status.

## ETLantic migration strategy

Use incremental delegation rather than a repository-wide move:

1. Introduce the package without changing ETLantic's public API.
2. Mirror frozen fixtures in both packages.
3. Delegate one semantic subsystem at a time through public APIs.
4. Keep compatibility imports while downstream consumers migrate.
5. Move executable registration, step creation, and runtime selection behind
   explicit ETLantic adapters.
6. Remove duplicates only after parity tests pass.
7. Require the dependency only after an independent release proves the seam.

Every temporary dual implementation needs an owner and removal milestone.

## Verification strategy

- unit invariants for immutability, canonicalization, validation, and budgets
- upstream DTCS and ETLantic portable-corpus conformance
- exact, normalized, extended, lossy, unsupported, and rejected conversions
- legacy-versus-package differential tests for descriptors, plans,
  fingerprints, diagnostics, and DTCS artifacts
- isolated source/wheel installs and type-consumer tests
- Linux, macOS, Windows, and supported Python coverage
- absence of ETLantic and optional-backend imports in the core

## Security and reliability requirements

- explicit byte, depth, collection, expression, reference, and diagnostic
  budgets
- no source rows, resolved secrets, or callables in portable evidence
- loading never imports arbitrary modules or executes user code
- unknown wire and DTCS versions fail closed
- extensions are namespaced, JSON-compatible, and bounded
- the semantic core never resolves remote references; an authorized host
  supplies already resolved bounded content
- inspection and validation have no external effects

## Graduation gates

- an independent consumer can author, validate, inspect, round-trip, and diff a
  transformation
- equivalent definitions serialize and fingerprint identically across
  supported Python versions and operating systems
- unsupported and lossy semantics are explicit and fail closed when required
- ETLantic's complete transformation conformance suite passes through the
  package
- the public protocol, semver, deprecation, support, and wire-version policies
  are documented
- `py.typed` ships and installed-wheel consumer tests pass
- backend engines remain optional and model inspection has no external effects
- the package has no dependency on ETLantic internals

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Package is useful only to ETLantic | Require an independent consumer before graduation |
| Circular dependency | Enforce import tests and one-way dependency rules |
| DTCS semantics are duplicated | Delegate normative behavior to public `dtcs` APIs |
| Runtime concerns leak into the model | Keep callables, engines, resources, and plugins in ETLantic |
| Public imports churn | Maintain shims and a documented deprecation window |
| Fingerprints change during extraction | Freeze fixtures; require parity or explicit migration |
| Dual implementations drift | Give every duplicate an owner and removal milestone |
| Core imports become heavy | Set import budgets and keep integrations lazy |

## Decisions required before TM-1

- final distribution and import names (`transformationmodel` is provisional)
- whether ContractModel is core or optional
- the initial descriptor wire-schema version
- which ETLantic imports receive compatibility re-exports
- identity ownership for Python models versus DTCS artifacts
- supported initial `dtcs` and Python ranges
- nested-package release automation

## Definition of done

TransformationModel graduates when it is independently useful, installable,
typed, documented, and released; DTCS remains the normative authority; its
values are immutable, deterministic, and versioned; fidelity is explicit; no
backend or pipeline concern enters its core; ETLantic uses only public APIs;
and all conformance, security, packaging, performance, and migration gates pass.

Until then, it remains provisional and cannot be the sole implementation behind
an ETLantic 0.38 stable-foundation compatibility promise.
