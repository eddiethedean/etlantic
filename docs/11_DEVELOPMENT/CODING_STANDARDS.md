# Coding Standards

Portable IR nodes are immutable, backend-free, canonically serializable, and
closed over explicitly registered operations. Core code must not import native
Polars, Pandas, PySpark, SQL driver, or compiler objects. Never serialize a
callable, `repr()` fallback, source row, live resource, or resolved secret into
a portable definition.

ETLantic code should be explicit, typed, testable, and approachable to
Python developers familiar with Pydantic and FastAPI-style APIs.

## Python

Use the Python versions declared in `pyproject.toml`. Prefer modern standard
typing and standard-library features supported by the minimum version.

## Style

- Format and lint with Ruff.
- Use four-space indentation.
- Prefer clear names over abbreviations.
- Keep functions focused.
- Avoid clever metaprogramming when explicit code is sufficient.
- Document non-obvious invariants.

## Typing

Public APIs require complete type annotations.

Prefer:

```python
def validate_pipeline(
    pipeline: PipelineDefinition,
    *,
    profile: Profile | None = None,
) -> ValidationReport:
    ...
```

Avoid untyped dictionaries at public boundaries. Use dataclasses, typed
mappings, protocols, enums, and generics.

Use `Any` only at genuine third-party or dynamic boundaries, then normalize it
immediately.

## Immutability

Use frozen, slotted dataclasses for value objects where practical:

```python
@dataclass(frozen=True, slots=True)
class PortReference:
    node_id: str
    port_name: str
```

Authoring descriptors and planner builders may be mutable internally.
Published reports and `PipelinePlan` should be immutable.

## Protocols and Composition

Prefer small protocols:

```python
class StoragePlugin(Protocol):
    async def read(self, asset: str) -> object: ...
    async def write(self, asset: str, value: object) -> None: ...
```

Do not require plugins to inherit from deep framework hierarchies.

## Async

- Keep the orchestration boundary async.
- Await native async callables directly.
- Run blocking sync work through managed worker boundaries.
- Do not call `asyncio.run()` inside an active event loop.
- Preserve cancellation.
- Always clean up sync and async resources.
- Do not hide unbounded concurrency.

## Exceptions and Diagnostics

Expected user mistakes produce diagnostics. Exceptions represent invalid API
usage, infrastructure failures, plugin crashes, or internal invariants.

Never:

- Swallow exceptions silently
- Print from library code
- Leak secrets in errors
- Replace cancellation with generic failure

## Imports

- Keep root imports lightweight.
- Avoid required imports of optional backends.
- Use explicit relative imports within a package where appropriate.
- Prevent circular dependencies through architecture tests.
- Do not perform plugin discovery at import time.

## Public and Internal APIs

The package root exposes only common, stable authoring APIs. Advanced public
interfaces belong in named modules such as `etlantic.sdk`.

Internal names begin with `_` and may change without compatibility guarantees.

## Documentation

Public classes and functions require docstrings that explain:

- Purpose
- Parameters and return values
- Exceptions
- Sync or async behavior
- Stability and extension expectations

Examples should use the same terminology as the user guide.

## Data and Secrets

- Never log raw data by default.
- Redact secrets and credentials.
- Do not serialize resolved secrets into plans.
- Treat contract and configuration inputs as untrusted.
- Avoid arbitrary code execution during contract loading.

## Plugin Code

Plugins must:

- Declare accurate capabilities
- Validate their configuration
- Normalize backend errors
- Preserve logical step identity
- Support cleanup
- Avoid changing pipeline semantics
- Pass SDK conformance tests

## Tests

Every behavior change requires tests. Bug fixes should include a regression
test that fails before the fix.

Use fakes for unit tests and real backends for explicitly marked integration
tests.

## Comments

Comments should explain why a constraint or unusual implementation exists.
Avoid comments that merely restate code.

## Compatibility

Before changing a public model, protocol, diagnostic code, configuration key,
or generated schema:

1. Identify consumers.
2. Assess backward compatibility.
3. Add a deprecation or migration path.
4. Update tests and documentation.
5. Record an ADR if the decision is architectural.

## Core Rule

> Make the typed user experience simple while keeping the underlying semantics
> explicit, deterministic, and portable.
