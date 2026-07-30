"""SQLAlchemy-backed SQL plugin (PostgreSQL + SQLite Tier A reference)."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from etlantic.capabilities import PluginCapabilities
from etlantic.sql.helpers import require_safe_identifier
from etlantic.sql.protocol import (
    SQL_PROTOCOL_VERSION,
    CompiledSql,
    RelationRef,
    SqlExecutionContext,
    SqlExecutionResult,
    SqlPluginInfo,
    SqlQuery,
    SqlWrite,
    TransactionOutcome,
    WriteIntentKind,
)
from etlantic_sql.catalog import create_table_from_model as catalog_create_table
from etlantic_sql.catalog import inspect_relation as catalog_inspect
from etlantic_sql.catalog import validate_primary_keys as catalog_validate_pk
from etlantic_sql.compiler import SqlCompiler
from etlantic_sql.dialect_postgresql import dialect_info, quote_identifier
from etlantic_sql.executor import SqlExecutor

__version__ = "0.36.0"


def create_plugin() -> PostgresSqlPlugin:
    """Entry-point factory for ``etlantic.sql_plugins``."""
    return PostgresSqlPlugin()


class PostgresSqlPlugin:
    """Reference SQL plugin (Tier A: PostgreSQL + SQLite via SQLAlchemy Core)."""

    def __init__(self, *, url: str | None = None) -> None:
        self._url = url or os.environ.get(
            "ETLANTIC_SQL_URL", "sqlite+pysqlite:///:memory:"
        )
        self._engine: Engine | None = None
        self._async_engine: Any | None = None
        self._rows_fetched = [0]
        self._bound_params: dict[str, dict[str, Any]] = {}
        self._staging_tables: list[str] = []
        info = dialect_info(self._url)
        self._dialect_info = info
        dialect = info.name
        supports_merge = info.supports_merge
        async_ok = _async_driver_available(self._url)
        if dialect == "postgresql":
            extras = frozenset(
                {"postgresql", "sqlalchemy", f"dialect_tier_{info.tier}"}
            )
        elif dialect == "sqlite":
            extras = frozenset({"sqlite", "sqlalchemy", f"dialect_tier_{info.tier}"})
        else:
            extras = frozenset(
                {dialect, "sqlalchemy", f"dialect_tier_{info.tier}", "gated"}
            )
        # Tier B / unknown: advertise core sql but not advanced features.
        tier_a = info.is_tier_a
        caps = PluginCapabilities(
            engine="sql",
            async_execution=async_ok and tier_a,
            dataframe=False,
            sql=True,
            transactions=tier_a,
            cancellation=False,
            schema_inspection=tier_a,
            sql_merge=supports_merge,
            sql_cte=info.supports_cte,
            sql_returning=info.supports_returning,
            sql_transactional_ddl=info.supports_transactional_ddl,
            sql_atomic_rename=tier_a,
            sql_catalog_inspect=tier_a,
            sql_trusted_fragments=False,
            eager=False,
            # Relational reuse is CTE/temp-relation fusion, not dataframe lazy.
            lazy=False,
            extras=extras,
        )
        self._info = SqlPluginInfo(
            name="etlantic-sql",
            engine="sql",
            dialect=dialect,
            version=__version__,
            protocol_version=SQL_PROTOCOL_VERSION,
            capabilities=caps,
        )
        self._compiler = SqlCompiler(dialect=dialect, supports_merge=supports_merge)

    @property
    def info(self) -> SqlPluginInfo:
        return self._info

    def capabilities(self) -> PluginCapabilities:
        assert self._info.capabilities is not None
        return self._info.capabilities

    def rows_fetched_total(self) -> int:
        return self._rows_fetched[0]

    def get_engine(self) -> Engine:
        """Return the shared SQLAlchemy engine for this plugin instance."""
        return self._get_engine()

    def _get_engine(self) -> Engine:
        if self._engine is None:
            if not self._dialect_info.is_tier_a:
                raise ValueError(
                    f"Dialect {self._dialect_info.name!r} is Tier "
                    f"{self._dialect_info.tier}; the reference plugin only "
                    "executes Tier A dialects (sqlite|postgresql)."
                )
            self._engine = create_engine(self._url, future=True)
        return self._engine

    def _executor(self) -> SqlExecutor:
        return SqlExecutor(
            engine=self._get_engine(),
            dialect=self.info.dialect,
            rows_fetched_counter=self._rows_fetched,
            bound_params=self._bound_params,
            staging_tables=self._staging_tables,
        )

    def _seal(self, compiled: CompiledSql) -> CompiledSql:
        """Move live bound values into a private map; strip from public metadata."""
        meta = dict(compiled.metadata)
        bound = dict(meta.pop("_bound_params", {}) or {})
        if bound:
            self._bound_params[compiled.statement_id] = bound
        return replace(compiled, metadata=meta)

    def quote_identifier(self, name: str) -> str:
        return quote_identifier(name, dialect=self.info.dialect)

    def relation_from_binding(
        self,
        *,
        binding: str,
        location: str | None,
        metadata: Mapping[str, Any] | None = None,
    ) -> RelationRef:
        _ = metadata
        if location:
            rel = RelationRef.parse(location)
            for part in (rel.catalog, rel.namespace, rel.name):
                if part is not None:
                    require_safe_identifier(part)
            return rel
        return RelationRef(name=require_safe_identifier(binding))

    def compile_query(
        self,
        query: SqlQuery,
        *,
        context: SqlExecutionContext,
    ) -> CompiledSql:
        return self._seal(self._compiler.compile_query(query, context=context))

    def compile_write(
        self,
        write: SqlWrite,
        *,
        context: SqlExecutionContext,
    ) -> CompiledSql:
        return self._seal(self._compiler.compile_write(write, context=context))

    def execute(
        self,
        compiled: Sequence[CompiledSql],
        *,
        params: Mapping[str, Any],
        context: SqlExecutionContext,
        fetch: bool = False,
    ) -> SqlExecutionResult:
        return self._executor().execute(
            compiled, params=params, context=context, fetch=fetch
        )

    def execute_write(
        self,
        write: SqlWrite,
        *,
        params: Mapping[str, Any],
        context: SqlExecutionContext,
    ) -> SqlExecutionResult:
        compiled = self.compile_write(write, context=context)
        result = self.execute([compiled], params=params, context=context, fetch=False)
        if result.outcome is not TransactionOutcome.COMMITTED:
            return result
        if write.intent in {WriteIntentKind.REPLACE, WriteIntentKind.SNAPSHOT}:
            staging_data = compiled.metadata.get("staging") or {}
            staging = RelationRef.from_dict(dict(staging_data))
            swap = self._executor().publish_replace(
                target=write.target,
                staging=staging,
                compiler=self._compiler,
                context=context,
            )
            swap.compiled = list(result.compiled) + list(swap.compiled)
            return swap
        return result

    async def execute_async(
        self,
        compiled: Sequence[CompiledSql],
        *,
        params: Mapping[str, Any],
        context: SqlExecutionContext,
        fetch: bool = False,
    ) -> SqlExecutionResult:
        """AsyncEngine execution path (requires async driver URL + extras)."""
        from etlantic_sql.async_executor import AsyncSqlExecutor

        if not self.capabilities().supports("async_execution"):
            raise ValueError(
                "async_execution is not advertised for this dialect/URL; fail closed"
            )
        executor = AsyncSqlExecutor(
            engine=await self._get_async_engine(),
            dialect=self.info.dialect,
            rows_fetched_counter=self._rows_fetched,
            bound_params=self._bound_params,
            staging_tables=self._staging_tables,
        )
        return await executor.execute(
            compiled, params=params, context=context, fetch=fetch
        )

    async def _get_async_engine(self) -> Any:
        if self._async_engine is None:
            from sqlalchemy.ext.asyncio import create_async_engine

            self._async_engine = create_async_engine(self._url, future=True)
        return self._async_engine

    def materialize_temp(
        self,
        query: SqlQuery,
        *,
        temp_name: str,
        params: Mapping[str, Any],
        context: SqlExecutionContext,
    ) -> SqlExecutionResult:
        return self._executor().materialize_temp(
            self._compiler,
            query,
            temp_name=temp_name,
            params=params,
            context=context,
            seal=self._seal,
        )

    def load_records(
        self,
        records: Sequence[Any],
        *,
        target: RelationRef,
        context: SqlExecutionContext,
    ) -> SqlExecutionResult:
        return self._executor().load_records(
            records, target=target, context=context, compiler=self._compiler
        )

    def fetch_records(
        self,
        relation: RelationRef | SqlQuery,
        *,
        params: Mapping[str, Any],
        context: SqlExecutionContext,
        contract_type: type[Any] | None = None,
    ) -> SqlExecutionResult:
        return self._executor().fetch_records(
            self._compiler,
            relation,
            params=params,
            context=context,
            contract_type=contract_type,
            seal=self._seal,
        )

    def inspect_relation(
        self,
        relation: RelationRef,
        *,
        context: SqlExecutionContext,
    ) -> dict[str, Any]:
        _ = context
        return catalog_inspect(self._get_engine(), relation, dialect=self.info.dialect)

    def create_table_from_model(
        self,
        model: Any,
        *,
        checkfirst: bool = True,
    ) -> dict[str, Any]:
        """Create a table from a SQLModel / SQLAlchemy Table metadata object."""
        return catalog_create_table(
            self._get_engine(),
            model,
            dialect=self.info.dialect,
            checkfirst=checkfirst,
        )

    def validate_primary_keys(
        self,
        relation: RelationRef,
        *,
        expected_keys: Sequence[str],
        context: SqlExecutionContext | None = None,
    ) -> dict[str, Any]:
        """Validate that ``relation`` declares the expected primary-key columns."""
        _ = context
        return catalog_validate_pk(
            self._get_engine(),
            relation,
            expected_keys=expected_keys,
            dialect=self.info.dialect,
        )

    def cleanup_staging(self) -> None:
        """Drop run-scoped durable staging tables."""
        self._executor().cleanup_staging()


def _async_driver_available(url: str) -> bool:
    """Return True when the URL looks like an async SQLAlchemy driver."""
    scheme = url.split("://", 1)[0].lower()
    async_markers = (
        "+asyncpg",
        "+aiosqlite",
        "+aiomysql",
        "+asyncmy",
        "+psycopg_async",
    )
    return any(marker in scheme for marker in async_markers)
