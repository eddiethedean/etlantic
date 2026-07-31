"""Request-scoped SQLModel session helpers for control-plane stores."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy.engine import Engine

from sqlmodel import Session, create_engine


def create_sqlite_engine(url: str = "sqlite://", **kwargs: Any) -> Engine:
    """Create an engine; use a file URL for restart durability tests."""
    connect_args = dict(kwargs.pop("connect_args", {}))
    if url.startswith("sqlite"):
        connect_args.setdefault("check_same_thread", False)
    return create_engine(url, connect_args=connect_args, **kwargs)


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """Yield a session that commits on success and rolls back on error."""
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def make_session_factory(engine: Engine):
    """Return a zero-arg factory that opens a short-lived Session."""

    def factory() -> Session:
        return Session(engine)

    return factory


def request_scoped_session(engine: Engine):
    """FastAPI-compatible dependency generator for a request-scoped session.

    Sessions stay in the API layer — never pass them into pipeline runtimes.
    """

    def dependency() -> Iterator[Session]:
        with Session(engine) as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    return dependency


__all__ = [
    "create_sqlite_engine",
    "make_session_factory",
    "request_scoped_session",
    "session_scope",
]
