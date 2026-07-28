# Diagnostics Reference

Diagnostics are structured findings produced while loading, inspecting,
validating, planning, compiling, or executing a pipeline.

They are intended for people, CI systems, editors, and plugin tooling.

## Diagnostic Model

A diagnostic should contain:

```python
Diagnostic(
    code="PMPIPE201",
    severity=Severity.ERROR,
    message='Unknown input "cleaned_customer".',
    path=("pipeline", "publish", "input"),
    source=SourceLocation(...),
    help='Did you mean "cleaned_customers"?',
    related=(...),
    metadata={...},
)
```

## Severity

| Severity | Meaning |
|---|---|
| `error` | The operation cannot safely continue |
| `warning` | The model is valid but may be unsafe or surprising |
| `info` | Relevant explanatory information |
| `hint` | Optional improvement or editor assistance |

Only errors make a validation report invalid by default.

## Diagnostic Namespaces

ETLantic-owned codes should use stable categories:

```text
PMSRCxxx   Source and import loading
PMTYPExxx  Type annotations and model introspection
PMDATAxxx  Data-contract integration
PMTRNxxx   Transformation definitions and implementations
PMXFORMxxx Portable transformation authoring, IR, compilers, and execution
PMPIPExxx  Pipeline topology and wiring
PMPLANxxx  Planning and capability resolution
PMPLUGxxx  Plugin trust / allowlist (e.g. PMPLUG401, PMPLUG402)
PMORCHxxx  Orchestration / compile diagnostics
PMSPARKxxx Spark capability and runtime diagnostics
PMDFxxx    Dataframe plugin diagnostics
PMEXECxxx  Execution lifecycle
PMCFGxxx   Configuration and profiles
PMSECxxx   Security policy (I/O, serialization, outbound)
PMGENxxx   Contract and documentation generation
PMINTxxx   Internal framework invariants
```

Standards and plugins retain their own namespaces, such as `ODCS`, `DTCS`,
`DPCS`, or a documented plugin prefix.

## Practical code index

These codes are emitted by the installed ETLantic package (currently **0.31.0** /
0.31.x).
The message, path, metadata, and severity provide the case-specific detail.

**Exhaustive generated inventory:** [Diagnostics catalog](DIAGNOSTICS_CATALOG.md)
(code → source paths). Regenerate with:

```bash
uv run python scripts/generate_diagnostics_catalog.py --markdown \
  > docs/10_REFERENCE/DIAGNOSTICS_CATALOG.md
```

The curated tables below remain the human-oriented index.

### Pipeline and planning

| Code | Meaning |
|---|---|
| `PMPIPE201` | A pipeline member, connection, or referenced port is invalid or unresolved |
| `PMPIPE210` | Connected producer and consumer contracts are incompatible |
| `PMPIPE220` | An invalid-output port feeds a normal required input |
| `PMPIPE301` | Pipeline graph contains a cycle |
| `PMPIPE302` | The logical graph could not be built |
| `PMPLAN201` | An Extract/Load asset has no binding in the selected profile or registry |
| `PMPLAN202` | A node contract lacks a published ODCS identifier |
| `PMPLAN301` | A step has no implementation for the selected engine |
| `PMPLAN401` | No plugin capabilities are registered for the selected engine |
| `PMPLAN402` | A required capability is unsupported |
| `PMPLAN403` | Planning selected an allowed capability fallback |
| `PMPLAN420` | Quality gate requires `invalid_row_separation` unsupported by the engine |
| `PMPLAN421` | Required portable `quality.*` capability unsupported by the engine |
| `PMPLAN430` | Write-mode negotiation missing engine capabilities |
| `PMPLAN431` | Required `write.*` capability unsupported (fail before mutation) |
| `PMQTY400` | Quality evaluator could not coerce a row to a mapping |
| `PMQTY410` | Row failed one or more portable quality rules |

### Plugin trust and portable transforms

| Code | Meaning |
|---|---|
| `PMPLUG401` | A production profile has an empty plugin allowlist and fails closed |
| `PMPLUG402` | A discovered plugin is not allowlisted or does not match its version constraint |
| `PMXFORM201` | A declared portable output is missing from the return value |
| `PMXFORM202` | A portable definition returned an undeclared output |
| `PMXFORM301` | A compiler cannot satisfy a portable operation or capability requirement |
| `PMXFORM302` | Portable compilation is required but no suitable compiler is registered |
| `PMXFORM501` | Portable execution failed |
| `PMXFORM801` | Portable IR captured a callable |
| `PMXFORM802` | Portable IR contains a forbidden binary literal |
| `PMXFORM803` | Portable IR captured a secret value or reference |
| `PMXFORM810` | Portable plan exceeds the document-size budget |
| `PMXFORM811` | Portable plan exceeds the node-count budget |
| `PMXFORM812` | Portable plan exceeds the depth budget |

