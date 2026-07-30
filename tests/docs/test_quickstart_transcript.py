"""Report metadata and Quickstart transcript must stay warning-clean."""

from __future__ import annotations

import subprocess
import sys
import warnings
from pathlib import Path

from etlantic.reports.model import PipelineRunReport
from etlantic.runtime import RunStatus


def test_local_run_report_reload_has_no_metadata_namespace_warning(
    tmp_path: Path,
) -> None:
    """Persisted local orchestrator reports must reload without UserWarning."""
    from examples.memory_customers import CustomerPipeline

    report = CustomerPipeline.run(profile="development")
    assert report.status is RunStatus.SUCCEEDED
    payload = report.to_dict()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        PipelineRunReport.from_dict(payload)
    namespace_warnings = [
        w
        for w in caught
        if issubclass(w.category, UserWarning)
        and "extension namespaces" in str(w.message)
    ]
    assert not namespace_warnings, [str(w.message) for w in namespace_warnings]


def test_quickstart_intentional_failure_stderr_is_clean(tmp_path: Path) -> None:
    """Quickstart aha path: PMPIPE210 without report.metadata UserWarning."""
    project = tmp_path / "qs"
    project.mkdir()
    pipeline = project / "pipeline.py"
    pipeline.write_text(
        """\
from etlantic import Data, Extract, Input, Load, Output, Pipeline, Transformation

class Row(Data):
    id: int
    name: str

class Other(Data):
    id: int
    name: str

class Identity(Transformation):
    rows: Input[Row]
    result: Output[Row]

@Identity.implementation("python")
def identity(rows):
    return list(rows)

class SamplePipeline(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
    step = Identity.step(rows=raw)
    out: Load[Other] = Load(input=step.result, asset="out")
""",
        encoding="utf-8",
    )
    (project / "data").mkdir()
    (project / "data" / "rows.json").write_text(
        '[{"id": 1, "name": "Ada"}, {"id": 2, "name": "Grace"}]\n',
        encoding="utf-8",
    )
    # Seed a successful report first (the warning path), then validate broken wiring.
    good = project / "good_pipeline.py"
    good.write_text(
        pipeline.read_text(encoding="utf-8").replace("Load[Other]", "Load[Row]"),
        encoding="utf-8",
    )
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "etlantic",
            "run",
            "good_pipeline.py:SamplePipeline",
            "--profile",
            "development",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    bad = subprocess.run(
        [
            sys.executable,
            "-m",
            "etlantic",
            "validate",
            "pipeline.py:SamplePipeline",
            "--profile",
            "development",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    assert bad.returncode != 0
    combined = (bad.stdout or "") + (bad.stderr or "")
    assert "PMPIPE210" in combined
    assert "extension namespaces" not in combined
    assert "UserWarning" not in combined or "extension namespaces" not in combined
