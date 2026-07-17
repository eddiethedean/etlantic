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
PMPLGxxx   Plugin discovery and compatibility
PMEXECxxx  Execution lifecycle
PMCFGxxx   Configuration and profiles
PMGENxxx   Contract and documentation generation
PMINTxxx   Internal framework invariants
```

Standards and plugins retain their own namespaces, such as `ODCS`, `DTCS`,
`DPCS`, or a documented plugin prefix.

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
etlantic validate . --format json
etlantic validate . --format sarif
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
