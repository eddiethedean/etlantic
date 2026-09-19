---
status: experimental
since: "0.54.0"
current_minor: "0.54"
audience: developer
---

# 0.54 development candidate APIs

> 0.54 release candidate; publication pending. Adaptive is Experimental.

The public-only companion is `examples/adaptive_reference.py`. Run it with
`python examples/adaptive_reference.py` after installing the matching Polars,
Pandas and Arrow extras. It owns a temporary synthetic source and writes only
to an isolated in-memory sink.

These additions are an Experimental development candidate, not a promotion of
the existing adaptive matrix. Passing conformance does not authorize execution.

## Bounded Polars Parquet source

```python
from etlantic_polars import create_parquet_storage

source = create_parquet_storage({
    "schema": "etlantic.polars_parquet_source/1",
    "max_bytes": 64 * 1024 * 1024,
    "max_rows": 100_000,
})
runtime.register_storage("polars-parquet", source)
```

The immutable adapter implements read-only storage. Reads require the existing
safe-I/O policy and a single relative `.parquet` filename under an approved root.
No URL, glob, parent traversal, write, arbitrary reader callback or symlink
escape is supported. Limits include source bytes, decoded column chunk sizes,
rows and all columns, including columns later dropped by projection. Every
column must be a flat int64 or boolean; at most eight columns are supported.
Maximum configuration bounds are 256 MiB and one million rows. Booleans are not
accepted as integer limits. A verified source handle supplies a bounded,
immutable byte snapshot that remains alive through the native query and is
released after native work drains. Native scans never reopen a snapshot path;
source or parent rename/replacement cannot replace those bytes. No disk
artifact or additional approved root is needed under the captured SafeIoPolicy.
Memory includes bounded copies during sanitization and native construction.

Before any Arrow or Polars reader is constructed, a bounded Compact-Thrift
footer pass sanitizes optional Parquet `FileMetaData` key/value metadata by
removing it, including ARROW:schema.
Registered Arrow extension deserializers never process source metadata, and
extension semantics are discarded. All physical columns still pass the
int64/boolean gate. Explicit source reads support PyArrow >=14, including
Arrow 20, without the newer `arrow_extensions_enabled` keyword. The adaptive
qualification pin remains PyArrow 25.0.0; ordinary compatibility does not expand
adaptive admission support. Compatibility cleanup inspection
returns no disk obligations, and unknown reconciliation tokens reject.

The exact fused candidate requires a binding with provider `polars-parquet`,
format `parquet`, the adapter's `configuration()`, matching installed provider
version and configuration fingerprint, and the capability evidence descriptor.
The root alias is `workspace`. The captured safe-I/O policy must name only that
alias, and `LocalScheduler.execute(..., workspace=approved_root)` resolves it
at admission. Physical paths are not stored in the plan. Binding registration
uses the existing public `BindingDescriptor` and runtime registry APIs.
Pass the canonical approved root (for example `approved_root.resolve(strict=True)`)
so a platform alias such as macOS `/var` is not mistaken for an unsafe symlink.

## Exact fusion boundary

Only the source → equality filter → plain projection prefix of the frozen
five-node Polars/Pandas chain is fused. The equality uses one required nullable
int64 column and one captured non-null int64 parameter. Projection must drop an
unused source column. Required nullable int64/boolean contracts must have no
defaults, validators, aliases, constraints or extra-forbid behavior. Profiles
must require portable transforms; retries, checkpoints, selected slices,
member metadata and custom step middleware are not qualified for this fusion.
All five node placements must be captured explicitly in implementation overrides;
this binds exact positive objective facts without hypothetical fusion credit.

Planning does not open the source. Admission pins source, compiler, original
portable IR, contracts and policy before any data effect. Execution composes the
original portable actions, proves actual native scan pushdowns, collects once,
then exposes only the projected boundary. It does not register eager raw/filter
artifacts or execute those members through the ordinary node loop. The existing
Arrow handoff, Pandas consumer, validation and publication barriers follow.

## Public provider conformance

Use `AdaptiveConformanceCase`, `AdaptiveConformanceReport`,
`run_adaptive_provider_conformance_suite` or `arun_adaptive_provider_conformance_suite` from
`etlantic.testing`. A case supplies a pipeline, explicit profile, run request,
fresh runtime factory, and required in-process verification callback. Optional
planning-context and workspace inputs use the existing public types.

Catalogue validation precedes runtime factories. Planning-only cases assert
zero effects through their verification callbacks. Execution cases serialize
and read the plan before scheduler execution. The callback receives the runtime,
stored plan and report and must assert behavior, not merely provider metadata.
Negative cases specify the exact expected diagnostic. Reports retain trusted
case IDs, outcomes, known codes and fingerprints—not rows, exception text,
provider objects or provider serializers. The sync helper rejects active event
loops; the async helper propagates cancellation after active work drains.

## Fresh local observations

Run `python scripts/check_adaptive_0_54.py` for temporary local observations.
To retain a new observation, supply both `--write --output NEW_DIRECTORY`.
Existing observations are never overwritten. Failing outcomes and source
changes are recorded as failures. Exact parameterized pytest IDs and all three
passing test phases are required. No decision or qualification bundle is edited.
The frozen catalogue binds exact full case identities and all local/programme
ACs. Use `--verify-index PATH` for read-only verification or `--aggregate DIR`
to assemble actual environment artifacts and check all nine CI cells. Neither
operation grants approval or fills missing remote observations.

## Expected output

```console
Experimental reference: one fused collection, one Arrow handoff, two published records
```
