# Portable Transformation Implementation Plan

Status: Internal project plan  
DTCS plan protocol: `dtcs.transform-plan/2` (v1 readable)  
ETLantic authoring profile: `etlantic.transform/1`  
Compiler protocol: `etlantic.transform-compiler/1`  
Current release boundary: authoring shipped in 0.11.0; compilers from 0.12
DTCS baseline: specification 3.0.0 / toolkit `dtcs>=0.13`

## Outcome

Authors define relational transformation logic once through a PySpark-inspired
DataFrame and Column API. ETLantic validates a closed portable IR, then Polars,
Pandas, SQL, and PySpark plugins compile it without changing its meaning.

## Success criteria

- A portable definition is deterministic, serializable, inspectable, and
  secret-free.
- The same definition executes with contract-equivalent results on at least
  Polars and PySpark before the protocol is declared stable.
- Unsupported operations fail during planning with an expression path.
- Polars and Spark preserve lazy/native expression execution.
- SQL lowering remains parameterized and contains no trusted raw SQL.
- Existing native `@implementation()` behavior remains compatible.
- Plugin conformance tests prove every advertised operation.

## Workstreams

| Workstream | Deliverable |
|---|---|
| Authoring | `@Transformation.portable`, symbolic DataFrame/Column API |
| DTCS kernel | canonical nodes, type system, semantics, serialization, fingerprint |
| Analysis | definition, name, type, contract, and bounded-structure validation |
| Planning | capability extraction, compiler selection, explain output |
| Runtime | compiled-transform execution and normalized outputs |
| Plugins | Polars, PySpark, Pandas, then SQL compilers |
| Interchange | DTCS extension and plan-schema representation |
| Assurance | security limits, golden files, conformance and differential tests |
| DX | diagnostics, symbols, source paths, docs, IDE schemas |

## Package layout

Proposed ETLantic facade modules:

```text
src/etlantic/transform/
├── __init__.py
├── dataframe.py
├── column.py
├── functions.py
├── window.py
├── complex.py          # list/map/object constructors and accessors
├── lambda_expr.py      # bounded lambda authoring helpers
├── dtcs_builder.py
├── validate.py
├── capabilities.py     # requirement extraction for later planning (stubs ok in 0.11)
├── protocol.py
└── discovery.py        # compiler discovery — used from 0.12+
```

Canonical nodes, portable types, semantics, serialization, and base validation
belong to public `dtcs` package modules. ETLantic MUST NOT duplicate those
models. The ETLantic core MUST NOT import backend libraries. Existing
`etlantic.sql` types may receive a lowering from the DTCS plan, but SQL types do
not become the portable model.

See [DTCS and Portable Transformation Evolution](DTCS_PORTABLE_EVOLUTION.md)
for the coordinated specification/package release workflow.
Normative DTCS foundations are recorded in:

- [DTCS 2.0 Portable Relational Publication Record](DTCS_PORTABLE_SPEC_PROPOSAL.md)
- [DTCS 3.0 Rich Portable Analytics Publication Record](DTCS_3_0_SPEC_PROPOSAL.md)

## 0.11: full portable authoring

DTCS readiness is satisfied by DTCS 3.0 / `dtcs` 0.13. This phase owns the
complete facade → validated `dtcs.transform-plan/2` path for Portable Relational
and Rich Portable Analytics. It does not mint parallel ETLantic semantics and
does not execute through compilers.

### Decisions and fixtures

- accept ADR-013 and the IR specification
- freeze facade→`dtcs:` mappings for every claimed profile family
- emit **only** `dtcs.transform-plan/2` for new definitions (v1 readable)
- audit published null, missing, and invalid behavior for authoring fidelity
- define canonical JSON examples before Python classes
- create semantic truth tables and golden IR per profile family
- define `PMXFORM` diagnostic allocation and source-path format
- benchmark acceptable definition and validation overhead

### Authoring deliverables

- `FrameExpr`, `ColumnExpr`, `GroupedData`, Window helpers, complex-value
  helpers, and bounded lambda helpers
- `@Transformation.portable` with symbolic input and parameter binding
- complete facade coverage for the profile table below
- profile requirement emission on every serialized plan
- prohibited action, boolean-conversion, raw SQL, callable, and secret-capture
  errors
- preservation of distinct DTCS null, missing, and invalid values
- deterministic serialization, fingerprints, definition validation, and output
  binding

### Profile → facade → IR → fixtures

