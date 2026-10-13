"""etlantic-prefect — Prefect ExecutionScheduler for ETLantic 0.16."""

from __future__ import annotations

from etlantic_prefect.deployment import (
    ManagedDeploymentBinding,
    ManagedDeploymentSpec,
    PrefectDeploymentRegistrar,
)
from etlantic_prefect.dispatcher import PrefectDispatcher
from etlantic_prefect.plugin import PrefectScheduler, create_plugin
from etlantic_prefect.worker import (
    ManagedExecutionReference,
    get_managed_run_status,
    managed_execution_flow,
    request_managed_run_cancellation,
)

__version__ = "0.59.0"

__all__ = [
    "ManagedDeploymentBinding",
    "ManagedDeploymentSpec",
    "ManagedExecutionReference",
    "PrefectDeploymentRegistrar",
    "PrefectDispatcher",
    "PrefectScheduler",
    "__version__",
    "create_plugin",
    "get_managed_run_status",
    "managed_execution_flow",
    "request_managed_run_cancellation",
]
