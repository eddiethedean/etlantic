"""Explicit run-scoped DuckDB connections and security setup."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

import duckdb
from etlantic_duckdb.config import DuckDBConfig


def _quote_setting(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def configure_connection(conn: duckdb.DuckDBPyConnection, config: DuckDBConfig) -> None:
    """Apply and verify the fail-closed configuration before user work."""
    conn.execute("SET enable_external_access = false")
    conn.execute("SET autoinstall_known_extensions = false")
    conn.execute("SET autoload_known_extensions = false")
    # These settings exist in supported DuckDB releases; fail closed if they
    # disappear instead of silently weakening the security posture.
    for setting in (
        "allow_community_extensions",
        "allow_unsigned_extensions",
        "allow_persistent_secrets",
        "allow_unredacted_secrets",
    ):
        conn.execute(f"SET {setting} = false")
    conn.execute(f"SET threads = {int(config.threads)}")
    if config.memory_limit:
        conn.execute(f"SET memory_limit = {_quote_setting(config.memory_limit)}")
    temp_directory = config.resolve_temp_directory()
    if temp_directory:
        conn.execute(f"SET temp_directory = {_quote_setting(temp_directory)}")
    for setting in (
        "enable_external_access",
        "autoinstall_known_extensions",
        "autoload_known_extensions",
        "allow_community_extensions",
        "allow_unsigned_extensions",
        "allow_persistent_secrets",
        "allow_unredacted_secrets",
    ):
        row = conn.execute(f"SELECT current_setting('{setting}')").fetchone()
        if row is None or str(row[0]).lower() not in {"false", "0"}:
            raise RuntimeError(f"DuckDB security setting {setting} was not enforced")
    conn.execute("SET lock_configuration = true")


@dataclass
class DuckDBSession:
    run_id: str
    config: DuckDBConfig
    connection: duckdb.DuckDBPyConnection
    lock: threading.RLock
    statement_count: int = 0
    closed: bool = False

    def execute(self, sql: str, params: Any = None) -> Any:
        if self.closed:
            raise RuntimeError("DuckDB run session is closed")
        self.statement_count += 1
        if self.statement_count > self.config.max_statements:
            raise RuntimeError("DuckDB statement budget exceeded")
        with self.lock:
            if params is None:
                return self.connection.execute(sql)
            return self.connection.execute(sql, params)

    def reserve_statements(self, count: int) -> None:
        """Reserve counted work before a multi-row operation mutates state."""
        if count < 0:
            raise ValueError("DuckDB statement reservation must be non-negative")
        with self.lock:
            next_count = self.statement_count + count
            if next_count > self.config.max_statements:
                raise RuntimeError("DuckDB statement budget exceeded")
            self.statement_count = next_count

    def close(self) -> None:
        if self.closed:
            return
        with self.lock:
            try:
                self.connection.close()
            finally:
                # A failed close must never leave this session eligible for
                # reuse. The manager detaches it before invoking close().
                self.closed = True


class DuckDBConnectionManager:
    """One explicit connection per run, isolated across plugin instances."""

    def __init__(self, config: DuckDBConfig | None = None) -> None:
        self.config = config or DuckDBConfig()
        self._sessions: dict[str, DuckDBSession] = {}
        self._lock = threading.RLock()

    def session(self, run_id: str) -> DuckDBSession:
        key = str(run_id)
        with self._lock:
            session = self._sessions.get(key)
            if session is not None and not session.closed:
                return session
            database = self.config.resolve_database()
            conn = duckdb.connect(database=database, read_only=self.config.read_only)
            try:
                configure_connection(conn, self.config)
            except Exception:
                conn.close()
                raise
            session = DuckDBSession(
                run_id=key,
                config=self.config,
                connection=conn,
                lock=threading.RLock(),
            )
            self._sessions[key] = session
            return session

    def cleanup_run(self, run_id: str) -> None:
        with self._lock:
            session = self._sessions.pop(str(run_id), None)
        if session is not None:
            session.close()

    def cleanup_all(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.close()

    def active_run_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(k for k, v in self._sessions.items() if not v.closed))