| DTCS profile | Facade modules | Representative IR constructs | Fixture ownership |
|---|---|---|---|
| `portable-relational-kernel/1` | `dataframe`, `column`, `functions` | project, filter, with_fields, rename/drop, scalar ops | golden kernel plans |
| `portable-relational-kernel/2` | same + plan v2 metadata | plan/2 document shape, registry pins | plan v2 round-trip |
| `portable-relational/1` | `dataframe`, `functions` | join, union, group, aggregate, sort, distinct, limit | multi-input relational IR |
| `portable-relational/2` | same | relational/2 candidate extensions | candidate relational IR |
| `portable-string-advanced/1` | `functions` | regex, split, pad, translate, … | string-advanced IR |
| `portable-conversion/1` | `functions` | strict cast / parse family | conversion IR |
| `portable-statistics/1` | `functions` | stddev, variance, corr, … | statistics IR |
| `portable-complex-values/1` | `complex`, `lambda_expr` | constructors, accessors, lambdas | complex + lambda IR |
| `portable-reshape/1` | `dataframe` | explode / reshape actions | reshape IR |
| `portable-relational-extended/1` | `dataframe` | extended relational actions | relational-extended IR |
| `portable-temporal-iana/1` | `functions` | IANA timezone / calendar ops | temporal-iana IR |
| `portable-nondeterministic/1` | `functions` | random, uuid, run-context | nondeterministic IR |
| `portable-window/2` (+ `/1` alias) | `window`, `functions` | window specs and analytics | window IR |
| `portable-complex-types/1` alias | `complex` | list/map/object subset of complex-values | alias compatibility |

Candidate and Experimental profiles are authorable and fingerprintable in 0.11;
they are not graduated to Standard until 0.12+ compilers pass two-engine
conformance.

### Tests

- unit tests for every facade method claimed in the table
- inheritance and multiple-output cases
- unknown argument, missing output, ambiguous column, and type errors
- recursion, depth, node-count, literal-size, lambda, and hostile-object limits
- golden canonical JSON and fingerprint stability per profile family

### Exit gate

Definitions generate validated `dtcs.transform-plan/2` for the full published
authoring surface, but do not execute.

## 0.12: planning integration

Deliver (compile/plan only; authoring already complete in 0.11):

- `TransformCapabilities` and requirement extraction from 0.11 IR
- compiler descriptors and discovery
- implementation policy: `require`, `prefer`, `native`
- `ImplementationDescriptor` extension for `portable_compiled`
- plan schema update with IR fingerprint, requirements, compiler identity, and
  optional embedded IR or stable artifact reference
- `plan explain` rendering
- diagnostics for unsupported operations and semantic modes
- cache and artifact identity inclusion of IR and compiler fingerprints

Decisions required:

- Embed full IR in `PipelinePlan` versus reference a content-addressed IR
  artifact. Recommendation: embed bounded canonical IR for portability, with a
  future external reference for oversized definitions.
- Whether portable compilation outranks native implementations by default.
  Recommendation: `prefer`, with an explicit profile policy and no silent
  fallback.

Exit gate: planning chooses a compiler deterministically and fails closed when
requirements are unsupported.

## 0.12: Polars vertical slice

Deliver:

- Polars compiler claiming an initial set (start with
  `dtcs:profile/portable-relational-kernel/*`; expand as fixtures land)
- native `pl.Expr` lowering
- eager and lazy input support
- lazy preservation and declared collection boundaries
- existing input/output validation integration
- multiple valid, invalid, and side outputs
- explain metadata and dataframe metrics

Exit gate: a complete example runs without a Polars-specific transformation
callable and retains `LazyFrame` through compatible regions.

## 0.13: PySpark compiler

Deliver:

- native Spark Column/DataFrame lowering for advertised claims
- Catalyst-visible expression verification
- Spark session and region integration
- explicit prohibition of UDF fallback
- type, timezone, null, and ownership conformance

Exit gate: Polars and PySpark pass the same semantic fixture corpus for shared
claims.

## 0.13: relational compiler claims

This phase targets complete **compiler** conformance with
`dtcs:profile/portable-relational/1` (authoring already covers the IR in 0.11),
including every advertised join and union mode rather than generic
operation-name checks.

Deliver:

- join, union-by-name, group-by, aggregation, deduplication, and full ordering
  under execution
- relation-scoped column resolution at compile time
- collision diagnostics
- aggregate typing and empty-input behavior
- Polars and PySpark implementations first

Exit gate: multi-input and aggregate examples pass differential tests.

## 0.14: Pandas compiler and conformance SDK

Deliver:

- eager lowering for all advertised kernel and relational capabilities
- index-neutral semantics
- ownership/copy declarations
- nullable dtype and Arrow-assisted behavior where available
- honest rejection where Pandas cannot preserve semantics

Exit gate: Pandas passes every fixture associated with its advertised
capabilities and does not claim unsupported lazy behavior.

## 0.15: SQL lowering and profile graduation

Deliver:

