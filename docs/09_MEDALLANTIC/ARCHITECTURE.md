# Architecture

## Ownership

Medallantic owns:

- bronze, silver, and gold vocabulary
- layer dependency conventions and defaults
- layer quality thresholds
- medallion naming and publication conventions
- SparkForge migration models and diagnostics

ETLantic owns:

- contracts and domain-neutral graph semantics
- validation, planning, execution lifecycle, and evidence
- profiles, capabilities, plugin trust, and safe I/O
- run requests, write intents, plans, and reports

Plugins own physical execution, storage, orchestration, and engine sessions.

## One logical graph

Medallantic does not reproduce separate Spark and SQL builders. One definition
lowers to one ETLantic graph; authorized profiles and capabilities select
physical realizations.

Unsupported semantics fail during validation or planning. Neither package
silently switches engines, approximates writes, repairs cycles, embeds live
backend objects in plans, or forces every intermediate result through a table.

## Promotion rule

A concept belongs in ETLantic only when it has the same meaning outside
medallion pipelines, is useful to multiple facades/plugins, affects portable
validation or execution, and can be named without layer terminology.

Otherwise it remains in Medallantic or an execution plugin.

## Security boundary

Definitions, plans, diagnostics, migration reports, and fingerprints contain
metadata and references—not credentials, source rows, sessions, dataframe
objects, or imported callables. Production execution inherits ETLantic's plugin
allowlists, redaction, safe I/O, mutation controls, and artifact isolation.