### Configuration and profiles

| Code | Meaning |
|---|---|
| `PMCFG100` | Unknown profile name; use a built-in template or pass an explicit profile path |
| `PMCFG110` | Legacy `bindings` key loaded from profile JSON; migrate to `assets` |
| `PMCFG111` | Profile JSON used legacy `bindings`; rename to `assets` or pass `--accept-legacy-bindings` |

### Source, import, and security policy

| Code | Meaning |
|---|---|
| `PMSRC101` | Unsafe or disallowed source import path under the active I/O policy |
| `PMSRC102` | Interchange bundle import rejected by security policy |
| `PMSRC103` | Interchange bundle descriptor failed validation |
| `PMSRC104` | Interchange bundle load failed closed |
| `PMSEC050` | Outbound network or transport request blocked by default-deny policy |
| `PMSEC051` | Outbound request exceeded configured policy limits |
| `PMSEC060` | Unsafe serialization blocked (secret or forbidden object graph) |

### Orchestration and execution

| Code | Meaning |
|---|---|
| `PMORCH300` | The requested orchestrator compiler plugin is missing or compilation failed |
| `PMORCH301` | The orchestrator lacks a required capability |
| `PMORCH340` | An in-memory artifact cannot cross the external orchestration boundary |
| `PMORCH341` | An oversized inline artifact requires durable transport |
| `PMORCH342` | Artifact metadata appears to contain a secret |
| `PMEXEC100` | `Pipeline.run()` was called from an active event loop; use `arun()` |
| `PMEXEC300` | A runtime node failed |
| `PMEXEC301` | Failure policy continued or skipped a node after an upstream failure |
| `PMEXEC320` | A planned step lacks required transformation identity or registration |
| `PMEXEC330` | Runtime input or output validation failed |
| `PMEXEC410` | Data publication succeeded but run report persistence failed (0.23) |
| `PMEXEC411` | Unsupported `CancellationPolicy` knobs (`abandon_after_seconds` / `cooperative=False`) |
| `PMEXEC412` | Cleanup fault after a successful step body (fault injection / cleanup path) |
| `PMEXEC413` | `step_failed` callback fault isolated from the primary step failure |
| `PMEXEC414` | Attempt cleanup failed after a successful step body (no retry) |
| `PMEXEC415` | No callable writer registered for a binding |
| `PMEXEC416` | No callable reader registered for a binding |
| `PMEXEC408` | Run timed out |
| `PMEXEC409` | Run cancelled |
| `PMEXEC401` | An environment-backed secret is unavailable |
| `PMEXEC501` | Retry refused because retry-safety declares the step unsafe |
| `PMEXEC402` | A file-backed secret cannot be loaded safely |
| `PMEXEC420` | A dataframe plugin is unavailable for the selected engine |
| `PMEXEC421` | Dataframe materialization failed for a node output |
| `PMEXEC422` | Dataframe implementation failed for a node |
| `PMEXEC430` | Unknown storage provider for an extract |
| `PMEXEC431` | Unknown storage provider for a load |
| `PMEXEC432` | Unknown or unsupported SQL write intent |
| `PMEXEC434` | A SQL plugin is unavailable for the selected engine |
| `PMEXEC440` | No Spark plugin is available for the selected engine |
| `PMEXEC450` | A JSON binding lacks a location path |
| `PMEXEC451` | JSON source file not found |
| `PMEXEC452` | Failed to coerce an engine frame to records |
| `PMEXEC453` | A CSV binding lacks a location path |
| `PMEXEC454` | CSV source file not found |
| `PMEXEC455` | Trusted SQL fragments disabled by policy/capability |
| `PMEXEC456` | SQL implementation returned an unsupported type |

### Backend-specific

| Code | Meaning |
|---|---|
| `PMDF410` | A dataframe row failed contract validation |
| `PMSPARK220` | Spark schema compatibility produced a lossy or incompatible finding |
| `PMSPARK221` | Spark schema inspection failed |
| `PMSPARK310` | The profile's UDF policy forbids a planned Spark UDF strategy |
| `PMSPARK320` | A batch-only transformation was placed in a streaming region |

