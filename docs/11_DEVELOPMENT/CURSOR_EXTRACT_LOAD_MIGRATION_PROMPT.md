# Cursor Prompt: Extract, Load, and Asset Vocabulary Migration

Copy the prompt below into Cursor from the root of the ETLantic repository.

---

You are a senior Python framework maintainer working in the ETLantic
repository.

Implement a deliberate public vocabulary migration:

- `Source[T]` becomes `Extract[T]`.
- `Sink[T]` becomes `Load[T]`.
- Public `binding=` becomes `asset=`.

This is an authoring-language change, not a new architectural layer. `Extract`
and `Load` must preserve the existing Source/Sink graph semantics, planning
behavior, DPCS representation, execution behavior, lineage, and plugin
boundaries.

Target release policy:

- ETLantic 0.15:
    - `Extract`, `Load`, and `asset=` become the preferred public API.
    - `Source`, `Sink`, and `binding=` remain temporarily supported.
    - Every use of the legacy vocabulary emits an appropriate
      `DeprecationWarning`.
- ETLantic 0.16+:
    - Remove `Source`, `Sink`, and public `binding=`.
    - Remove compatibility aliases and deprecated constructor paths.
    - `Extract`, `Load`, and `asset=` become the only supported public
      authoring vocabulary.

Do not introduce separate Extract/Load execution models. They are replacements
for Source and Sink, not additional node kinds.

## Desired authoring experience

```python
from etlantic import Data, Extract, Input, Load, Output, Pipeline, Transformation


class RawCustomer(Data):
    customer_id: int
    email: str


class Customer(Data):
    customer_id: int
    email: str


class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    result: Output[Customer]


class CustomerPipeline(Pipeline):
    customers: Extract[RawCustomer] = Extract(
        asset="customers.raw",
    )

    normalized = NormalizeCustomers.step(
        customers=customers,
    )

    curated: Load[Customer] = Load(
        input=normalized.result,
        asset="customers.curated",
    )
```

The API must remain declarative:

- Constructing an `Extract` must not read data.
- Constructing a `Load` must not write data.
- Runtime plugins continue to perform physical reads and writes.
- Profiles continue to resolve logical asset names to environment-specific
  implementations.
- Plans, contracts, reports, and diagnostics must remain secret-free.

## Terminology

Use these definitions consistently:

- `Extract[T]`: a typed logical entry boundary that introduces data governed
  by `T` into a pipeline.
- `Load[T]`: a typed logical publication boundary that receives data governed
  by `T`.
- `asset`: the stable logical identity resolved by profiles and plugins.
- `binding`: an internal planning/resolution concept only, if still useful
  internally.

Do not describe `asset` as a filesystem path, connection string, table name,
credential, or backend client. Physical resolution belongs to profiles and
plugins.

## Phase 1: repository audit

Before editing, inspect the complete repository for:

- `Source`
- `Sink`
- `binding`
- source/sink node kinds and descriptors
- source/sink plan records
- DPCS serialization and loading
- profile binding resolution
- storage, dataframe, SQL, and PySpark plugins
- runtime execution
- validation and diagnostics
- lineage and visualization
- examples and tests
- public imports and `__all__`
- generated schemas
- CLI output
- documentation navigation
- changelog, roadmap, compatibility, migration, and deprecation policies

Classify every occurrence as one of:

1. Public Python authoring vocabulary — rename.
2. Public documentation or diagnostics — rename or provide migration language.
3. Stable external-standard vocabulary such as DPCS — preserve if required.
4. Internal graph/planning terminology — preserve where changing it adds no
   user value.
5. Plugin protocol field — assess compatibility before changing.
6. Test fixture or golden artifact — update intentionally.

Do not perform a blind global replacement.

## Phase 2: ETLantic 0.15 compatibility implementation

Introduce `Extract[T]` and `Load[T]` as the canonical public classes.

Preferred approach:

- Rename the canonical implementation classes if doing so is safe.
- Preserve `Source` and `Sink` as explicit deprecated compatibility aliases or
  thin wrappers during 0.15.
- Ensure runtime type checks, generic annotations, class discovery,
  introspection, serialization, equality, hashing, and graph construction work
  identically through the new names.
- Avoid maintaining two independent implementations.

