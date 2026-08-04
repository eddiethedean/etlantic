"""Governed erasure protocols (CP4)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from etlantic.control_plane.erasure_models import (
    ErasureAction,
    ErasurePlan,
    ErasureReport,
    ErasureRequest,
    ErasureStepResult,
)
from etlantic.control_plane.models import ControlPlaneContext


@runtime_checkable
class ErasureProvider(Protocol):
    """Backend capability surface for delete/anonymize/lookup/proof/retry."""

    provider_id: str

    def supports(self, action: ErasureAction) -> bool:
        ...

    def execute(
        self,
        ctx: ControlPlaneContext,
        *,
        action: ErasureAction,
        subject_key_fingerprint: str,
        field_paths: Sequence[str],
    ) -> ErasureStepResult:
        ...


@runtime_checkable
class ErasureStore(Protocol):
    """Versioned erasure request → plan → report coordination."""

    def create_request(
        self,
        ctx: ControlPlaneContext,
        *,
        subject_key_fingerprint: str,
        field_paths: Sequence[str],
        legal_hold: bool = False,
        request_id: str | None = None,
    ) -> ErasureRequest:
        ...

    def get_request(
        self, ctx: ControlPlaneContext, *, request_id: str
    ) -> ErasureRequest:
        ...

    def plan(
        self,
        ctx: ControlPlaneContext,
        *,
        request_id: str,
        providers: Sequence[ErasureProvider],
        actions: Sequence[ErasureAction] | None = None,
    ) -> ErasurePlan:
        ...

    def execute(
        self,
        ctx: ControlPlaneContext,
        *,
        plan_id: str,
        providers: Sequence[ErasureProvider],
    ) -> ErasureReport:
        ...

    def get_report(
        self, ctx: ControlPlaneContext, *, report_id: str
    ) -> ErasureReport:
        ...


__all__ = ["ErasureProvider", "ErasureStore"]