Search the exact code in the source or include it in an issue when a code is
not listed here. Do not suppress trust, secret, or semantic safety diagnostics.

## Source Locations

When available, diagnostics should identify:

- File or URI
- Line and column
- Python object or class
- Contract path
- Pipeline node and port
- Generated artifact

Example:

```text
src/pipelines/customer.py:42:9 PMPIPE201

The step "publish_customers" expects Customer, but received RawCustomer
from "load_customers.result".

help: connect the output of NormalizeCustomers or change the sink contract
```

## Related Locations

A diagnostic may refer to more than one place:

- The consumer port
- The producer port
- The relevant contract declaration
- The selected implementation

Related locations make type and compatibility errors explainable without
flattening them into a single message.

## Reports

Operations return reports containing diagnostics:

```python
report = CustomerPipeline.validate()

if not report.valid:
    report.raise_for_errors()
```

Reports should support:

- Filtering by severity or code
- Stable ordering
- JSON serialization
- Human rendering
- SARIF export
- Summary counts

## Exceptions and Diagnostics

Expected user errors should become diagnostics. Exceptions are reserved for
invalid API usage, I/O failures configured as fatal, plugin crashes, or broken
framework invariants.

An exception raised by a convenience method should retain its report:

```python
try:
    CustomerPipeline.plan(profile="production")
except PipelineValidationError as exc:
    print(exc.report)
```

## Validation Diagnostics

Validation may report:

- Invalid data-contract types
- Missing transformation inputs
- Incompatible output and input contracts
- Cycles
- Duplicate identifiers
- Invalid parameters
- Missing sinks
- Unsupported subpipeline boundaries
- Invalid portable expression names, types, outputs, or bounded structure

## Planning Diagnostics

Planning may report:

- No compatible implementation
- Missing plugin
- Unsupported capability
- Ambiguous binding
- Unsafe artifact boundary
- Unsupported orchestrator behavior
- Incompatible SQL or Spark dialect
- Unsupported portable operation, function, type, or semantic mode
- Ambiguous portable/native selection or prohibited fallback

Portable diagnostics use expression paths such as
`outputs.result.project.full_name` and reserve these ranges:

```text
PMXFORM1xx authoring and signatures
PMXFORM2xx names, types, contracts, and outputs
PMXFORM3xx compiler selection and capabilities
PMXFORM4xx lowering and semantic mismatch
PMXFORM5xx portable runtime execution
PMXFORM8xx security and bounded-input rejection
PMXFORM9xx internal invariants
```

Shipped authoring codes in 0.11 include:

| Code | Meaning |
|---|---|
| `PMXFORM101` | Portable definition signature mismatch or excluded `F.expr` |
| `PMXFORM110` | Return value is not a `FrameExpr` / output mapping |
| `PMXFORM201` | Declared output missing from portable return value |
| `PMXFORM202` | Undeclared output returned |
| `PMXFORM203` | Single `FrameExpr` return with multiple outputs |
| `PMXFORM801`–`803` | Callable / binary / secret capture rejection |
| `PMXFORM810`–`812` | Document size / node count / depth budget exceeded |
| `PMXFORM901` | Unexpected plan protocol identity |

## Execution Diagnostics

Execution findings should distinguish:

- Failed
- Timed out
- Cancelled
- Skipped
- Retrying
- Abandoned
- Invalid input data
- Invalid output data

Runtime exceptions should be normalized without hiding the original exception.

## Suppression

Suppressions should be explicit, narrow, and reviewable:

```python
class CustomerPipeline(Pipeline):
    model_config = {
        "diagnostic_suppressions": {
            "PMPIPE410": "Legacy source retained during migration",
        }
    }
```

Suppressing errors that protect required semantics should not be allowed.

## Machine-Readable Output

```bash
etlantic validate path/to/pipeline.py:CustomerPipeline --format json
etlantic validate path/to/pipeline.py:CustomerPipeline --format sarif
```

Machine output should use stable field names and diagnostic codes even when
human wording improves.

## Plugin Requirements

Plugins should:

- Emit structured diagnostics rather than printing
- Use stable documented codes
- Attach node and plugin identity
- Preserve causal exceptions
- Avoid leaking secrets
- Suggest remediation when possible

## See Also

- [Exceptions](EXCEPTIONS.md)
- [Pipeline Validation](../05_PIPELINES/PIPELINE_VALIDATION.md)
- [Error Handling](../04_TRANSFORMATIONS/ERROR_HANDLING.md)
