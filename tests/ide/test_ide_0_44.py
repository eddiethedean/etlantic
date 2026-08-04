"""Tests for ETLantic 0.44 IDE protocol, analysis, trust, and SARIF locations."""

from __future__ import annotations

from pathlib import Path

import pytest

from etlantic.diagnostics import Diagnostic, Severity, SourceLocation
from etlantic.diagnostics.github import diagnostics_to_github_annotations
from etlantic.diagnostics.sarif import diagnostics_to_sarif
from etlantic.ide import (
    IdeCommand,
    TrustedWorkspacePolicy,
    execute_command,
    get_command_schema,
    list_commands,
)
from etlantic.ide.analysis import WorkspaceIndex, extract_symbols_from_source
from etlantic.ide.host import TrustedAnalysisHost
from etlantic.ide.protocol import DiagnosticPayload, LocationLink


def test_command_schemas_still_listed() -> None:
    assert "validate" in list_commands()
    assert get_command_schema("plan")["required"] == ["target"]


def test_sarif_prefers_source_location() -> None:
    payload = diagnostics_to_sarif(
        [
            Diagnostic(
                code="PMTEST001",
                severity=Severity.ERROR,
                message="boom",
                path=("pipeline", "step"),
                source=SourceLocation(path="src/pipe.py", line=12, column=4),
            )
        ]
    )
    loc = payload["runs"][0]["results"][0]["locations"][0]["physicalLocation"]
    assert loc["artifactLocation"]["uri"] == "src/pipe.py"
    assert loc["region"]["startLine"] == 12
    assert loc["region"]["startColumn"] == 4
    assert payload["runs"][0]["results"][0]["properties"]["logicalPath"] == [
        "pipeline",
        "step",
    ]


def test_github_annotation_uses_source_location() -> None:
    lines = diagnostics_to_github_annotations(
        [
            Diagnostic(
                code="PMTEST001",
                severity=Severity.ERROR,
                message="boom",
                source=SourceLocation(path="a.py", line=3, column=1),
            )
        ]
    )
    assert "file=a.py" in lines[0]
    assert "line=3" in lines[0]


def test_ast_extract_pipeline_symbols() -> None:
    source = """
from etlantic import Data, Pipeline, Extract, Load

class Row(Data):
    id: int

class Sample(Pipeline):
    raw: Extract[Row] = Extract(asset="rows")
"""
    symbols = extract_symbols_from_source(source)
    kinds = {s.kind for s in symbols}
    names = {s.name for s in symbols}
    assert "pipeline" in kinds
    assert "data" in kinds
    assert "Sample" in names
    assert "Row" in names


def test_workspace_index_python_file(tmp_path: Path) -> None:
    pipe = tmp_path / "pipe.py"
    pipe.write_text(
        "from etlantic import Data, Pipeline\n"
        "class Row(Data):\n"
        "    id: int\n"
        "class P(Pipeline):\n"
        "    pass\n",
        encoding="utf-8",
    )
    index = WorkspaceIndex(root=tmp_path)
    stats = index.refresh()
    assert stats["updated"] >= 1
    symbols = index.symbols("P")
    assert any(s.name == "P" for s in symbols)
    warm = index.refresh()
    assert warm["updated"] == 0


def test_execute_command_json_pipeline_no_trust(
    tmp_path: Path,
) -> None:
    del tmp_path
    # Assert PermissionError path on import target without trust.
    result = execute_command(
        IdeCommand(name="validate", arguments={"target": "missing.py:Foo"}),
        policy=TrustedWorkspacePolicy.disabled(),
    )
    assert result.ok is False
    assert result.error and "trusted" in result.error.lower()


def test_trusted_host_denies_outside_roots(tmp_path: Path) -> None:
    policy = TrustedWorkspacePolicy(
        enabled=True,
        allow_roots=(str(tmp_path / "allowed"),),
        allow_imports=True,
    )
    (tmp_path / "allowed").mkdir()
    host = TrustedAnalysisHost(policy)
    outside = tmp_path / "evil.py"
    outside.write_text("class X: pass\n", encoding="utf-8")
    with pytest.raises(PermissionError):
        host.load_target(f"{outside}:X")


