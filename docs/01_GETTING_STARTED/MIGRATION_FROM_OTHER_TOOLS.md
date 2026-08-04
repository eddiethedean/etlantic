# Migration from other tools

> **Status: Available in ETLantic 0.42.0.** Honest scope for evaluators who
> already run Airflow, dbt, or Dagster. There is **no automated migrator in
> 0.36**; bounded brownfield import and compiler bridges are planned for
> [0.49](../11_DEVELOPMENT/ADOPTION_ECOSYSTEM_PLAN.md#brownfield-adoption-bridges).

ETLantic is a typed pipeline modeling and validation layer. It does not replace
your warehouse tool, scheduler, or dataframe engine. Expect a **re-authoring**
effort, not a one-click import.

## From Airflow DAGs

| Keep in Airflow | Rebuild in ETLantic |
|---|---|
| Scheduling, sensors, pools, SLA | Typed `Pipeline` / `PipelineDefinition` |
| Existing operators for I/O you trust | `Extract` / `Load` assets + profile bindings |
| Deployment topology | `python -m etlantic compile --target airflow` (needs `etlantic-airflow`) |

Recommended path:

1. Pick one DAG worth of logic and rewrite it as contracts + transformations.
2. `validate` → `plan` with an allowlisted production profile
   ([prod.example.json](prod.example.json)).
3. `compile --target airflow` and compare the emitted DAG to the hand-written one.
4. Expand only after the plan and reports look right.

There is no “import my_dag.py” command. See
[Airflow tutorial](../06_EXECUTION/AIRFLOW_TUTORIAL.md) and
[Compare](COMPARE.md).

## From dbt

dbt owns warehouse SQL models and tests. ETLantic owns typed contracts,
cross-engine planning, and validate-before-write for Python/SQL/Spark
pipelines. Typical coexistence:

- Keep dbt for warehouse transforms you already trust.
- Use ETLantic for multi-engine pipelines that need shared contracts, plans, and
  plugin trust before write.
- In 0.36, do not expect ETLantic to import a dbt project into a
  `PipelinePlan`. The planned 0.49 bridge starts from versioned
  `manifest.json` metadata, reports fidelity explicitly, and does not execute
  arbitrary project code.

## From Dagster / Prefect

| Tool | ETLantic relationship in 0.39 |
|---|---|
| Dagster | No compiler plugin; a Definitions compiler is planned for 0.49 |
| Prefect | Optional `etlantic-prefect` local MVP (direct execution); compile/deployment expansion is planned for 0.49 |

Author once in ETLantic, then choose whether to run locally, compile to Airflow,
or keep the existing orchestrator and call ETLantic validate/plan from CI.

## What “migration” means here

1. Map sources/sinks to logical assets and contracts (`Data`).
2. Map transforms to `Transformation` implementations (or portable transforms).
3. Compose a `Pipeline`, validate against a profile, review the secret-free plan.
4. Only then compile or run.

## Next

- [Compare](COMPARE.md) — positioning vs dbt / Airflow / Pandera
- [Capabilities](CAPABILITIES.md) — what ships in 0.42
- [Evaluator brief](EVALUATOR.md) — diligence packet
