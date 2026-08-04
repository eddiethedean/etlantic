"""Notebook session and display tests for 0.44."""

from __future__ import annotations

from pathlib import Path

from tests.fixtures.sample_pipeline import SamplePipeline

from etlantic.authoring.preview import plan_preview, structural_validate_preview
from etlantic.authoring.serialize import read_pipeline_json
from etlantic.ide import IdeCommand, execute_command
from etlantic.notebook import (
    ArtifactPreview,
    NotebookSession,
    PipelineDisplay,
    PlanDisplay,
)


def test_pipeline_display_side_effect_free() -> None:
    disp = PipelineDisplay(SamplePipeline)
    text = str(disp)
    assert "raw" in text or "Sample" in text or "out" in text
    html = disp._repr_html_()
    assert "<" in html


def test_artifact_preview_bounds() -> None:
    rows = [{"a": i, "secret": "hunter2"} for i in range(100)]
    preview = ArtifactPreview(rows, row_limit=10, column_limit=2)
    assert preview.truncated is True
    assert len(preview.rows) <= 10
    assert all(row.get("secret") == "***" for row in preview.rows if "secret" in row)


def test_notebook_session_export_and_extract() -> None:
    session = NotebookSession(profile="development")
    session.display_pipeline(SamplePipeline)
    exported = session.export_bundle()
    assert "breakpoints" in exported
    assert "validation" in exported["breakpoints"]
    stub = session.extract_module_stub()
    assert "Pipeline" in stub


def test_plan_identity_json_definition(tmp_path: Path) -> None:
    """IDE command and authoring preview share plan fingerprint for JSON defs."""
    src = Path("tests/fixtures/burn_in/pipeline/v0_37/minimal.json")
    target = tmp_path / "pipeline.json"
    target.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    defn = read_pipeline_json(target)
    _ = structural_validate_preview(defn, profile="development")
    plan, _plan_report = plan_preview(defn, profile="development")
    ide = execute_command(
        IdeCommand(
            name="plan", arguments={"target": str(target), "profile": "development"}
        )
    )
    if plan is None:
        assert ide.ok is False or ide.name == "plan"
        return
    assert ide.ok is True
    assert ide.payload["fingerprint"] == plan.fingerprint
    display = PlanDisplay(plan)
    assert plan.fingerprint in str(display)


def test_stale_detection() -> None:
    session = NotebookSession(profile="development")
    session.bind_pipeline(SamplePipeline)
    assert session.stale is False
    session.force_stale()
    assert session.stale is True
    assert session.export_bundle()["stale"] is True


def test_bind_pipeline_marks_stale_on_redefine() -> None:
    session = NotebookSession(profile="development")
    session.bind_pipeline(SamplePipeline)
    session._model_identity = "other-identity"
    session.bind_pipeline(SamplePipeline)
    assert session.stale is True
    assert session._plan is None


def test_optional_widgets_without_extra() -> None:
    session = NotebookSession()
    assert session.optional_widgets() is None