- portable IR to ETLantic SQL IR lowering
- safe identifier and bound-literal handling
- CTE/region fusion while retaining logical identities
- dialect capability mapping
- no trusted fragments in portable definitions
- cross-engine database integration fixtures
- two-compiler graduation path for Rich Portable Analytics and related
  Candidate/Experimental families already authored in 0.11

Exit gate: supported portable definitions compile to safe SQL and match the
reference result corpus; graduated families meet two-compiler criteria.

## 0.15+: graduating advanced families

Compiler claims for windows, arrays, maps, structs, and advanced functions ship
one semantic family at a time. Each graduation requires two compilers, shared
fixtures, capability identifiers, and explain rendering. Authoring for these
families already exists in 0.11; this work is execution and conformance only.

Starting standards remain the experimental
`dtcs:profile/portable-window/1` /
`dtcs:profile/portable-complex-types/1` families and the DTCS 3.0 Rich
Portable Analytics profiles (`portable-window/2`, `portable-complex-values/1`,
string-advanced, reshape, and peers). ETLantic authoring aliases normalize
arrays to DTCS lists and structs to DTCS objects.

## DTCS and Pipeline Plan integration

ETLantic's `PipelinePlan` should reference or embed the canonical DTCS plan
without changing its content. An illustrative ETLantic integration block is:

```yaml
implementation:
  portableDefinition:
    protocol: dtcs.transform-plan/2
    authoringProfile: etlantic.transform/1
    fingerprint: sha256:...
    plan: {}
```

Native implementations remain separate execution metadata. Loading a DTCS
artifact reconstructs data-only IR and never imports Python definition code.

The `PipelinePlan` schema needs:

- implementation kind
- portable protocol and fingerprint
- compiler identity and version
- requirements and support decisions
- deterministic/nondeterministic classification
- safe definition representation or content-addressed reference

Plan schema changes require compatibility fixtures and migration guidance.

## Diagnostics

Reserve `PMXFORMxxx`:

| Range | Purpose |
|---|---|
| `PMXFORM1xx` | authoring and signature errors |
| `PMXFORM2xx` | name, type, contract, and output validation |
| `PMXFORM3xx` | plugin capability and compiler selection |
| `PMXFORM4xx` | compilation failures and semantic mismatches |
| `PMXFORM5xx` | runtime portable-transform failures |
| `PMXFORM8xx` | security and bounded-input rejection |
| `PMXFORM9xx` | internal invariants |

Every expression diagnostic includes transformation identity, output port,
expression path, stable requirement identifier, and remediation when possible.

## Testing strategy

### Unit and golden tests

- operators, nodes, types, canonicalization, and fingerprints
- serialized IR and plan schema
- explain and diagnostics output

### Conformance tests

Plugins run fixtures selected from advertised capabilities. Capability claims
must fail CI if the associated fixture is missing or failing.

### Differential tests

Generate bounded datasets containing nulls, NaN, extreme numbers, Unicode,
decimal edges, timezone transitions, duplicate keys, and empty inputs. Execute
the same IR across engines and compare normalized contract values.

### Property tests

Use property-based tests for type promotion, three-valued boolean logic,
canonicalization, deterministic fingerprints, and expression rewrites.

### Security tests

- hostile depth and node count
- oversized strings and literal collections
- executable-object rejection
- secret wrapper and secret-like value redaction
- unsafe SQL identifiers and injection payloads
- plugin allowlist and version mismatch
- no data access during planning

## Documentation gate

Before marking the feature available:

- convert accepted-design examples into runnable tests
- update capabilities and known limitations
- publish a complete supported-operation matrix per plugin
- document semantic differences that are rejected, not approximated
- add migration guidance for teams replacing native implementations
- generate API reference from the shipped public modules

## Risks

| Risk | Mitigation |
|---|---|
| Familiar syntax implies full PySpark parity | publish explicit support matrix and excluded APIs |
| Backend semantic drift | normative semantics and differential conformance |
| IR grows into a general programming language | keep it closed, relational, and action-free |
| Plugin capability overclaim | capability-selected mandatory fixtures |
| Planning executes author code | static IR loading; symbolic decorator invocation only in trusted import path |
| Plans leak values | symbolic parameters, bounded literals, redaction, secret rejection |
| Optimization loses attribution | preserve logical expression and step mappings |
| Too much initial scope | kernel first; joins, windows, and complex types gated separately |

## Definition of done

The first public release is done only when:

1. The normative protocol and Python API agree.
2. Polars and PySpark independently pass kernel conformance.
3. Planning explains every compiler and fallback decision.
4. Unsupported semantics fail before execution.
5. Security and serialization gates pass.
6. Existing native implementations remain compatible.
7. Documentation examples execute in CI.