Add `asset=` as the canonical constructor parameter.

During 0.15, this is preferred:

```python
Extract[Customer](asset="customers")
Load[Customer](input=result, asset="customers")
```

Legacy calls remain functional but warn:

```python
Source[Customer](binding="customers")
Sink[Customer](input=result, binding="customers")
```

Also support transitional calls where necessary:

```python
Extract[Customer](binding="customers")
Load[Customer](input=result, binding="customers")
```

Every legacy form must emit `DeprecationWarning` with:

- the deprecated name
- the replacement
- the removal version, 0.16
- a concise migration example

Example message:

```text
Source and binding= are deprecated in ETLantic 0.15 and will be removed in
0.16. Use Extract(asset=...) instead.
```

Do not emit warnings for internal framework reconstruction, safe contract
loading, or deserialization paths users did not author directly. Avoid
duplicate warnings for a single declaration.

Define conflict behavior:

- Supplying both `asset=` and `binding=` must fail with a clear `TypeError` or
  model-definition diagnostic.
- Empty asset identifiers must fail validation.
- Asset identifiers must remain logical and deterministic.
- Existing binding normalization rules should apply to `asset=` unless a
  documented change is necessary.

## Phase 3: internal normalization

Normalize the new public vocabulary into the existing logical representation.

It is acceptable for internal and external-standard structures to retain names
such as:

- source node
- sink node
- source binding
- sink binding
- DPCS source/sink

Do not change stable DPCS meaning merely to match Python vocabulary.

Where internal records expose public-facing properties, prefer:

```python
extract.asset
load.asset
```

A deprecated `.binding` property may remain in 0.15 with a warning if it was
publicly accessible. Remove it in 0.16.

Preserve:

- graph topology
- deterministic identifiers
- plan fingerprints, unless public vocabulary is intentionally semantic
- validation boundaries
- source and sink lineage roles
- execution selection
- plugin capability requirements
- materialization behavior
- read/write behavior
- contract compatibility
- DPCS round trips

Equivalent 0.14 and 0.15 declarations should normalize to semantically
equivalent plans.

## Phase 4: profile vocabulary

Evaluate the current profile binding configuration. Prefer public
asset-oriented configuration for 0.15:

```python
Profile(
    name="production",
    assets={
        "customers.raw": ...,
        "customers.curated": ...,
    },
)
```

If separate source/sink maps remain necessary internally, provide a documented
normalization boundary from public `assets` to those maps.

Do not combine resolved credentials or live clients with logical asset
references.

If replacing profile fields creates excessive scope, document and implement a
staged migration. Any retained legacy profile-binding field must follow the
same 0.15 warning and 0.16 removal policy.

## Phase 5: diagnostics and user-facing output

Update public diagnostics to say:

- Extract instead of Source when discussing Python authoring.
- Load instead of Sink when discussing Python authoring.
- Asset instead of binding when discussing the logical identifier.

Preserve source/sink terminology when discussing graph theory, DPCS, lineage
roles, or compatibility-sensitive plugin protocol fields.

Diagnostics for common mistakes must be actionable:

```text
Extract 'customers' has no asset resolution in profile 'production'.
```

```text
Load 'curated' requires asset 'customers.curated', but the selected plugin
cannot satisfy the requested write semantics.
```

## Phase 6: public exports and typing

Update:

- top-level `etlantic` exports
- public module exports and `__all__`
- generated API documentation
- type annotations and generic aliases
- stub files, if present
- IDE schemas and completion metadata
- introspection output

In 0.15, legacy imports must continue working:

```python
from etlantic import Source, Sink
```

Determine whether warning at import or construction time provides the best
signal without noisy transitive warnings. Prefer construction-time warnings
unless project conventions require otherwise.

The new API must type-check naturally:

```python
raw: Extract[RawCustomer]
curated: Load[Customer]
```

## Phase 7: documentation migration

Update all documentation, not only the API reference:

- README and docs home page
- installation, quickstart, and first pipeline
- core concepts and architecture
- pipeline guide
- Extract and Load reference pages
- profiles and asset resolution
- execution model and plugin documentation
- DPCS documentation
- examples
- API reference and compatibility matrix
- known limitations and FAQ
- roadmap and changelog
- migration and deprecation policies
- contributor documentation
- diagrams, snippets, and documentation navigation

