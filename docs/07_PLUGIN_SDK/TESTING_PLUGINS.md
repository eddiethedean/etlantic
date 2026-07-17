# Testing Plugins

Testing plugins provide standardized ways to verify that ETLantic plugins
conform to the Plugin SDK and preserve pipeline semantics.

A plugin should not merely "work" with one example pipeline—it should
demonstrate that it correctly implements the contracts defined by the SDK
across a broad range of scenarios.

Portable compiler plugins must also run the future
`etlantic.testing.portable_transform_conformance` suite for every operation,
function, type, and semantic mode they advertise. Capability claims select
mandatory fixtures; unsupported behavior produces planning diagnostics rather
than backend-dependent results.

## Goals

Testing plugins should:

- Verify SDK conformance.
- Validate semantic correctness.
- Detect regressions.
- Produce deterministic results.
- Support automated CI/CD.
- Encourage interoperability across plugins.

## Philosophy

Every plugin should be tested against the same expectations.

```text
Plugin
   │
   ▼
SDK Test Suite
   │
   ├── API Conformance
   ├── Capability Validation
   ├── Semantic Tests
   ├── Failure Tests
   ├── Compatibility Tests
   └── Performance Benchmarks
```

A plugin that passes the same conformance suite should behave predictably with
ETLantic.

## What Should Be Tested?

Depending on plugin type:

- Registration
- Discovery
- Capability advertisement
- Version compatibility
- Error handling
- Structured diagnostics
- Async and sync behavior
- Resource lifecycle
- Deterministic execution

Execution plugins should additionally verify:

- Dependency ordering
- Retry semantics
- Callback ordering
- Failure propagation

Dataframe plugins should verify:

- Transformation execution
- Contract validation
- Backend equivalence
- Output correctness

Storage plugins should verify:

- Read/write operations
- Binding resolution
- Persistence semantics

Resource providers should verify:

- Resource resolution
- Lifecycle
- Cleanup
- Pooling
- Authentication hooks

## Conformance Testing

ETLantic should provide reusable conformance suites.

Conceptually:

```python
from etlantic.testing import run_conformance_suite

results = run_conformance_suite(plugin)
```

Passing the suite demonstrates compatibility with the published SDK version.

## Reference Test Pipelines

The SDK should ship small reference pipelines covering:

- Linear pipelines
- Branching pipelines
- Fan-in / fan-out
- Nested subpipelines
- Failures
- Retries
- Async execution

Every plugin should produce equivalent observable behavior.

## Performance Testing

Performance tests measure implementation quality rather than correctness.

Metrics may include:

- Startup time
- Throughput
- Memory usage
- Parallel scaling
- Resource reuse

Performance should never be confused with semantic correctness.

## CI/CD

Recommended workflow:

1. Unit tests
2. SDK conformance suite
3. Compatibility tests
4. Integration tests
5. Performance benchmarks

## Best Practices

- Automate all plugin tests.
- Run conformance tests in CI.
- Keep fixtures deterministic.
- Test both success and failure paths.
- Version-lock conformance suites to SDK releases.

## Anti-Patterns

Avoid:

- Testing only happy paths.
- Depending on backend-specific behavior.
- Skipping capability validation.
- Allowing nondeterministic results.
- Claiming SDK compatibility without conformance testing.

## Key Principle

> Every ETLantic plugin should prove compatibility through standardized,
> repeatable conformance testing. Correctness is defined by preserved pipeline
> semantics, not by a specific implementation strategy.

## Next Step

Continue with [Distribution](DISTRIBUTION.md) to learn how independently
versioned plugins declare compatibility and are published.
