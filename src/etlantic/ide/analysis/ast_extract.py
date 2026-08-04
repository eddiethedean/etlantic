"""No-import AST extraction for Python pipeline sources (0.44)."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ExtractedSymbol:
    name: str
    kind: str
    line: int
    column: int
    end_line: int | None = None
    end_column: int | None = None
    bases: tuple[str, ...] = ()
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "line": self.line,
            "column": self.column,
            "end_line": self.end_line,
            "end_column": self.end_column,
            "bases": list(self.bases),
            "detail": self.detail,
        }


_PIPELINE_BASES = frozenset({"Pipeline", "etlantic.Pipeline"})
_DATA_BASES = frozenset({"Data", "etlantic.Data"})
_TRANSFORM_BASES = frozenset({"Transformation", "etlantic.Transformation"})


def _base_names(node: ast.ClassDef) -> tuple[str, ...]:
    names: list[str] = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            names.append(base.id)
        elif isinstance(base, ast.Attribute):
            parts: list[str] = []
            cur: ast.AST = base
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
            names.append(".".join(reversed(parts)))
    return tuple(names)


def _kind_for_bases(bases: tuple[str, ...]) -> str | None:
    simple = {b.split(".")[-1] for b in bases}
    base_set = set(bases)
    if simple & {"Pipeline"} or base_set & _PIPELINE_BASES:
        return "pipeline"
    if simple & {"Transformation"} or base_set & _TRANSFORM_BASES:
        return "transformation"
    if simple & {"Data"} or base_set & _DATA_BASES:
        return "data"
    return None


def _identifier_column(line_text: str, col_offset: int, name: str, keyword: str) -> int:
    """Return 0-based column of ``name`` after ``class``/``def``, not the keyword."""
    rest = line_text[col_offset:]
    match = re.match(rf"{keyword}\s+", rest)
    if match:
        return col_offset + match.end()
    idx = line_text.find(name, col_offset)
    return idx if idx >= 0 else col_offset


def extract_symbols_from_source(
    source: str,
    *,
    path: str | Path | None = None,
) -> list[ExtractedSymbol]:
    """Parse Python source without importing it; extract ETLantic class symbols."""
    del path
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    lines = source.splitlines()
    symbols: list[ExtractedSymbol] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = _base_names(node)
        kind = _kind_for_bases(bases)
        if kind is None:
            continue
        line_text = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
        name_col = _identifier_column(line_text, node.col_offset, node.name, "class")
        end_line = getattr(node, "end_lineno", None)
        symbols.append(
            ExtractedSymbol(
                name=node.name,
                kind=kind,
                line=node.lineno,
                column=name_col,
                end_line=end_line,
                end_column=name_col + len(node.name),
                bases=bases,
            )
        )
        # Extract simple annotated assignments as ports/bindings on pipelines
        if kind == "pipeline":
            for child in node.body:
                if isinstance(child, ast.AnnAssign) and isinstance(
                    child.target, ast.Name
                ):
                    symbols.append(
                        ExtractedSymbol(
                            name=child.target.id,
                            kind="port",
                            line=child.lineno,
                            column=child.target.col_offset,
                            end_line=getattr(child, "end_lineno", None),
                            end_column=child.target.col_offset + len(child.target.id),
                            detail=node.name,
                        )
                    )
                elif isinstance(child, ast.Assign):
                    for target in child.targets:
                        if isinstance(target, ast.Name):
                            symbols.append(
                                ExtractedSymbol(
                                    name=target.id,
                                    kind="binding",
                                    line=child.lineno,
                                    column=target.col_offset,
                                    end_line=getattr(child, "end_lineno", None),
                                    end_column=target.col_offset + len(target.id),
                                    detail=node.name,
                                )
                            )
    return symbols


def extract_symbols_from_path(path: str | Path) -> list[ExtractedSymbol]:
    text = Path(path).read_text(encoding="utf-8")
    return extract_symbols_from_source(text, path=path)
