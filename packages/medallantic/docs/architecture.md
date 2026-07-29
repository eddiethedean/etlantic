# Architecture

## Ownership

```text
Medallantic
  medallion vocabulary, authoring, defaults, migration
        |
        v
ETLantic
  contracts, graph, validation, plans, runtime, evidence, trust
        |
        v
Plugins and providers
  Polars, Pandas, SQL, PySpark, Delta, storage, observability
```

## Why medallion concepts stay outside core

Bronze/silver/gold is a useful pipeline convention, not a universal pipeline
semantic. Keeping it in a facade allows ETLantic to serve other architectures
without phase-coded models, validation fields, or runtime branches.

Medallantic may attach namespaced annotations and choose policy defaults.
ETLantic still validates and serializes only domain-neutral graph and runtime
meaning.

## One graph, multiple realizations

Medallantic must not reproduce the legacy split between Spark and SQL builders.
A portable definition has one logical graph. Profiles and capability
negotiation select physical implementations.

Unsupported semantics fail during validation or planning. Medallantic and
ETLantic must not:

- silently switch engines
- approximate merge as append
- retry unsafe mutations
- break dependency cycles automatically
- force every intermediate result through a table
- embed live backend objects or executable code in plans

## Extension decision

When Medallantic exposes a missing concept, use this test:

1. Does it mean the same thing outside medallion pipelines?
2. Will multiple facades or plugins consume it?
3. Does it affect portable validation, planning, runtime, evidence, or trust?
4. Can it be named without layer or engine terminology?

If all answers are yes, evolve ETLantic first and consume the public capability
from Medallantic. Otherwise keep it in Medallantic or an execution plugin.

Examples likely to belong in ETLantic:

- typed multi-output artifacts
- atomic state transitions
- transaction boundaries
- materialization and publication policies
- capability diagnostics
- normalized lifecycle evidence

Examples that remain in Medallantic:

- bronze/silver/gold classes
- layer thresholds and defaults
- medallion dependency conventions
- layer naming and storage conventions
- SparkForge migration helpers

## Security boundary

Planning is secret-free and side-effect-free. Production execution uses
ETLantic's plugin allowlists, secret references, redaction, safe I/O, schema
mutation controls, and artifact isolation.

Medallantic IR and migration reports must contain metadata and references, not
resolved credentials, source rows, sessions, dataframe objects, or imported
legacy callables.
