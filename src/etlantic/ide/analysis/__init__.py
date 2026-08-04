"""Static workspace analysis package (0.44)."""

from __future__ import annotations

from etlantic.ide.analysis.ast_extract import (
    ExtractedSymbol,
    extract_symbols_from_path,
    extract_symbols_from_source,
)
from etlantic.ide.analysis.discovery import ProjectRoot, WorkspaceDiscovery
from etlantic.ide.analysis.index import IndexedFile, WorkspaceIndex

__all__ = [
    "ExtractedSymbol",
    "IndexedFile",
    "ProjectRoot",
    "WorkspaceDiscovery",
    "WorkspaceIndex",
    "extract_symbols_from_path",
    "extract_symbols_from_source",
]
