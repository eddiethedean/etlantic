"""Engine executor adapters wrapping existing exec modules.

Not wired into ``LocalOrchestrator`` in 0.23 — dispatch remains in orchestrator
exec modules directly. Reserved for future centralized engine routing.
"""

from __future__ import annotations

from typing import Any

from etlantic.engines import get_engine_registry


class DataframeExecutor:
    def matches(self, engine: str) -> bool:
        return get_engine_registry().is_dataframe_engine(engine)

    async def execute_source(self, ctx: Any, node: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("source dispatch remains in LocalOrchestrator")

    async def execute_step(self, ctx: Any, node: Any, **kwargs: Any) -> Any:
        from etlantic.runtime.dataframe_exec import execute_dataframe_step

        return await execute_dataframe_step(**kwargs)

    async def execute_sink(self, ctx: Any, node: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("sink dispatch remains in LocalOrchestrator")


class SqlExecutor:
    def matches(self, engine: str) -> bool:
        return get_engine_registry().is_sql_engine(engine)

    async def execute_source(self, ctx: Any, node: Any, **kwargs: Any) -> Any:
        from etlantic.runtime.sql_exec import execute_sql_source

        return await execute_sql_source(**kwargs)

    async def execute_step(self, ctx: Any, node: Any, **kwargs: Any) -> Any:
        from etlantic.runtime.sql_exec import execute_sql_step

        return await execute_sql_step(**kwargs)

    async def execute_sink(self, ctx: Any, node: Any, **kwargs: Any) -> Any:
        from etlantic.runtime.sql_exec import execute_sql_sink

        return await execute_sql_sink(**kwargs)


class SparkExecutor:
    def matches(self, engine: str) -> bool:
        return get_engine_registry().is_spark_engine(engine)

    async def execute_source(self, ctx: Any, node: Any, **kwargs: Any) -> Any:
        from etlantic.runtime.spark_exec import execute_spark_source

        return await execute_spark_source(**kwargs)

    async def execute_step(self, ctx: Any, node: Any, **kwargs: Any) -> Any:
        from etlantic.runtime.spark_exec import execute_spark_step

        return await execute_spark_step(**kwargs)

    async def execute_sink(self, ctx: Any, node: Any, **kwargs: Any) -> Any:
        from etlantic.runtime.spark_exec import execute_spark_sink

        return await execute_spark_sink(**kwargs)


_BUILTIN_EXECUTORS: tuple[Any, ...] = (
    SparkExecutor(),
    SqlExecutor(),
    DataframeExecutor(),
)


class ExecutorRegistry:
    """Resolve the executor for a runtime engine name."""

    def __init__(self, executors: tuple[Any, ...] | None = None) -> None:
        self._executors = executors or _BUILTIN_EXECUTORS

    def resolve(self, engine: str) -> Any | None:
        for executor in self._executors:
            if executor.matches(engine):
                return executor
        return None


_DEFAULT_REGISTRY = ExecutorRegistry()


def get_executor_registry() -> ExecutorRegistry:
    return _DEFAULT_REGISTRY
