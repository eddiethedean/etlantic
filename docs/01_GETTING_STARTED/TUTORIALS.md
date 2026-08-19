# Tutorials

> **Status: Available in ETLantic 0.48.0.** Guided paths with expected time,
> environment, and CI coverage.

| Tutorial | Time | Environment | CI |
|---|---|---|---|
| [End-to-end pilot](END_TO_END_PILOT.md) | ~30–60 min | PyPI / no clone required | Partial |
| [File-backed pipeline](../06_EXECUTION/FILE_STORAGE_TUTORIAL.md) | ~15 min | Core | Syntax-checked |
| [Contract-first workflow](../09_EXAMPLES/CONTRACT_FIRST_TUTORIAL.md) | ~20 min | Core | Syntax-checked |
| [Polars](../06_EXECUTION/POLARS_TUTORIAL.md) | ~20 min | `etlantic[polars]` | `dataframes` job |
| [Pandas](../06_EXECUTION/PANDAS_TUTORIAL.md) | ~20 min | `etlantic[pandas]` | `dataframes` job |
| [SQL hello (PyPI)](../06_EXECUTION/SQL_HELLO_PYPI.md) | ~10 min | `etlantic[sql]` | Syntax-checked |
| [SQL (repository)](../06_EXECUTION/SQL_TUTORIAL.md) | ~30 min | Clone + SQL | `sql` job |
| [PySpark (repository)](../06_EXECUTION/PYSPARK_TUTORIAL.md) | ~30 min | Clone + PySpark | `spark` job |
| [Airflow compilation](../06_EXECUTION/AIRFLOW_TUTORIAL.md) | ~20 min | `etlantic-airflow` | `airflow` job |
| [Prefect local](../09_EXAMPLES/PREFECT_RUN.md) | ~15 min | Clone + `etlantic-prefect` | `prefect` job |
| [Human-governed AI](HUMAN_GOVERNED_AI.md) | ~15 min | PyPI / no clone | CLI |
| [Scheduler and worker](SCHEDULER_TUTORIAL.md) | ~15 min | PyPI / no clone | CLI |

Start with the [Quickstart](QUICKSTART.md) before engine tutorials.
Clone-required rows need a git checkout (`examples/` is not on the wheel).
Runnable companions are registered in `scripts/check_runnable_docs.py`.
