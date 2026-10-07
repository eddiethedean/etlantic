"""Typed failures used by managed execution workers."""

from __future__ import annotations


class ExecutionRejected(ValueError):
    """Accepted work is malformed or unsupported before ETL effects begin."""


class ExecutionCancelled(RuntimeError):
    """The current attempt stopped before execution while waiting for ownership."""


class UnknownCommitError(RuntimeError):
    """An external effect may have committed; automatic retry is unsafe."""


__all__ = ["ExecutionCancelled", "ExecutionRejected", "UnknownCommitError"]