def test_trusted_host_denies_secret_flags(tmp_path: Path) -> None:
    policy = TrustedWorkspacePolicy(
        enabled=True,
        allow_roots=(str(tmp_path),),
        allow_imports=True,
        allow_secret_resolution=True,
    )
    host = TrustedAnalysisHost(policy)
    target = tmp_path / "p.py"
    target.write_text("class P: pass\n", encoding="utf-8")
    with pytest.raises(PermissionError, match=r"secret|schema"):
        host.load_target(f"{target}:P")


def test_trusted_host_denies_dotted_module_outside_roots(tmp_path: Path) -> None:
    policy = TrustedWorkspacePolicy(
        enabled=True,
        allow_roots=(str(tmp_path / "allowed"),),
        allow_imports=True,
    )
    (tmp_path / "allowed").mkdir()
    host = TrustedAnalysisHost(policy)
    with pytest.raises(PermissionError, match=r"outside allow_roots|unresolved"):
        host.load_target("json:loads")


def test_trusted_host_execute_denies_secret_flags(tmp_path: Path) -> None:
    policy = TrustedWorkspacePolicy(
        enabled=True,
        allow_roots=(str(tmp_path),),
        allow_imports=True,
        allow_secret_resolution=True,
    )
    host = TrustedAnalysisHost(policy)
    pipe = tmp_path / "p.py"
    pipe.write_text("class P: pass\n", encoding="utf-8")
    result = host.execute(
        IdeCommand(name="validate", arguments={"target": f"{pipe}:P"})
    )
    assert result.ok is False
    assert result.error and "secret" in result.error.lower()


def test_trusted_host_execute_denies_json_outside_roots(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text(
        '{"schema": "etlantic.pipeline/1", "name": "x"}', encoding="utf-8"
    )
    policy = TrustedWorkspacePolicy(
        enabled=True,
        allow_roots=(str(allowed),),
        allow_imports=True,
    )
    host = TrustedAnalysisHost(policy)
    result = host.execute(
        IdeCommand(name="validate", arguments={"target": str(outside)})
    )
    assert result.ok is False
    assert result.error and "allow_roots" in result.error
    assert host.audit_log and host.audit_log[-1].allowed is False


def test_diagnostic_payload_roundtrip() -> None:
    payload = DiagnosticPayload(
        code="PMPIPE302",
        severity="error",
        message="missing binding",
        path=("pipeline", "raw"),
        location=LocationLink(uri="pipe.py", line=10, column=2),
        impact="downstream Load out will fail",
    )
    data = payload.to_dict()
    assert data["code"] == "PMPIPE302"
    assert data["location"]["line"] == 10
    assert data["impact"]


def test_rename_preview_no_unrelated(tmp_path: Path) -> None:
    pipe = tmp_path / "pipe.py"
    source = "from etlantic import Pipeline\nclass Alpha(Pipeline):\n    pass\n"
    pipe.write_text(source, encoding="utf-8")
    index = WorkspaceIndex(root=tmp_path)
    index.refresh()
    preview = index.rename_preview("Alpha", "Beta")
    assert preview["unrelated_rewrite_count"] == 0
    assert preview["requires_revalidation"] is True
    assert any(e["old"] == "Alpha" for e in preview["edits"])
    # Identifier column must point at Alpha, not the class keyword.
    edit = next(e for e in preview["edits"] if e["old"] == "Alpha")
    line = source.splitlines()[edit["line"] - 1]
    start = int(edit["column"])
    assert line[start : start + len("Alpha")] == "Alpha"


def test_pmid001_invalid_json(tmp_path: Path) -> None:
    bad = tmp_path / "broken.json"
    bad.write_text("{not-json", encoding="utf-8")
    index = WorkspaceIndex(root=tmp_path)
    index.refresh()
    codes = {d.code for d in index.diagnostics_for(bad)}
    assert "PMID001" in codes


def test_pmid002_invalid_pipeline_json(tmp_path: Path) -> None:
    bad = tmp_path / "pipe.json"
    bad.write_text(
        '{"$schema": "etlantic.pipeline/1", "kind": "pipeline", "name": "x"}',
        encoding="utf-8",
    )
    index = WorkspaceIndex(root=tmp_path)
    index.refresh()
    diags = index.diagnostics_for(bad)
    # Either structural validate diagnostics or PMID002 on loader failure.
    assert diags
    assert all("Failed to validate pipeline JSON:" not in d.message for d in diags)


def test_protocol_version_constant() -> None:
    from etlantic.ide.protocol import PROTOCOL_VERSION

    assert PROTOCOL_VERSION == "etlantic.ide/1"
