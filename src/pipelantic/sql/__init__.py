"""Versioned SQL execution protocol (pipelantic.sql/1).

Core stays driver-free. Install ``pipelantic-sql`` for the PostgreSQL
reference plugin.
"""

from __future__ import annotations

from pipelantic.sql.discovery import (
    SQL_PLUGIN_ENTRY_POINT,
    discover_sql_plugins,
    load_sql_plugin,
    register_discovered_plugins,
)
from pipelantic.sql.expression import alias, col, concat, lit, select, trusted_sql
from pipelantic.sql.helpers import (
    is_safe_identifier,
    redact_params,
    require_safe_identifier,
    sqlmodel_table_to_relation,
)
from pipelantic.sql.protocol import (
    SQL_ENGINES,
    SQL_PROTOCOL_VERSION,
    AliasedExpr,
    AtomicPublicationStrategy,
    BinaryExpr,
    ColumnRef,
    CompiledSql,
    ConcatExpr,
    LiteralExpr,
    RelationRef,
    SqlExecutionContext,
    SqlExecutionResult,
    SqlMetrics,
    SqlParameter,
    SqlPhase,
    SqlPlugin,
    SqlPluginInfo,
    SqlQuery,
    SqlWrite,
    TransactionOutcome,
    TrustedSqlFragment,
    WriteIntentKind,
)
from pipelantic.sql.write import append, insert_select, merge, replace

__all__ = [
    "SQL_ENGINES",
    "SQL_PLUGIN_ENTRY_POINT",
    "SQL_PROTOCOL_VERSION",
    "AliasedExpr",
    "AtomicPublicationStrategy",
    "BinaryExpr",
    "ColumnRef",
    "CompiledSql",
    "ConcatExpr",
    "LiteralExpr",
    "RelationRef",
    "SqlExecutionContext",
    "SqlExecutionResult",
    "SqlMetrics",
    "SqlParameter",
    "SqlPhase",
    "SqlPlugin",
    "SqlPluginInfo",
    "SqlQuery",
    "SqlWrite",
    "TransactionOutcome",
    "TrustedSqlFragment",
    "WriteIntentKind",
    "alias",
    "append",
    "col",
    "concat",
    "discover_sql_plugins",
    "insert_select",
    "is_safe_identifier",
    "lit",
    "load_sql_plugin",
    "merge",
    "redact_params",
    "register_discovered_plugins",
    "replace",
    "require_safe_identifier",
    "select",
    "sqlmodel_table_to_relation",
    "trusted_sql",
]
