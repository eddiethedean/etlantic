# Migration 0.50 → 0.51

> **Status: Applies to the ETLantic 0.51.0 (published Beta).**

## Repin the lockstep packages

Install core and every first-party plugin on the same minor line. Official
plugin metadata requires `etlantic>=0.51.0,<0.52`.

```bash
python -m pip install 'etlantic==0.51.0' 'etlantic-polars==0.51.0'
```

Do not mix 0.50 and 0.51 packages. Production profiles must retain explicit
plugin, optimization-pass, schema-registry, and resource-provider allowlists
where those extension families are enabled.

## Keep executable profiles explicit

Existing Profiles default to `execution_strategy="explicit"` and continue to
produce canonical `etlantic.plan/1` documents. No action is required for that
path.

The new `execution_strategy`, `placement_targets`, `eligible_targets`, and
`adaptive_fallback` fields establish the adaptive policy contract. In 0.51.0,
opting into `execution_strategy="adaptive"` is for contract evaluation only:
planning rejects with `PMADP221` before candidate discovery or external I/O.
Do not enable it for production execution.

## Handle adaptive plan documents as a separate schema

`plan_from_json()` dispatches `etlantic.plan/1` to `PipelinePlan` and
`etlantic.plan/2` to `AdaptivePipelinePlan`. `/2` documents support canonical
serialization and fingerprint verification, but they are not executable in
0.51.0. Unsupported compilers, schedulers, control-plane paths, and remote
runtimes reject them before plugin discovery, acceptance, or external I/O.

Never rewrite or downgrade a stored `/2` document as `/1`; create a fresh
explicit plan from the source pipeline and Profile instead.

## Update built-in run-report metadata consumers

New writers use these step-level keys:

| 0.50 alias | 0.51 canonical key |
|---|---|
| `dataframe` | `etlantic.dataframe` |
| `sql` | `etlantic.sql` |
| `spark` | `etlantic.spark` |
| `spark_schema` | `etlantic.spark_schema` |

The `etlantic.run_report/1` reader migrates these four aliases without warnings.
When a bare alias and its namespaced form collide, the namespaced value wins.
Reserialization writes only the canonical namespaced form. Unrelated extension
metadata is unchanged.

## Rollback

Re-pin the complete 0.50.1 core/plugin set and continue using explicit Profiles
and `/1` plans. Restore consumers that expect the 0.50 bare report keys if they
do not already accept the namespaced forms. Do not feed `/2` documents to 0.50
readers and do not attempt a schema downgrade.