Use `Extract`, `Load`, and `asset=` in all primary examples.

Legacy `Source`, `Sink`, and `binding=` should appear only in:

- the 0.15 migration guide
- deprecation documentation
- historical release notes
- external-standard explanations where necessary
- explicit before/after examples

Add a migration page with this mapping:

| ETLantic ≤0.14 | ETLantic 0.15 |
|---|---|
| `Source[T]` | `Extract[T]` |
| `Sink[T]` | `Load[T]` |
| `binding=` | `asset=` |
| source binding configuration | asset resolution configuration |
| `.binding` | `.asset` |

Include before-and-after examples and state clearly:

> Extract and Load are renamed authoring primitives. They do not introduce new
> execution stages or alter pipeline semantics.

Update the roadmap:

- 0.15 introduces the new vocabulary and deprecation warnings.
- 0.16 removes the old public names and compatibility paths.

## Phase 8: tests

Add or update tests for the new API:

- `Extract[T](asset=...)`
- `Load[T](input=..., asset=...)`
- generic typing behavior
- pipeline class discovery and graph construction
- validation and planning
- execution
- lineage and visualization
- contract generation
- DPCS serialization and loading
- profile resolution
- plugin execution
- deterministic fingerprints

Add deprecation tests proving:

- `Source` warns in 0.15.
- `Sink` warns in 0.15.
- `binding=` warns in 0.15.
- `.binding` warns if retained.
- Messages include 0.16 removal guidance.
- New syntax emits no deprecation warnings.
- Internal deserialization does not produce noisy warnings.
- Supplying `asset=` and `binding=` together fails.
- Warning stack levels point to user code.

Construct equivalent legacy and new pipelines and prove:

- identical graph shape
- identical contract identities
- identical source/sink lineage roles
- equivalent DPCS artifacts
- equivalent plan requirements
- equivalent execution results
- equivalent plugin selection
- equivalent security and redaction behavior

If fingerprints intentionally change, document why and provide migration tests.

## Phase 9: ETLantic 0.16 removal plan

Do not necessarily implement the 0.16 removal on the 0.15 branch, but document
and isolate everything that must be deleted:

- `Source` and `Sink` exports
- compatibility aliases or wrappers
- `binding=` constructor support
- `.binding` compatibility property
- legacy profile binding fields
- deprecation-warning code
- legacy tests
- transitional documentation

Compatibility code should be easy to remove without rewriting the canonical
`Extract` and `Load` implementation.

## Architectural constraints

- Do not add separate Extract/Load execution layers.
- Do not change DTCS transformation semantics.
- Do not move physical asset configuration into pipeline definitions.
- Do not embed credentials, resolved secrets, clients, or backend objects in
  plans or contracts.
- Do not silently weaken plugin capability requirements.
- Production profiles must continue to fail closed on plugin trust.
- Preserve DPCS source/sink vocabulary and compatibility where required by the
  standard.
- Preserve medallion concepts outside ETLantic core.
- Prefer public SDK imports over private modules.

## Validation workflow

Run the repository's complete relevant validation:

```bash
ruff check .
ruff format --check .
pytest
python scripts/check_docs.py
mkdocs build --strict
git diff --check
```

Also run focused tests for pipeline modeling, DPCS, planning, runtime, plugins,
lineage, schemas, and documentation companions before the complete suite.

Do not declare completion if tests are skipped without explanation.

## Deliverables

Produce:

1. Canonical `Extract` and `Load` public APIs.
2. Canonical `asset=` vocabulary.
3. ETLantic 0.15 compatibility aliases and warnings.
4. Updated profile/asset-resolution behavior where applicable.
5. Updated diagnostics and public exports.
6. Complete tests and semantic-parity coverage.
7. Repository-wide documentation migration.
8. A 0.14-to-0.15 migration guide.
9. A documented 0.16 removal checklist.
10. Changelog and roadmap updates.
11. Validation results.

At completion, summarize:

- the exact public API changes
- compatibility behavior in 0.15
- removals scheduled for 0.16
- external-standard fields intentionally retaining source/sink/binding
  terminology
- fingerprint or serialized-artifact impact
- tests and documentation validation performed
