"""LSP conformance helpers and create_server smoke tests."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pygls")
pytest.importorskip("lsprotocol")

from etlantic_lsp import __version__, create_server
from etlantic_lsp.server import (
    CUSTOM_COMMAND,
    CUSTOM_GRAPH,
    CUSTOM_IMPACT,
    CUSTOM_PLAN,
    _completion_kind,
    _severity,
    _symbol_kind,
    _to_location,
)
from lsprotocol import types as lsp

from etlantic.ide.protocol import LocationLink


def test_package_version() -> None:
    assert __version__ == "0.44.0"


def test_create_server() -> None:
    server = create_server()
    assert server.name == "etlantic-lsp"
    assert server.workspace_index is None


def test_helpers() -> None:
    assert _severity("error") == lsp.DiagnosticSeverity.Error
    assert _symbol_kind("pipeline") == lsp.SymbolKind.Class
    assert _completion_kind("port") == lsp.CompletionItemKind.Field
    link = LocationLink(
        uri=str(Path("/tmp/x.py")),
        line=2,
        column=1,
    )
    loc = _to_location(link)
    assert loc.uri.startswith("file://")
    assert loc.range.start.line == 1


def test_custom_method_names() -> None:
    assert CUSTOM_GRAPH.startswith("etlantic/")
    assert CUSTOM_PLAN.startswith("etlantic/")
    assert CUSTOM_IMPACT.startswith("etlantic/")
    assert CUSTOM_COMMAND.startswith("etlantic/")


def test_server_indexes_workspace(tmp_path: Path) -> None:
    (tmp_path / "p.py").write_text(
        "from etlantic import Pipeline\nclass P(Pipeline):\n    pass\n",
        encoding="utf-8",
    )
    server = create_server()
    from etlantic.ide.analysis import WorkspaceIndex

    server.workspace_index = WorkspaceIndex(root=tmp_path)
    stats = server.workspace_index.refresh()
    assert stats["files"] >= 1
    assert any(s.name == "P" for s in server.workspace_index.symbols())
