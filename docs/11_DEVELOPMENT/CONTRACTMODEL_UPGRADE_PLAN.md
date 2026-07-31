# ContractModel Upgrade Plan

> **Plan status: historical review baseline with active follow-up work.**
>
> **Current 0.39 boundary:** ETLantic requires ContractModel `>=0.2,<0.3`.
> This document's detailed review targeted ContractModel 0.1.2, so it does not
> define the current upstream API. Proposed interfaces remain illustrative
> unless the current ContractModel or ETLantic reference documents them.
>
> **Authority:** ContractModel owns its shipped API and contract semantics.
> This plan owns ETLantic integration goals that still require validation.
> See [Capabilities](../01_GETTING_STARTED/CAPABILITIES.md) and the
> [Planning Hub](PLAN_INDEX.md).
>
> **Review trigger:** Re-audit when ETLantic's supported ContractModel range
> changes or an open recommendation becomes shipped upstream behavior.

## Review baseline

This document follows a historical review of
[`eddiethedean/contractmodel`](https://github.com/eddiethedean/contractmodel)
at commit `12e8505` (`0.1.2`) and the ETLantic integration that existed at that
time. Revalidate every open recommendation against ContractModel 0.2.x before
implementation.

## Product outcome

ContractModel should be the best Python-native way to turn a data contract into
an operational, portable, inspectable interface:

```text
ODCS or Python authoring
          ↓
versioned canonical contract semantics
          ↓
introspection • validation • compatibility • fidelity evidence
          ↓
pipelines, applications, CI, registries, and engine adapters
```

ContractModel owns what a valid data contract means. ETLantic owns where and
when that contract is applied across a pipeline. Execution plugins own how a
required check is realized efficiently on a backend.

The dependency remains strictly one-way:

```text
ContractModel
      ▲
      │ public, versioned integration API
      │
ETLantic
```

ContractModel must never import ETLantic, [DTCS](../04_TRANSFORMATIONS/DTCS.md), [DPCS](../05_PIPELINES/DPCS.md), pipeline plans,
orchestrators, or dataframe execution plugins.

## Review-baseline strengths

At the reviewed 0.1.2 baseline, ContractModel provided:

- a small `DataContract` facade over a Canonical Contract Model (CCM)
- [ODCS](../03_DATA_CONTRACTS/ODCS.md) and Pydantic round trips
- structured record, JSON, CSV, Parquet, Pandas, and Polars validation
- compatibility modes and structured contract diffs
- JSON Schema, OpenAPI, Markdown, RDF, SHACL, and OWL exports
- a typed package, strict mypy configuration, Ruff, and a 94% coverage gate
- a useful CLI, bundled examples, SARIF, and documented error codes
- explicit API stability tiers and honest experimental labels
- safe YAML loading, file/row limits, bounded registry responses, and
  name-only plugin discovery for `doctor`

The upgrade should consolidate these strengths around a smaller stable
semantic kernel.

## Findings that should shape 0.2+

### The integration surface is implicit

ETLantic repeatedly constructs `DataContract` objects to discover identity,
version, fields, and compatibility. It separately introspects Pydantic fields
to normalize schemas and imports `contractmodel.validation.limits` rather than
a top-level safety API. ContractModel needs an explicit consumer integration
surface so downstream tools do not depend on storage or Pydantic internals.

### Canonical values are not immutable or wire-versioned

CCM models reject unknown properties but contain mutable lists, dictionaries,
`Any` metadata, defaults, examples, thresholds, and extensions. There is no
published CCM wire-schema identifier, canonical byte encoding, or contract
fingerprint API. This weakens cache identity and cross-process evidence.

### Fidelity is represented unevenly

ODCS imports record selected warnings, but fidelity is not a uniform result of
every conversion. Consumers need exact, normalized, extended, lossy,
unsupported, or rejected outcomes with stable codes and contract paths.

### Validation is not yet a scalable protocol

`validate_records()` materializes iterables. File/dataframe validation is
whole-input oriented. Results may contain raw invalid values, which is useful
locally but unsafe by default for logs, reports, SARIF, and pipeline evidence.
ContractModel needs bounded streaming, diagnostic budgets, redaction,
cancellation, and engine-neutral request/result models.

### Native and pushed-down checks need one truth model

Pydantic, Pandas, Polars, SQL, and Spark enforce overlapping subsets of the
same rules. ContractModel should publish normalized validation requirements and
semantic capabilities. It should not absorb SQL, Spark, scheduling, or pipeline
execution.

### Plugin and registry trust remain experimental

`doctor` lists entry-point names without loading code, but execution imports
plugins without a manifest, protocol version, allowlist, provenance, or
capability validation. Registry URLs can target unsafe addresses or redirects,
and environment credentials need origin binding. These surfaces should remain
experimental until they fail closed.

### Adapter count is prioritized too early

The current roadmap quickly expands to JSON Schema, OpenAPI, Avro, Protobuf,
Parquet, dbt, lakehouse, event, and catalog adapters. New formats should follow
a stable adapter/fidelity protocol, canonical type system, and conformance
suite rather than define semantics incrementally.

### Release assurance needs a stable 0.x path

CI covers Python 3.10–3.12 on Linux. The stable path should add current Python,
Windows/macOS, isolated wheels, minimal dependencies, optional-extra matrices,
performance budgets, property/fuzz tests, SBOM/provenance, signed artifacts,
and trusted publishing.

## Ownership boundary

### ContractModel owns

- the versioned Canonical Contract Model
- Python/Pydantic normalization and ODCS version policy
- logical types, nullability, constraints, quality declarations, and metadata
- contract identity, semantic version, canonical serialization, and fingerprint
- validation requirement semantics and reference record validation
- compatibility and contract-evolution classification
- import/export fidelity findings
- safe contract loading and bounded validation
- structured, redactable validation and compatibility evidence
- adapter and validator conformance suites

### ETLantic owns

- pipeline graph semantics and identities
- `Extract`, transformations, `Load`, and subpipelines
- DTCS and DPCS integration
- profiles, bindings, plugin selection, and security domains
- deciding where and when contract validation occurs
- fail, reject, quarantine, or warn outcome policy
- execution regions, materialization, retries, scheduling, and orchestration
- plans, run reports, lineage, and artifacts
- mapping ContractModel logical types to DTCS/backend protocols

### Execution plugins own

- compiling normalized requirements to backend-native checks
- truthful capabilities for rules they preserve
- data access, vectorization, pushdown, materialization, and collection
- normalized evidence without redefining ContractModel semantics

## Required public integration API

Names are illustrative; the capabilities are required.

### Recognition

```python
def is_contract_model(value: object) -> TypeGuard[type[ContractModel]]: ...
def resolve_contract_model(annotation: object) -> type[ContractModel] | None: ...
```

### Immutable normalized introspection

```python
descriptor = describe_contract(Customer)

descriptor.identity
descriptor.version
descriptor.schema
descriptor.fingerprint
descriptor.provenance
descriptor.fidelity
```

The descriptor must be deeply immutable, versioned, canonically serializable,
and free of live classes, callables, source rows, and secrets. It must preserve
nested object/array/map/enum, decimal, temporal, binary, UUID, URI, email, and
extension types and distinguish required, optional, nullable, defaulted, and
missing values.

### Generated-model identity

ContractModel should attach and preserve contract ID, version, canonical
fingerprint, source format/version, provenance, and fidelity when generating a
Pydantic class. Reconstructing a contract from that class must not silently
replace published identity or version with inferred defaults.

### Compatibility report

```python
report = compare_contracts(old, new, mode=CompatibilityMode.BACKWARD)
```

The versioned report should contain source/target identities and fingerprints,
policy version, overall category, and stable path-specific findings with old
and new normalized values, rationale, and remediation. Consumers should not
parse messages or recompute compatibility.

### Validation specification and result

```python
spec = contract.validation_spec()
result = contract.validate_records(records, request=request)
```

The immutable specification describes required checks without data access. The
request/result should support row/byte/error/warning/depth/time budgets,
batching, cancellation, redaction, stable diagnostics, applied/skipped/
unsupported/approximate outcomes, and engine evidence. Invalid rows belong in
opaque runtime handles, never serialized results. Raw values should be excluded
by default with bounded opt-in debugging only.

### Safe loading policy

All loaders should accept one public policy covering approved roots, normalized
paths, symlinks, special files, byte/depth/collection/reference limits, allowed
formats/versions, remote resolution, and diagnostic budgets. Consumers should
not import `contractmodel.validation.limits`.

### Adapter fidelity result

Every import/export should expose a versioned report with exact, normalized,
extended, lossy, unsupported, or rejected status and path-specific findings.
Lossy output must require explicit policy.

## 0.2 — Semantic kernel and integration API

### Deliver

- publish `contractmodel.ccm/1` and its complete JSON Schema
- add immutable descriptor, schema, field, constraint, identity, provenance,
  fidelity, and fingerprint values
- define canonical JSON and exact fingerprint participation rules
- preserve identity/version/provenance across ODCS → Pydantic → CCM round trips
- add public recognition and annotation-resolution helpers
- add a public bounded loading policy
- define extension namespaces, JSON-value constraints, and size budgets
- publish supported ODCS and Pydantic ranges; cap Pydantic below v3
- classify every export as stable, provisional, experimental, or private

### Acceptance

- equivalent contracts have identical bytes/fingerprints across supported
  Python versions and operating systems
- nested mutation cannot alter a descriptor or fingerprint
- round trips retain identity, version, nested meaning, and fidelity evidence
- ETLantic obtains identity, schema, nullability, constraints, and fingerprint
  without `model_fields` or private imports
- unsupported or oversized documents fail before class generation

### Exit gate

ETLantic can implement its data-contract analysis boundary using only
documented top-level ContractModel APIs.

## 0.3 — Bounded validation protocol

### Deliver

- publish versioned immutable validation specification and result schemas
- make diagnostic budgets deterministic and redact values by default
- validate iterators/batches without unconditional materialization
- define cancellation, timeout, partial-result, and cleanup semantics
- distinguish exact, approximate, unsupported, skipped, and failed checks
- expose invalid-row separation only through runtime handles
- separate the reference engine from optional engine adapters
- publish a validation-engine conformance suite

### Acceptance

- unbounded iterators cannot exhaust memory before crossing a configured budget
- row/error/time limits stop deterministically with partial counts
- results, SARIF, and logs contain no source values by default
- Pydantic, Pandas, and Polars agree on their advertised intersection
- external engines report unsupported rules without silently passing them

## 0.4 — Adapter and fidelity framework

### Deliver

- publish a versioned adapter protocol and static manifest
- declare format/version ranges, capabilities, fidelity, and dependency tier
- add bounded contexts and structured fidelity results
- create golden and property-based round-trip suites
- graduate ODCS under the protocol, then JSON Schema
- prioritize formats by semantic coverage and user value, not count

### Acceptance

- exact round trips are semantically equivalent and fingerprint-stable
- lossy paths identify every transformed or dropped element
- unsupported versions fail closed
- optional dependencies remain absent from core imports
- third-party adapters pass public fidelity conformance

## 0.5 — Compatibility and evolution

### Deliver

- version compatibility policy independently from CCM
- define identical, compatible, conditional, breaking, and unknown outcomes
- cover nested, rename, default, required/nullable, enum, numeric, temporal,
  composite, constraint, key, index, and semantic changes
- distinguish producer, consumer, backward, forward, and full compatibility
- add deterministic migration guidance and machine-readable actions
- provide CCM/result schema migration functions and historical fixtures

### Acceptance

- every stable type/constraint has documented compatibility semantics
- aliases cannot hide breaking semantic changes
- unknown extensions do not become optimistically compatible
- ETLantic maps structured findings without parsing messages

## 0.6 — Trust, plugins, and registries

### Deliver

- split plugin discovery, evaluation, authorization, and loading
- inspect static manifests without importing entry points
- version protocols and capabilities; add allowlists, version ranges,
  provenance/digests, duplicate detection, and conflicts
- add adversarial conformance and an external reference plugin
- enforce registry scheme/host/address, redirect, TLS, timeout, response, and
  private/metadata-target policy
- bind credentials to approved origins and support digest/signature checks
- emit security events without credentials or source samples

### Acceptance

- disallowed plugins are rejected without import
- trusted names alone cannot grant behavior
- unsafe registry destinations and redirects fail by default
- errors expose no tokens or credential-bearing URLs

## 0.7 — Developer experience and CLI

### Deliver

- organize CLI workflows around `init`, `inspect`, `validate`, `diff`,
  `convert`, `export`, `doctor`, and optional `registry`
- standardize human/JSON/SARIF diagnostics and exit codes
- add consistent dry-run, color, quiet, verbose, and non-interactive behavior
- declare targets and overwrite policy for every mutation
- make `doctor` inspect manifests and safety without loading plugins
- generate deterministic importable Python and type-check it
- publish focused guides for users, adapter/engine authors, and integrators

### Exit gate

The CLI is a projection of the public library API, not parallel semantics.

## 0.8 — Performance and conformance

### Deliver

- set time/memory budgets for loading, normalization, generation, validation,
  diffing, and export
- benchmark nested/wide contracts and representative data sizes
- add Hypothesis properties and malformed/deep/recursive fuzz corpora
- test Linux, macOS, Windows, and every supported Python line
- test minimal core and each extra from isolated wheels
- test ETLantic against minimum and latest ContractModel versions
- publish conformance packages for external engines/adapters

### Acceptance

- budget regressions fail CI or require reviewed budget changes
- core import does not import optional engines or semantic/registry code
- adversarial inputs terminate within configured bounds
- source and wheel behavior match

## 0.9 — Stable-foundation release candidate

- freeze API, CCM, descriptor, validation, compatibility, diagnostic, fidelity,
  adapter, and plugin snapshots
- rehearse upgrades from every supported 0.x artifact
- publish removals and migrations for deprecated 0.1 APIs
- complete security control-to-test traceability
- generate SBOMs and signed provenance; use trusted publishing
- run source, sdist, and wheel acceptance everywhere supported

The exact candidate must pass compatibility, security, upgrade, rollback,
packaging, performance, and ETLantic integration rehearsals unchanged.

## 0.10 — Stable data-contract foundation

ContractModel 0.10 ships only when:

- canonical and public result schemas are versioned and stable
- canonical bytes and fingerprints are deterministic and verified
- Python/ODCS round trips publish complete fidelity evidence
- validation is bounded, redactable, cancellable, and engine-conformant
- compatibility covers every stable logical type and constraint
- plugin and registry trust boundaries fail closed
- supported adapters pass round-trip/fidelity conformance
- CLI and library expose the same semantics
- minimal and optional installations pass isolated wheels
- ETLantic depends only on stable public APIs
- ContractModel has no ETLantic or pipeline-specific dependency

## ETLantic adoption plan

### 1. Define shared fixtures

Convert the required integration surface into executable protocol/schema
fixtures. Cover nested fields, aliases, constraints, defaults, nullability,
decimals, temporal types, enums, arrays, maps, and extensions. Keep ETLantic's
internal adapter while ContractModel 0.2 develops.

### 2. Run dual-version acceptance

Test ETLantic against 0.1.2 and 0.2 prereleases. Compare identities,
fingerprints, ODCS, diagnostics, compatibility, and validation outcomes. Do not
change ETLantic plan semantics to match a prerelease accident.

### 3. Replace duplicated behavior

- subclass/annotation checks → ContractModel recognition helpers
- repeated identity conversion → descriptor identity
- direct `model_fields` normalization → normalized schema view
- private limits import → public safety policy
- message-level diff mapping → structured compatibility findings
- ad hoc model attributes → supported identity/provenance metadata

ETLantic retains DTCS projection, physical schema observations, pipeline drift
policy, validation placement/outcomes, plans, artifacts, security domains, and
run reports.

### 4. Pin and support deliberately

After validation, pin a bounded range such as `contractmodel>=0.2,<0.3`, test
its lowest and newest versions, and require migration evidence before widening.
Record the ContractModel version, descriptor schema, compatibility policy, and
contract fingerprints in ETLantic evidence where relevant.

### 5. Rehearse 0.10 interoperability

Jointly prove code-first/ODCS equivalence, identity preservation, validation
parity, structured compatibility, secret/source-row-free evidence, fail-closed
loss handling, and stable pipeline plans across supported upgrades. The two
projects do not need lockstep versions or release schedules.

## Prioritization rule

Prefer semantic depth over integration count:

1. canonical semantics and identity
2. bounded validation and evidence
3. compatibility and fidelity
4. trust and conformance
5. developer experience
6. additional formats and registries

A new adapter should not outrank a missing guarantee in the canonical model it
targets.

## Success measures

- ETLantic imports no private ContractModel modules
- one descriptor replaces repeated Pydantic introspection
- equivalent contracts have stable cross-process fingerprints
- validation results are source-row-free by default
- adapter losses are machine-readable and path-specific
- third-party validators/adapters pass public conformance
- unsafe plugins and registry destinations fail before effects
- core-only import remains lightweight
- scale and compatibility are measured rather than implied
