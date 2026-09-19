---
status: experimental
since: "0.54.0"
current_minor: "0.54"
audience: developer
---

# Adaptive provider conformance

Use these public helpers from `etlantic.testing`:

- `AdaptiveConformanceCase` and `AdaptiveConformanceReport`
- `run_adaptive_provider_conformance_suite(cases)`
- `arun_adaptive_provider_conformance_suite(cases)`

Each immutable case has a bounded unique identifier, public Pipeline class or
PipelineDefinition, explicit Profile/RunRequest, fresh runtime factory and
required process-local verification callback. Optional planning-context factory
and workspace inputs use public types. Cases declare planning/execution mode,
expected acceptance and exact expected PM diagnostic for a negative outcome.

Validate the complete catalogue before factories. The callback receives runtime,
stored plan and report; inspect synthetic outputs and zero-effect sentinels in
process. Assertion failures are behavioral failures, while malformed factories
or unsupported callback returns are safe harness errors. Never retain rows or
call provider serialization hooks to construct a conformance report.

Include positive and negative cases for claimed compiler operations/types,
unknown/missing evidence, source bounds, unsupported fusion boundaries and both
interchange directions. Metadata recognition alone is not proof: retain real
compiler/source/Arrow effects and assert dispatch, nulls, duplicate/order
semantics, validation and publication. Third-party execution without a packaged
row should be an expected negative; never patch packaged authority to force a
positive. Passing confers no maturity, production allowlist or execution trust.

Run the async helper inside an event loop. The sync helper rejects active loops
before factories. Caller cancellation drains active work and propagates after
the case; reports contain only trusted case IDs, outcomes, known codes and
optional verified fingerprints. No private core imports are required.

See [bounded candidate usage](../11_DEVELOPMENT/ADAPTIVE_0_54_USAGE.md) and the
executable public-only `examples/adaptive_reference.py`.
