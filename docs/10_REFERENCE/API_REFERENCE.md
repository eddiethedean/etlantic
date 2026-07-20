# Python API Reference

> **Status: Available in ETLantic 0.21.0.** Signatures and docstrings are
> generated from the package source across the pages linked below.

## Start here by persona

| Persona | Start with | Then |
|---|---|---|
| Pipeline author | Author essentials below, [CLI](CLI.md) | [Authoring API](API_AUTHORING.md), [Plan and runtime](API_PLAN_RUNTIME.md) |
| Plugin author | [Protocols](API_PROTOCOLS.md) | [Plugin SDK](../07_PLUGIN_SDK/README.md), Testing helpers |
| CI / ops | [CLI](CLI.md), [Runtime configuration](RUNTIME_CONFIGURATION.md) | [Ops examples](../01_GETTING_STARTED/OPS_EXAMPLES.md) |

```python
from etlantic import (
    Data,
    Input,
    Output,
    Parameter,
    Pipeline,
    PipelineRuntime,
    Load,
    Extract,
    Transformation,
)
```

`DataContractModel` is a deprecated alias for `Data`.

## Author essentials

| Symbol | Module | One-liner |
|---|---|---|
| `Data` | `etlantic.contracts` | ContractModel-compatible dataset type |
| `Input` / `Output` / `Parameter` | `etlantic.ports` | Transformation port markers |
| `Transformation` | `etlantic.transformation` | Typed transform interface + implementations |
| `Extract` / `Load` | `etlantic.pipeline` | Pipeline entry / publication boundaries |
| `Pipeline` | `etlantic.pipeline` | Declarative graph; `validate` / `plan` / `run` |
| `Profile` | `etlantic.profile` | Environment + allowlist + engine selection; `security_mode` for trust |
| `resolve_profile` | `etlantic.profile` | Named/path resolve; unknown names fail closed unless `allow_adhoc_profile=True` |
| `PipelineRuntime` | `etlantic.lifecycle` | Process-local plugins, memory, reports |
| `PipelinePlan` | `etlantic.plan` | Immutable secret-free resolved plan (`schema` required on wire) |
| `plan_pipeline` / `explain_plan` | `etlantic.plan` | Functional planning helpers |
| `verify_plan_fingerprint` / `deep_freeze` | `etlantic.plan` | Trust-boundary fingerprint check; deep immutability helper |
| `compile_plan` | `etlantic.orchestration` | External orchestrator artifact emission (verifies fingerprint first) |
| `ValidationReport` | `etlantic.diagnostics` | Structured validate findings |
| `PipelineRunReport` | `etlantic.reports` | Structured run outcomes |
| `SecretRef` | `etlantic.secrets` | Runtime-only secret reference |
| `BackfillRequest` | `etlantic.reliability_runtime` | Reliability backfill request helper |
| Gate A tabular types | `etlantic.interchange.tabular` | Descriptors, mechanism selection, fidelity, evidence (`etlantic.interchange/1`) |

Optional plugins document factories in package READMEs. See
[Optional Packages](OPTIONAL_PACKAGES.md).

## Generated API pages

- [Authoring](API_AUTHORING.md) — contracts, transformations, pipelines, ports
- [Plan and runtime](API_PLAN_RUNTIME.md) — validation, profiles, plan, runtime, storage, secrets, contract interchange, **Gate A tabular interchange**
- [Protocols](API_PROTOCOLS.md) — dataframe, SQL, Spark, orchestration, viz, testing, reliability

## Core behavioral contracts

| API | Returns | Important failures / side effects |
|---|---|---|
| `Transformation.step(**bindings)` | A symbolic `Step`; no user code runs | Unknown bindings raise `ModelDefinitionError` |
| `Transformation.implementation(engine)` | Decorator returning the original callable | Registration replaces same class/engine in-process |
| `Transformation.portable` | Decorator registering a symbolic definition | Authoring errors raise `ModelDefinitionError` (`PMXFORM*`) |
| `Pipeline.validate(...)` | `ValidationReport` | Does not execute transforms; empty production allowlist fails closed |
| `Pipeline.plan(...)` | Immutable, secret-free `PipelinePlan` | Missing plugins/assets/capabilities fail planning; nested nests are deep-frozen |
| `Pipeline.run(...)` / `arun(...)` | `PipelineRunReport` | Verifies plan fingerprint before execution; storage side effects follow the plan |
| `Pipeline.to_mermaid()` | Mermaid flowchart string | Does not plan or execute |

```python
report = CustomerPipeline.validate(profile="development")
report.raise_for_errors()
plan = CustomerPipeline.plan(profile="development")
```

`PipelineRuntime` is application-owned. A new process receives an empty
memory store unless durable providers are configured.

## Stability

ETLantic 0.21.0 is **stable** for documented single-tenant reference
deployments (not unrestricted enterprise production). Public compatibility
follows the documented 0.x deprecation policy; minor releases may still include
announced migrations. Review the changelog and
[compatibility matrix](COMPATIBILITY.md) before upgrading. Narrative CLI docs:
[CLI](CLI.md).
