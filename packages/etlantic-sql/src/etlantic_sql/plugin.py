"""SQLAlchemy-backed PostgreSQL (reference) SQL plugin."""

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
from etlantic_sql.catalog import inspect_relation as catalog_inspect
from etlantic_sql.compiler import SqlCompiler
from etlantic_sql.dialect_postgresql import detect_dialect, quote_identifier
from etlantic_sql.executor import SqlExecutor

__version__ = "0.13.0"


def create_plugin() -> PostgresSqlPlugin:
    """Entry-point factory."""
    return PostgresSqlPlugin()


class PostgresSqlPlugin:
    """Reference SQL plugin (PostgreSQL-shaped; SQLAlchemy Core)."""

    def __init__(self, *, url: str | None = None) -> None:
        self._url = url or os.environ.get(
            "ETLANTIC_SQL_URL", "sqlite+pysqlite:///:memory:"
        )
        self._engine: Engine | None = None
        self._rows_fetched = [0]
        self._bound_params: dict[str, dict[str, Any]] = {}
        self._staging_tables: list[str] = []
        dialect = detect_dialect(self._url)
        extras = (
            frozenset({"postgresql", "sqlalchemy"})
            if dialect == "postgresql"
            else frozenset({"sqlite", "sqlalchemy"})
        )
        # MERGE is not implemented in 0.6 — never advertise it.
        caps = PluginCapabilities(
            engine="sql",
            async_execution=False,
            dataframe=False,
            sql=True,
            transactions=True,
            cancellation=False,
            schema_inspection=True,
            sql_merge=False,
            sql_cte=True,
            sql_returning=dialect == "postgresql",
            sql_transactional_ddl=dialect == "postgresql",
            sql_atomic_rename=True,
            sql_catalog_inspect=True,
            sql_trusted_fragments=False,
            eager=False,
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
        self._compiler = SqlCompiler(dialect=dialect, supports_merge=False)

    @property
    def info(self) -> SqlPluginInfo:
        return self._info

    def capabilities(self) -> PluginCapabilities:
        assert self._info.capabilities is not None
        return self._info.capabilities

    def rows_fetched_total(self) -> int:
        return self._rows_fetched[0]

    def _get_engine(self) -> Engine:
        if self._engine is None:
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

    def cleanup_staging(self) -> None:
        """Drop run-scoped durable staging tables."""
        self._executor().cleanup_staging()
