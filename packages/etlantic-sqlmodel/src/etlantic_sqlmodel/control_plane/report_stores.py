"""Tenant/workspace-scoped durable ETLantic run reports."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import Table
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from etlantic.control_plane.models import ControlPlaneContext
from etlantic.reports.model import PipelineRunReport
from etlantic_sqlmodel.control_plane.models import RunReportRow
from etlantic_sqlmodel.control_plane.session import session_scope
from sqlmodel import Session, select


def _report_table() -> Table:
    return cast(Table, cast(Any, RunReportRow).__table__)


def create_run_report_tables(engine: Engine) -> None:
    """Create report tables for tests and local demos only."""
    _report_table().create(engine, checkfirst=True)


class SqlModelRunReportStore:
    """ReportStore-compatible adapter bound to a trusted control-plane scope."""

    def __init__(self, engine: Engine, ctx: ControlPlaneContext) -> None:
        self._engine = engine
        self._tenant_id = ctx.tenant.tenant_id
        self._workspace_id = ctx.workspace.workspace_id

    def put(self, report: PipelineRunReport) -> None:
        """Persist a report atomically, updating intermediate run projections."""
        if not isinstance(report.plan_fingerprint, str) or not report.plan_fingerprint:
            raise ValueError("Managed run reports require a plan fingerprint")
        payload = report.to_json(indent=None)
        updated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        for attempt in range(2):
            try:
                with session_scope(self._engine) as session:
                    row = self._get_row(session, report.run_id)
                    if row is None:
                        session.add(
                            RunReportRow(
                                tenant_id=self._tenant_id,
                                workspace_id=self._workspace_id,
                                run_id=report.run_id,
                                pipeline_id=report.pipeline_id,
                                plan_fingerprint=report.plan_fingerprint,
                                report_json=payload,
                                created_at=updated_at,
                                updated_at=updated_at,
                            )
                        )
                    else:
                        if row.plan_fingerprint != report.plan_fingerprint:
                            raise ValueError(
                                "A run report cannot change its accepted plan fingerprint"
                            )
                        row.pipeline_id = report.pipeline_id
                        row.report_json = payload
                        row.updated_at = updated_at
                        session.add(row)
                    session.flush()
                return
            except IntegrityError:
                if attempt == 1:
                    raise

    def get(self, run_id: str) -> PipelineRunReport | None:
        """Load a report only from this provider's bound scope."""
        with session_scope(self._engine) as session:
            row = self._get_row(session, run_id)
            return (
                None
                if row is None
                else PipelineRunReport.from_dict(json.loads(row.report_json))
            )

    def list(
        self,
        *,
        pipeline_id: str | None = None,
        limit: int | None = None,
    ) -> list[PipelineRunReport]:
        """List recent reports inside the fixed scope."""
        if limit is not None and limit < 1:
            return []
        with session_scope(self._engine) as session:
            statement = select(RunReportRow).where(
                RunReportRow.tenant_id == self._tenant_id,
                RunReportRow.workspace_id == self._workspace_id,
            )
            if pipeline_id is not None:
                statement = statement.where(RunReportRow.pipeline_id == pipeline_id)
            report_table = _report_table()
            statement = statement.order_by(
                report_table.c["updated_at"].desc(),
                report_table.c["id"].desc(),
            )
            if limit is not None:
                statement = statement.limit(limit)
            rows = session.exec(statement).all()
            return [
                PipelineRunReport.from_dict(json.loads(row.report_json)) for row in rows
            ]

    def _get_row(self, session: Session, run_id: str) -> RunReportRow | None:
        statement = select(RunReportRow).where(
            RunReportRow.tenant_id == self._tenant_id,
            RunReportRow.workspace_id == self._workspace_id,
            RunReportRow.run_id == run_id,
        )
        return session.exec(statement).first()


class SqlModelRunReportStoreProvider:
    """Factory returning report stores bound to trusted request/worker scopes."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def for_context(self, ctx: ControlPlaneContext) -> SqlModelRunReportStore:
        return SqlModelRunReportStore(self._engine, ctx)


__all__ = [
    "SqlModelRunReportStore",
    "SqlModelRunReportStoreProvider",
    "create_run_report_tables",
]
