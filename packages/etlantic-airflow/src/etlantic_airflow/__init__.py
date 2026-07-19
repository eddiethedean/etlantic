"""etlantic-airflow — Airflow reference orchestrator for ETLantic 0.8."""

from __future__ import annotations

from etlantic_airflow.loader import load_compiled_module, load_compiled_pipeline
from etlantic_airflow.plugin import AirflowOrchestratorPlugin, create_plugin

__version__ = "0.14.0"

__all__ = [
    "AirflowOrchestratorPlugin",
    "__version__",
    "create_plugin",
    "load_compiled_module",
    "load_compiled_pipeline",
]
