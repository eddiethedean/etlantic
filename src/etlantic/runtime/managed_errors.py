"""Typed failures used by managed execution workers."""

from __future__ import annotations


class ExecutionRejected(ValueError):
    """Accepted work is malformed or unsupported before ETL effects begin."""


class UnknownCommitError(RuntimeError):
    """An external effect may have committed; automatic retry is unsafe."""


__all__ = ["ExecutionRejected", "UnknownCommitError"]
