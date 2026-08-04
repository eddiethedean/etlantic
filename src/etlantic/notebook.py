"""Optional notebook / IPython display helpers (0.44)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from html import escape
from typing import Any

from etlantic.mermaid import graph_to_mermaid
from etlantic.model import LogicalGraph
from etlantic.plan.model import PipelinePlan
from etlantic.profile import Profile, resolve_profile
from etlantic.reports.model import PipelineRunReport
from etlantic.runtime.request import RunRequest, RunSelection
from etlantic.viz import graph_to_html, logical_graph_to_ir

DEFAULT_ROW_LIMIT = 50
DEFAULT_BYTE_LIMIT = 64_000
DEFAULT_COLUMN_LIMIT = 32


def _text_graph(graph: LogicalGraph) -> str:
    lines = [f"Pipeline {graph.pipeline_name} ({graph.pipeline_id})"]
    for node in graph.nodes:
        lines.append(f"  - {node.kind.value}: {node.name}")
    for edge in graph.edges:
        lines.append(
            f"  {edge.producer_node}.{edge.producer_port} -> "
            f"{edge.consumer_node}.{edge.consumer_port}"
        )
    return "\n".join(lines)


def _identity_fingerprint(target: Any) -> str:
    name = getattr(target, "__name__", None) or getattr(target, "pipeline_name", None)
    module = getattr(target, "__module__", "")
    raw = f"{module}:{name}:{id(target)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class PipelineDisplay:
    """Plain-text / HTML representations for a Pipeline class or LogicalGraph.

    Side-effect free: does not resolve secrets, import execution plugins,
    read artifacts, or contact remote systems.
    """

    def __init__(self, target: Any) -> None:
        if hasattr(target, "inspect"):
            self.graph = target.inspect()
            self.name = getattr(target, "__name__", self.graph.pipeline_name)
            self._target = target
        elif isinstance(target, LogicalGraph):
            self.graph = target
            self.name = target.pipeline_name
            self._target = target
        else:
            raise TypeError("Expected Pipeline subclass or LogicalGraph")
        self.identity = _identity_fingerprint(self._target)

    def _repr_pretty_(self, p: Any, cycle: bool) -> None:
        p.text(self.__str__())

    def __str__(self) -> str:
        return _text_graph(self.graph)

    def _repr_html_(self) -> str:
        return graph_to_html(logical_graph_to_ir(self.graph))

    def mermaid(self) -> str:
        return graph_to_mermaid(self.graph)


class PlanDisplay:
    def __init__(self, plan: PipelinePlan, *, stale: bool = False) -> None:
        self.plan = plan
        self.stale = stale

    def __str__(self) -> str:
        stale = " STALE" if self.stale else ""
        return (
            f"plan_id={self.plan.plan_id}{stale}\n"
            f"fingerprint={self.plan.fingerprint}\n"
            f"profile={self.plan.profile_name}\n"
            f"nodes={len(self.plan.logical_graph.nodes)}"
        )

    def _repr_html_(self) -> str:
        badge = (
            '<p style="color:#a40"><strong>Stale:</strong> pipeline redefined '
            "after this plan was created.</p>"
            if self.stale
            else ""
        )
        return (
            badge
            + f"<pre>{escape(str(self))}</pre>"
            + graph_to_html(logical_graph_to_ir(self.plan.logical_graph))
        )


class ReportDisplay:
    def __init__(self, report: PipelineRunReport, *, stale: bool = False) -> None:
        self.report = report
        self.stale = stale

    def __str__(self) -> str:
        prefix = "[STALE] " if self.stale else ""
        return prefix + self.report.to_text()

    def _repr_html_(self) -> str:
        badge = (
            "<p><strong>Stale report</strong> — model changed after run.</p>"
            if self.stale
            else ""
        )
        return badge + self.report.to_html()


class DiagnosticsDisplay:
    def __init__(self, report: Any) -> None:
        self.report = report

    def __str__(self) -> str:
        lines = [f"valid={getattr(self.report, 'valid', None)}"]
        for d in getattr(self.report, "diagnostics", ()):
            lines.append(
                f"{d.severity.value if hasattr(d.severity, 'value') else d.severity}: {d.code} {d.message}"
            )
        return "\n".join(lines)

    def _repr_html_(self) -> str:
        return f"<pre>{escape(str(self))}</pre>"


class ArtifactPreview:
    """Bounded, redacted artifact preview for notebooks."""

    def __init__(
        self,
        rows: list[dict[str, Any]] | tuple[dict[str, Any], ...] | Any,
        *,
        row_limit: int = DEFAULT_ROW_LIMIT,
        byte_limit: int = DEFAULT_BYTE_LIMIT,
        column_limit: int = DEFAULT_COLUMN_LIMIT,
    ) -> None:
        from etlantic.runtime.logging import redact_value

        self.truncated = False
        self.sampled = False
        if hasattr(rows, "to_dicts"):
            data = list(rows.to_dicts())  # type: ignore[union-attr]
        elif isinstance(rows, (list, tuple)):
            data = list(rows)
        else:
            data = [{"value": rows}]
        if len(data) > row_limit:
            data = data[:row_limit]
            self.truncated = True
            self.sampled = True
        cleaned: list[dict[str, Any]] = []
        for row in data:
            if not isinstance(row, dict):
                row = {"value": row}
            keys = list(row.keys())[:column_limit]
            if len(row) > column_limit:
                self.truncated = True
            cleaned.append(redact_value({k: row[k] for k in keys}))
        encoded = json.dumps(cleaned, default=str)
        if len(encoded.encode("utf-8")) > byte_limit:
            encoded = encoded[:byte_limit] + "…"
            self.truncated = True
            cleaned = [{"_truncated": True, "preview": encoded}]
        self.rows = cleaned

    def __str__(self) -> str:
        suffix = " (truncated)" if self.truncated else ""
        return json.dumps(self.rows, indent=2, default=str) + suffix

    def _repr_html_(self) -> str:
        note = "<p><em>Truncated/sampled preview</em></p>" if self.truncated else ""
        return note + f"<pre>{escape(str(self))}</pre>"


@dataclass
class NotebookSession:
    """Explicit notebook session helper (no hidden kernel globals)."""

    profile: Profile | str = "local"
    selection: RunSelection = field(default_factory=RunSelection.all)
    artifacts: dict[str, Any] = field(default_factory=dict)
    _model_identity: str | None = None
    _plan: PipelinePlan | None = None
    _report: PipelineRunReport | None = None
    _pipeline: Any | None = None
    breakpoints: set[str] = field(
        default_factory=lambda: {
            "validation",
            "pre_step",
            "post_step",
            "failure",
            "publication",
        }
    )
    cancel_requested: bool = False

    def resolved_profile(self) -> Profile:
        return resolve_profile(self.profile)

    def set_profile(self, profile: Profile | str) -> None:
        self.profile = profile

    def select(
        self, *, run_one: str | None = None, run_until: str | None = None
    ) -> None:
        if run_one and run_until:
            raise ValueError("Use only one of run_one or run_until")
        if run_one:
            self.selection = RunSelection.only(run_one)
        elif run_until:
            self.selection = RunSelection.until(run_until)
        else:
            self.selection = RunSelection.all()

    def remember(self, name: str, value: Any) -> None:
        self.artifacts[name] = value

    def bind_pipeline(self, pipeline_cls: type[Any]) -> None:
        identity = _identity_fingerprint(pipeline_cls)
        prior = self._model_identity
        prior_clean = prior[6:] if prior and prior.startswith("stale:") else prior
        if prior_clean and prior_clean != identity:
            self._plan = None
            self._report = None
            self._model_identity = f"stale:{identity}"
        else:
            self._model_identity = identity
        self._pipeline = pipeline_cls

    @property
    def stale(self) -> bool:
        if self._model_identity is None:
            return False
        if self._model_identity.startswith("stale:"):
            return True
        if self._pipeline is None:
            return False
        return _identity_fingerprint(self._pipeline) != self._model_identity

    def mark_redefined(self, pipeline_cls: type[Any]) -> None:
        """Call when a notebook cell redefines the pipeline class."""
        new_id = _identity_fingerprint(pipeline_cls)
        if self._model_identity and self._model_identity != new_id:
            self._model_identity = f"stale:{self._model_identity}"
        self._pipeline = pipeline_cls

    def force_stale(self) -> None:
        """Test/helper: mark current plan/report identity as stale."""
        if self._model_identity:
            self._model_identity = f"stale:{self._model_identity}"

    def display_pipeline(self, pipeline_cls: type[Any]) -> PipelineDisplay:
        self.bind_pipeline(pipeline_cls)
        disp = PipelineDisplay(pipeline_cls)
        self.remember("last_pipeline_display", disp)
        return disp

    def validate(self, pipeline_cls: type[Any] | None = None) -> DiagnosticsDisplay:
        from etlantic.authoring.lifecycle import validate_pipeline_like

        target = pipeline_cls or self._pipeline
        if target is None:
            raise ValueError("No pipeline bound")
        self.bind_pipeline(target)
        report = validate_pipeline_like(target, profile=self.profile)
        self.remember("last_validation", report)
        return DiagnosticsDisplay(report)

    def plan(self, pipeline_cls: type[Any] | None = None) -> PlanDisplay:
        from etlantic.authoring.lifecycle import plan_pipeline_like

        target = pipeline_cls or self._pipeline
        if target is None:
            raise ValueError("No pipeline bound")
        self.bind_pipeline(target)
        plan = plan_pipeline_like(target, profile=self.profile)
        self._plan = plan
        self._model_identity = _identity_fingerprint(target)
        self.remember("last_plan", plan)
        return PlanDisplay(plan, stale=False)

    def explain(self, pipeline_cls: type[Any] | None = None) -> dict[str, Any]:
        from etlantic.plan.explain import explain_plan

        display = self.plan(pipeline_cls)
        return explain_plan(display.plan)

    def run(self, pipeline_cls: type[Any] | None = None) -> ReportDisplay:
        from etlantic.runtime.execute import run_pipeline

        if self.cancel_requested:
            raise RuntimeError("Run cancelled")
        target = pipeline_cls or self._pipeline
        if target is None:
            raise ValueError("No pipeline bound")
        if self._plan is not None and self.stale:
            raise RuntimeError("Stale notebook definition detected; re-plan before run")
        self.bind_pipeline(target)
        request = RunRequest(selection=self.selection)
        report = run_pipeline(target, profile=self.profile, request=request)
        self._report = report
        self._model_identity = _identity_fingerprint(target)
        self.remember("last_report", report)
        return ReportDisplay(report, stale=False)

    def cancel(self) -> None:
        self.cancel_requested = True

    def compare_runs(
        self, left: PipelineRunReport, right: PipelineRunReport
    ) -> dict[str, Any]:
        return {
            "left": left.run_id,
            "right": right.run_id,
            "same_pipeline": getattr(left, "pipeline_id", None)
            == getattr(right, "pipeline_id", None),
            "left_status": str(left.status),
            "right_status": str(right.status),
        }

    def export_bundle(self) -> dict[str, Any]:
        """Deterministic export: code refs, non-secret config, plan hash."""
        profile = self.resolved_profile()
        return {
            "profile": profile.name,
            "security_mode": profile.security_mode,
            "selection": {
                "kind": self.selection.kind,
                "nodes": list(self.selection.nodes),
            },
            "plan_id": self._plan.plan_id if self._plan else None,
            "plan_fingerprint": self._plan.fingerprint if self._plan else None,
            "run_id": self._report.run_id if self._report else None,
            "stale": self.stale,
            "breakpoints": sorted(self.breakpoints),
            "artifact_keys": sorted(self.artifacts),
        }

    def extract_module_stub(self, module_name: str = "pipeline_module") -> str:
        """Scaffold notebook-to-project extraction (reviewable text only)."""
        name = getattr(self._pipeline, "__name__", "Pipeline")
        return (
            f'"""Extracted from notebook session — review before commit."""\n'
            f"from etlantic import Pipeline\n\n"
            f"# TODO: move Data/Transformation definitions here\n"
            f"class {name}(Pipeline):\n"
            f"    pass\n"
        )

    def optional_widgets(self) -> Any | None:
        """Return ipywidgets controls when ``etlantic[notebook]`` is installed."""
        try:
            import ipywidgets as widgets
        except ImportError:
            return None

        out = widgets.Output()

        def _on_validate(_: Any) -> None:
            with out:
                out.clear_output()
                print(self.validate())

        def _on_plan(_: Any) -> None:
            with out:
                out.clear_output()
                print(self.plan())

        def _on_run(_: Any) -> None:
            with out:
                out.clear_output()
                print(self.run())

        def _on_cancel(_: Any) -> None:
            self.cancel()
            with out:
                print("cancel requested")

        box = widgets.HBox(
            [
                widgets.Button(description="Validate"),
                widgets.Button(description="Plan"),
                widgets.Button(description="Run"),
                widgets.Button(description="Cancel"),
            ]
        )
        box.children[0].on_click(_on_validate)
        box.children[1].on_click(_on_plan)
        box.children[2].on_click(_on_run)
        box.children[3].on_click(_on_cancel)
        return widgets.VBox([box, out])

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.resolved_profile().name,
            "selection": {
                "kind": self.selection.kind,
                "nodes": list(self.selection.nodes),
                "start": self.selection.start,
                "end": self.selection.end,
            },
            "artifact_keys": sorted(self.artifacts),
            "stale": self.stale,
            "plan_fingerprint": self._plan.fingerprint if self._plan else None,
        }
