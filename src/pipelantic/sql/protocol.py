"""Versioned SQL execution protocol (pipelantic.sql/1).

Core stays driver-free. The reference plugin lives in ``pipelantic-sql``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pipelantic.capabilities import PluginCapabilities

SQL_PROTOCOL_VERSION = "pipelantic.sql/1"
SQL_ENGINES = frozenset({"sql"})


class SqlPhase(StrEnum):
    """Reportable phases of SQL region / step execution."""

    RESOLVE = "resolve"
    COMPILE = "compile"
    EXECUTE = "execute"
    INSPECT = "inspect"
    PUBLISH = "publish"
    FETCH = "fetch"
    LOAD = "load"
    CLEANUP = "cleanup"


class TransactionOutcome(StrEnum):
    """Known transaction outcomes for retry gating."""

    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    UNKNOWN = "unknown"
    NOT_STARTED = "not_started"


class WriteIntentKind(StrEnum):
    """Portable SQL write / publication intents."""

    APPEND = "append"
    INSERT_SELECT = "insert_select"
    REPLACE = "replace"
    SNAPSHOT = "snapshot"
    CREATE_TABLE_AS = "create_table_as"
    MERGE = "merge"
    REPLACE_PARTITION = "replace_partition"


class AtomicPublicationStrategy(StrEnum):
    """How replace/snapshot must publish atomically."""

    RENAME_SWAP = "rename_swap"
    TRANSACTIONAL = "transactional"
    STAGING_SWAP = "staging_swap"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class RelationRef:
    """Logical relation identity without credentials or live connections."""

    name: str
    namespace: str | None = None
    catalog: str | None = None
    version: str | None = None

    @property
    def qualified_name(self) -> str:
        parts = [p for p in (self.catalog, self.namespace, self.name) if p]
        return ".".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "namespace": self.namespace,
            "catalog": self.catalog,
            "version": self.version,
            "qualified_name": self.qualified_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RelationRef:
        return cls(
            name=str(data["name"]),
            namespace=data.get("namespace"),
            catalog=data.get("catalog"),
            version=data.get("version"),
        )

    @classmethod
    def parse(cls, value: str) -> RelationRef:
        """Parse ``catalog.schema.name`` or ``schema.name`` or ``name``."""
        parts = [p for p in str(value).split(".") if p]
        if len(parts) == 1:
            return cls(name=parts[0])
        if len(parts) == 2:
            return cls(namespace=parts[0], name=parts[1])
        return cls(catalog=parts[0], namespace=parts[1], name=parts[2])


@dataclass(frozen=True, slots=True)
class SqlParameter:
    """Named parameter placeholder (value resolved only at runtime)."""

    name: str
    source: str | None = None  # logical source for explain; never a secret value

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "source": self.source}


@dataclass(frozen=True, slots=True)
class ColumnRef:
    """Column reference within a relation alias."""

    column: str
    relation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"column": self.column, "relation": self.relation}


@dataclass(frozen=True, slots=True)
class LiteralExpr:
    """Typed literal (serialized into bound parameters, never interpolated)."""

    value: Any
    sql_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "literal", "sql_type": self.sql_type, "has_value": True}


@dataclass(frozen=True, slots=True)
class BinaryExpr:
    """Binary expression over portable operators."""

    op: str
    left: Any
    right: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "binary",
            "op": self.op,
            "left": _expr_to_dict(self.left),
            "right": _expr_to_dict(self.right),
        }


@dataclass(frozen=True, slots=True)
class ConcatExpr:
    """String concatenation of columns / literals."""

    parts: tuple[Any, ...]
    separator: str = " "
    alias: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "concat",
            "parts": [_expr_to_dict(p) for p in self.parts],
            "separator": self.separator,
            "alias": self.alias,
        }


@dataclass(frozen=True, slots=True)
class AliasedExpr:
    """Projection expression with output alias."""

    expr: Any
    alias: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "aliased",
            "expr": _expr_to_dict(self.expr),
            "alias": self.alias,
        }


def _expr_to_dict(expr: Any) -> Any:
    if hasattr(expr, "to_dict"):
        return expr.to_dict()
    if isinstance(expr, str):
        return {"kind": "column", "column": expr}
    return {"kind": "opaque", "repr": repr(expr)}


@dataclass(frozen=True, slots=True)
class TrustedSqlFragment:
    """Escape hatch for trusted SQL text (policy-gated; disabled by default)."""

    text: str
    param_names: tuple[str, ...] = ()
    allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "trusted_fragment",
            "param_names": list(self.param_names),
            "allowed": self.allowed,
            "text_length": len(self.text),
        }


@dataclass(frozen=True, slots=True)
class SqlQuery:
    """Closed portable select / projection query IR."""

    source: RelationRef
    columns: tuple[Any, ...] = ()
    where: Any | None = None
    limit: int | None = None
    distinct: bool = False
    parameters: tuple[SqlParameter, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "select",
            "source": self.source.to_dict(),
            "columns": [_expr_to_dict(c) for c in self.columns],
            "where": _expr_to_dict(self.where) if self.where is not None else None,
            "limit": self.limit,
            "distinct": self.distinct,
            "parameters": [p.to_dict() for p in self.parameters],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class SqlWrite:
    """Write / publication intent against a target relation."""

    intent: WriteIntentKind
    target: RelationRef
    source: SqlQuery | RelationRef | None = None
    atomic: AtomicPublicationStrategy = AtomicPublicationStrategy.TRANSACTIONAL
    merge_keys: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        source: Any
        if isinstance(self.source, (SqlQuery, RelationRef)):
            source = self.source.to_dict()
        else:
            source = None
        return {
            "intent": self.intent.value,
            "target": self.target.to_dict(),
            "source": source,
            "atomic": self.atomic.value,
            "merge_keys": list(self.merge_keys),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class CompiledSql:
    """Compiled statement with secret-free parameter metadata."""

    statement_id: str
    text: str
    param_names: tuple[str, ...] = ()
    redacted_params: Mapping[str, str] = field(default_factory=dict)
    dialect: str = "postgresql"
    logical_nodes: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "statement_id": self.statement_id,
            "text": self.text,
            "param_names": list(self.param_names),
            "redacted_params": dict(self.redacted_params),
            "dialect": self.dialect,
            "logical_nodes": list(self.logical_nodes),
            "metadata": dict(self.metadata),
        }


@dataclass
class SqlMetrics:
    """Normalized SQL execution metrics (no query values)."""

    rows_affected: int | None = None
    rows_fetched: int = 0
    statements: int = 0
    fused_steps: int = 0
    phases: list[str] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows_affected": self.rows_affected,
            "rows_fetched": self.rows_fetched,
            "statements": self.statements,
            "fused_steps": self.fused_steps,
            "phases": list(self.phases),
            "extras": dict(self.extras),
        }


@dataclass
class SqlExecutionResult:
    """Result of compiling/executing SQL work."""

    outcome: TransactionOutcome = TransactionOutcome.NOT_STARTED
    relation: RelationRef | None = None
    metrics: SqlMetrics = field(default_factory=SqlMetrics)
    compiled: list[CompiledSql] = field(default_factory=list)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    backend_ref: str | None = None
    records: list[Any] | None = None  # only set at hybrid fetch boundaries

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "relation": self.relation.to_dict() if self.relation else None,
            "metrics": self.metrics.to_dict(),
            "compiled": [c.to_dict() for c in self.compiled],
            "diagnostics": list(self.diagnostics),
            "backend_ref": self.backend_ref,
            "records_fetched": len(self.records) if self.records is not None else 0,
        }


@dataclass(frozen=True, slots=True)
class SqlPluginInfo:
    """Installed SQL plugin metadata."""

    name: str
    engine: str
    dialect: str
    version: str
    protocol_version: str = SQL_PROTOCOL_VERSION
    capabilities: PluginCapabilities | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "engine": self.engine,
            "dialect": self.dialect,
            "version": self.version,
            "protocol_version": self.protocol_version,
            "capabilities": (
                self.capabilities.to_dict() if self.capabilities is not None else None
            ),
        }


@dataclass(frozen=True, slots=True)
class SqlExecutionContext:
    """Runtime identity and connection binding for SQL work."""

    run_id: str
    pipeline_id: str
    plan_id: str
    step_name: str
    engine: str = "sql"
    attempt: int = 1
    connection_binding: str | None = None
    allow_trusted_sql: bool = False
    capture_explain: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class SqlPlugin(Protocol):
    """Protocol for SQL execution backends."""

    @property
    def info(self) -> SqlPluginInfo: ...

    def capabilities(self) -> PluginCapabilities:
        """Return declared SQL / dialect capabilities."""
        ...

    def quote_identifier(self, name: str) -> str:
        """Validate and quote an identifier; raise on illegal names."""
        ...

    def relation_from_binding(
        self,
        *,
        binding: str,
        location: str | None,
        metadata: Mapping[str, Any] | None = None,
    ) -> RelationRef:
        """Map a storage/binding location to a RelationRef."""
        ...

    def compile_query(
        self,
        query: SqlQuery,
        *,
        context: SqlExecutionContext,
    ) -> CompiledSql:
        """Compile a portable query to parameterized dialect SQL."""
        ...

    def compile_write(
        self,
        write: SqlWrite,
        *,
        context: SqlExecutionContext,
    ) -> CompiledSql:
        """Compile a write / publication intent."""
        ...

    def execute(
        self,
        compiled: Sequence[CompiledSql],
        *,
        params: Mapping[str, Any],
        context: SqlExecutionContext,
        fetch: bool = False,
    ) -> SqlExecutionResult:
        """Execute compiled statements.

        When ``fetch`` is False (SQL-to-SQL), must not materialize rows into
        Python. When True (hybrid boundary), may return ``records``.
        """
        ...

    def execute_write(
        self,
        write: SqlWrite,
        *,
        params: Mapping[str, Any],
        context: SqlExecutionContext,
    ) -> SqlExecutionResult:
        """Compile and execute a write intent."""
        ...

    def materialize_temp(
        self,
        query: SqlQuery,
        *,
        temp_name: str,
        params: Mapping[str, Any],
        context: SqlExecutionContext,
    ) -> SqlExecutionResult:
        """Create a temporary relation from a query without fetching rows."""
        ...

    def load_records(
        self,
        records: Sequence[Any],
        *,
        target: RelationRef,
        context: SqlExecutionContext,
    ) -> SqlExecutionResult:
        """Load Python/dataframe records into a staging relation."""
        ...

    def fetch_records(
        self,
        relation: RelationRef | SqlQuery,
        *,
        params: Mapping[str, Any],
        context: SqlExecutionContext,
        contract_type: type[Any] | None = None,
    ) -> SqlExecutionResult:
        """Fetch rows at a hybrid boundary (counts toward rows_fetched)."""
        ...

    def inspect_relation(
        self,
        relation: RelationRef,
        *,
        context: SqlExecutionContext,
    ) -> dict[str, Any]:
        """Inspect catalog metadata without reading source rows."""
        ...

    def rows_fetched_total(self) -> int:
        """Instrumentation: cumulative rows fetched into Python."""
        ...
