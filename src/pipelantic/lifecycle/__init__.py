"""Lifecycle extension package."""

from __future__ import annotations

from pipelantic.lifecycle.callbacks import (
    CallbackRegistry,
    FailureAction,
    StepFailureContext,
)
from pipelantic.lifecycle.middleware import MiddlewareStack
from pipelantic.lifecycle.outbound import Emit, OutboundEvent
from pipelantic.lifecycle.resources import Inject, ResourceManager
from pipelantic.lifecycle.runtime import PipelineRuntime

__all__ = [
    "CallbackRegistry",
    "Emit",
    "FailureAction",
    "Inject",
    "MiddlewareStack",
    "OutboundEvent",
    "PipelineRuntime",
    "ResourceManager",
    "StepFailureContext",
]
