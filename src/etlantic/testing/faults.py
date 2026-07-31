"""Public failure-injection helpers for plugin and resilience conformance.

Part of the stable ``etlantic.testing`` foundation (0.37). Injection fires only
when ``ETLANTIC_FAULT_INJECTION`` is armed (see ``etlantic.runtime.faults``).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from etlantic.runtime.faults import (
    FaultBoundary,
    FaultSpec,
    FaultTrigger,
    active_faults,
    clear_faults,
    fault_injection_enabled,
    maybe_inject,
    maybe_inject_async,
    register_faults,
    reset_fault_counts,
)

__all__ = [
    "FaultBoundary",
    "FaultSpec",
    "FaultTrigger",
    "clear_faults",
    "fault_injection_enabled",
    "maybe_inject",
    "maybe_inject_async",
    "register_faults",
    "reset_fault_counts",
    "with_faults",
]

_FAULT_ENV = "ETLANTIC_FAULT_INJECTION"


@contextmanager
def with_faults(*specs: FaultSpec) -> Iterator[None]:
    """Install fault specs for the duration of a test block.

    Arms ``ETLANTIC_FAULT_INJECTION`` for the block when it is unset/empty so
    ``PipelineTestCase.faults`` and direct ``with_faults`` usage do not require
    a separate monkeypatch.
    """
    prior = os.environ.get(_FAULT_ENV)
    armed_here = prior is None or str(prior).strip() == ""
    if armed_here:
        os.environ[_FAULT_ENV] = "1"
    try:
        with active_faults(*specs):
            reset_fault_counts()
            try:
                yield
            finally:
                reset_fault_counts()
    finally:
        if armed_here:
            if prior is None:
                os.environ.pop(_FAULT_ENV, None)
            else:
                os.environ[_FAULT_ENV] = prior
