# Validation Everywhere

> **Status: Available in ETLantic 0.37.0.**

ETLantic models ETL with validation at every meaningful boundary.

```text
V(model) ──▶ Extract ──▶ V(input) ──▶ Transform ──▶ V(output) ──▶ Load ──▶ V/evidence
```

This is not a new acronym, a fourth contract family, or an instruction to add
handwritten validation transformations between every pair of steps. Validation
is a cross-cutting control layer derived from the existing data,
transformation, and pipeline contracts.

It also makes the project name concrete: **ETL** remains the recognizable
extract-transform-load flow, while **ETLantic** is that flow surrounded by
typed contracts, validation, planning, and evidence from source to
publication. The name describes an ETL system with a validation envelope, not
a replacement for ETL.

## The Validation Envelope

The envelope has two complementary parts.

### Before execution

ETLantic validates the model and resolved environment before mutation:

- definitions and identities
- contract documents and supported versions
- graph references, cycles, ports, and contract compatibility
- portable transformation expressions
- profile bindings and resources
- backend and compiler capabilities
- plugin trust and production allowlists

These checks do not read datasets, invoke transformations, resolve secrets, or
write outputs. They answer whether the declared pipeline can be executed
safely with the selected profile.

### During execution

Runtime values are checked where data crosses a contract or ownership
boundary:

1. **Extract boundary.** Confirm that source data presented to the pipeline
   satisfies the extracted `Data` contract according to validation policy.
2. **Transformation input boundary.** Confirm that each implementation receives
   values compatible with its declared `Input[T]` ports.
3. **Transformation output boundary.** Confirm that valid, invalid, and side
   outputs match their declared ports before downstream consumption.
4. **Engine and interchange boundary.** Preserve contract fidelity when data
   changes engine, representation, ownership, or materialization strategy.
5. **Load boundary.** Validate the value being published and enforce declared
   write intent before mutation.
6. **Publication evidence.** Record the outcome, artifact identity, schema
   observation, diagnostics, and backend evidence available after publication.

The same value may cross several logical boundaries inside one fused physical
region. A backend may avoid redundant materialization only when it can preserve
the required validation semantics and logical attribution.

## Validation Is Policy-Driven

Not every boundary requires the same physical operation. Depending on the
profile, contract, backend, and declared policy, ETLantic may:

- fail the step or run
- reject or quarantine invalid rows when the plugin supports separation
- emit a warning or structured diagnostic
- compare normalized schemas
- verify counts, freshness, reconciliation, or other declared evidence
- rely on a transactional backend acknowledgement
- record that a stronger verification was unavailable and fail closed when it
  was required

ETLantic must not silently downgrade a mandatory validation requirement merely
because the selected engine lacks the capability.

## Validation Is Not Repeated Work by Default

“Validation at every boundary” describes semantic coverage, not mandatory
full-row rescans.

Validation can be satisfied by contract-aware construction, backend-native
schema checks, fused predicates, constrained writes, transactional results, or
previously established evidence when those mechanisms are truthful for the
declared policy. Plans should expose where validation occurs, whether it
materializes or scans data, and what evidence it produces.

A post-load check does not imply that ETLantic always reads the sink back. Some
providers can return strong publication evidence; others can only confirm that
the write request completed. If read-after-write verification is required, it
must be declared, supported, planned, and reported explicitly.

## Why It Matters

Traditional ETL often treats validation as a final quality task. That permits
bad source data, implementation mistakes, lossy engine conversions, or unsafe
writes to travel too far before discovery.

ETLantic instead keeps one chain of typed evidence:

```text
declared contract
      ↓
validated logical edge
      ↓
validated runtime boundary
      ↓
planned artifact and write intent
      ↓
publication and run evidence
```

This makes failures attributable to the boundary that introduced them and
keeps validation portable across local Python, Polars, Pandas, SQL, PySpark,
and orchestration targets.

## Design Rules

1. Validate structure and capabilities before data work begins.
2. Validate runtime values before they cross into the next contract boundary.
3. Validate or constrain writes before external mutation.
4. Preserve validation semantics through fusion and optimization.
5. Record what was checked, how it was checked, and what could not be checked.
6. Never put source rows or resolved secrets into plans, diagnostics, schema
   history, or validation evidence.
7. Fail closed when a required validation guarantee cannot be preserved.

## Related Concepts

- [Core Concepts](CORE_CONCEPTS.md)
- [Architecture](ARCHITECTURE.md)
- [Pipeline Validation](../05_PIPELINES/PIPELINE_VALIDATION.md)
- [Data Contract Validation](../03_DATA_CONTRACTS/VALIDATION.md)
- [Planning](../05_PIPELINES/PLANNING.md)
- [Run Reports](../06_EXECUTION/RUN_REPORTS.md)
