"""SQLAlchemy-backed PostgreSQL (reference) SQL plugin."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from pipelantic.capabilities import PluginCapabilities
from pipelantic.sql.helpers import require_safe_identifier
from pipelantic.sql.protocol import (
    SQL_PROTOCOL_VERSION,
    CompiledSql,
    RelationRef,
    SqlExecutionContext,
    SqlExecutionResult,
    SqlPluginInfo,
    SqlQuery,
    SqlWrite,
)
from pipelantic_sql.catalog import inspect_relation as catalog_inspect
from pipelantic_sql.compiler import SqlCompiler
from pipelantic_sql.dialect_postgresql import detect_dialect, quote_identifier
from pipelantic_sql.executor import SqlExecutor

__version__ = "0.6.0"


def create_plugin() -> PostgresSqlPlugin:
    """Entry-point factory."""
    return PostgresSqlPlugin()


class PostgresSqlPlugin:
    """Reference SQL plugin (PostgreSQL-shaped; SQLAlchemy Core)."""

    def __init__(self, *, url: str | None = None) -> None:
        self._url = url or os.environ.get(
            "PIPELANTIC_SQL_URL", "sqlite+pysqlite:///:memory:"
        )
        self._engine: Engine | None = None
        self._rows_fetched = [0]
        dialect = detect_dialect(self._url)
        extras = (
            frozenset({"postgresql", "sqlalchemy"})
            if dialect == "postgresql"
            else frozenset({"sqlite", "sqlalchemy"})
        )
        caps = PluginCapabilities(
            engine="sql",
            async_execution=False,
            dataframe=False,
            sql=True,
            transactions=True,
            cancellation=False,
            schema_inspection=True,
            sql_merge=dialect == "postgresql",
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
            name="pipelantic-sql",
            engine="sql",
            dialect=dialect,
            version=__version__,
            protocol_version=SQL_PROTOCOL_VERSION,
            capabilities=caps,
        )
        self._compiler = SqlCompiler(
            dialect=dialect, supports_merge=caps.supports("sql_merge")
        )

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
        )

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
        return self._compiler.compile_query(query, context=context)

    def compile_write(
        self,
        write: SqlWrite,
        *,
        context: SqlExecutionContext,
    ) -> CompiledSql:
        return self._compiler.compile_write(write, context=context)

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
        return self.execute([compiled], params=params, context=context, fetch=False)

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
        )

    def inspect_relation(
        self,
        relation: RelationRef,
        *,
        context: SqlExecutionContext,
    ) -> dict[str, Any]:
        _ = context
        return catalog_inspect(self._get_engine(), relation, dialect=self.info.dialect)
