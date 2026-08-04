"""Incremental workspace symbol and diagnostic index (0.44)."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from etlantic.ide.analysis.ast_extract import (
    ExtractedSymbol,
    extract_symbols_from_source,
)
from etlantic.ide.analysis.discovery import WorkspaceDiscovery
from etlantic.ide.protocol import (
    DiagnosticPayload,
    GraphPreview,
    ImpactPreview,
    LocationLink,
    PlanPreview,
    SymbolPayload,
)
from etlantic.ide.trust import TrustedWorkspacePolicy


@dataclass
class IndexedFile:
    path: Path
    content_hash: str
    mtime_ns: int
    symbols: list[ExtractedSymbol] = field(default_factory=list)
    kind: str = "unknown"  # python | pipeline_json | contract | other
    diagnostics: list[DiagnosticPayload] = field(default_factory=list)
    pipeline_name: str | None = None
    pipeline_id: str | None = None


@dataclass
class WorkspaceIndex:
    """Incremental no-import workspace index."""

    root: Path
    policy: TrustedWorkspacePolicy = field(
        default_factory=TrustedWorkspacePolicy.disabled
    )
    max_memory_bytes: int = 256 * 1024 * 1024
    _files: dict[str, IndexedFile] = field(default_factory=dict)
    _cancelled: bool = False
    last_cold_ms: float | None = None
    last_warm_ms: float | None = None

    def cancel(self) -> None:
        self._cancelled = True

    def reset_cancel(self) -> None:
        self._cancelled = False

    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _estimate_memory(self) -> int:
        # Rough estimate: path + hash + symbols
        total = 0
        for item in self._files.values():
            total += 256 + len(item.symbols) * 128
        return total

    def refresh(self, *, paths: list[Path] | None = None) -> dict[str, Any]:
        """Refresh index for all discovered files or a subset."""
        self.reset_cancel()
        started = time.perf_counter()
        discovery = WorkspaceDiscovery(self.root)
        targets = paths if paths is not None else discovery.iter_source_files()
        updated = 0
        removed = 0
        seen: set[str] = set()
        for path in targets:
            if self._cancelled:
                break
            if self._estimate_memory() > self.max_memory_bytes:
                break
            key = str(path.resolve())
            seen.add(key)
            try:
                stat = path.stat()
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            content_hash = self._hash_text(text)
            existing = self._files.get(key)
            if (
                existing is not None
                and existing.content_hash == content_hash
                and existing.mtime_ns == stat.st_mtime_ns
            ):
                continue
            indexed = self._index_file(path, text, content_hash, stat.st_mtime_ns)
            self._files[key] = indexed
            updated += 1
        if paths is None:
            for key in list(self._files):
                if key not in seen:
                    del self._files[key]
                    removed += 1
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if paths is None and not self._files:
            self.last_cold_ms = elapsed_ms
        elif updated == 0:
            self.last_warm_ms = elapsed_ms
        else:
            if self.last_cold_ms is None:
                self.last_cold_ms = elapsed_ms
            else:
                self.last_warm_ms = elapsed_ms
        return {
            "updated": updated,
            "removed": removed,
            "files": len(self._files),
            "elapsed_ms": elapsed_ms,
            "cancelled": self._cancelled,
            "memory_estimate_bytes": self._estimate_memory(),
        }

    def _index_file(
        self, path: Path, text: str, content_hash: str, mtime_ns: int
    ) -> IndexedFile:
        suffix = path.suffix.lower()
        symbols: list[ExtractedSymbol] = []
        diagnostics: list[DiagnosticPayload] = []
        kind = "other"
        pipeline_name = None
        pipeline_id = None
        if suffix == ".py":
            kind = "python"
            symbols = extract_symbols_from_source(text, path=path)
        elif suffix == ".json":
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                kind = "other"
                diagnostics.append(
                    DiagnosticPayload(
                        code="PMID001",
                        severity="error",
                        message=f"Invalid JSON: {exc.msg}",
                        location=LocationLink(
                            uri=str(path), line=exc.lineno, column=exc.colno
                        ),
                    )
                )
            else:
                if not isinstance(data, dict):
                    kind = "other"
                else:
                    schema = data.get("$schema") or data.get("schema")
                    if (
                        schema == "etlantic.pipeline/1"
                        or data.get("kind") == "pipeline"
                    ):
                        kind = "pipeline_json"
                        pipeline_name = data.get("name") or data.get("pipeline_name")
                        pipeline_id = data.get("pipeline_id") or data.get("id")
                        if pipeline_name:
                            symbols.append(
                                ExtractedSymbol(
                                    name=str(pipeline_name),
                                    kind="pipeline",
                                    line=1,
                                    column=0,
                                    detail="json",
                                )
                            )
                        diagnostics.extend(self._validate_pipeline_json(path, data))
                    elif "odcs" in str(schema).lower() or data.get("apiVersion"):
                        kind = "contract"
                        name = data.get("name") or path.stem
                        symbols.append(
                            ExtractedSymbol(
                                name=str(name), kind="contract", line=1, column=0
                            )
                        )
        return IndexedFile(
            path=path,
            content_hash=content_hash,
            mtime_ns=mtime_ns,
            symbols=symbols,
            kind=kind,
            diagnostics=diagnostics,
            pipeline_name=str(pipeline_name) if pipeline_name else None,
            pipeline_id=str(pipeline_id) if pipeline_id else None,
        )

    def _validate_pipeline_json(
        self, path: Path, data: dict[str, Any]
    ) -> list[DiagnosticPayload]:
        try:
            from etlantic.authoring.preview import structural_validate_preview
            from etlantic.authoring.serialize import read_pipeline_json

            # Re-read via official loader for schema fidelity
            defn = read_pipeline_json(path)
            report = structural_validate_preview(defn, profile="development")
            out: list[DiagnosticPayload] = []
            for diagnostic in report.diagnostics:
                payload = DiagnosticPayload.from_diagnostic(diagnostic)
                if payload.location is None:
                    payload = DiagnosticPayload(
                        code=payload.code,
                        severity=payload.severity,
                        message=payload.message,
                        path=payload.path,
                        location=LocationLink(uri=str(path), line=1, column=0),
                        help=payload.help,
                        phase=payload.phase,
                        actions=payload.actions,
                        impact=payload.impact,
                    )
                out.append(payload)
            return out
        except Exception as exc:
            exc_type = type(exc).__name__
            return [
                DiagnosticPayload(
                    code="PMID002",
                    severity="error",
                    message=f"Failed to validate pipeline JSON ({exc_type})",
                    location=LocationLink(uri=str(path), line=1, column=0),
                )
            ]

    def symbols(self, query: str | None = None) -> list[SymbolPayload]:
        q = (query or "").lower()
        results: list[SymbolPayload] = []
        for indexed in self._files.values():
            for sym in indexed.symbols:
                if q and q not in sym.name.lower():
                    continue
                results.append(
                    SymbolPayload(
                        name=sym.name,
                        kind=sym.kind,
                        location=LocationLink(
                            uri=str(indexed.path),
                            line=sym.line,
                            column=sym.column,
                            end_line=sym.end_line,
                            end_column=sym.end_column,
                            symbol=sym.name,
                            kind=sym.kind,
                        ),
                        container=sym.detail,
                        detail=sym.kind,
                    )
                )
        return results

    def diagnostics_for(
        self, path: str | Path | None = None
    ) -> list[DiagnosticPayload]:
        if path is None:
            out: list[DiagnosticPayload] = []
            for indexed in self._files.values():
                out.extend(indexed.diagnostics)
            return out
        key = str(Path(path).resolve())
        indexed = self._files.get(key)
        return list(indexed.diagnostics) if indexed else []

    def find_definition(self, name: str) -> list[LocationLink]:
        return [s.location for s in self.symbols(name) if s.name == name]

    def find_references(self, name: str) -> list[LocationLink]:
        refs: list[LocationLink] = []
        for indexed in self._files.values():
            for sym in indexed.symbols:
                if sym.name == name or sym.detail == name:
                    refs.append(
                        LocationLink(
                            uri=str(indexed.path),
                            line=sym.line,
                            column=sym.column,
                            symbol=sym.name,
                            kind=sym.kind,
                        )
                    )
        return refs

    def rename_preview(self, old_name: str, new_name: str) -> dict[str, Any]:
        """Build a reviewable workspace edit preview (does not write files)."""
        edits: list[dict[str, Any]] = []
        for indexed in self._files.values():
            if indexed.kind not in {"python", "pipeline_json"}:
                continue
            try:
                text = indexed.path.read_text(encoding="utf-8")
            except OSError:
                continue
            if old_name not in text:
                continue
            # Conservative: only rename exact symbol occurrences already indexed
            for sym in indexed.symbols:
                if sym.name != old_name:
                    continue
                edits.append(
                    {
                        "uri": str(indexed.path),
                        "line": sym.line,
                        "column": sym.column,
                        "old": old_name,
                        "new": new_name,
                        "kind": sym.kind,
                    }
                )
        return {
            "edits": edits,
            "unrelated_rewrite_count": 0,
            "requires_revalidation": True,
        }

    def graph_preview(self, pipeline_name: str | None = None) -> GraphPreview | None:
        from etlantic.mermaid import graph_to_mermaid
        from etlantic.viz import logical_graph_to_ir

        for indexed in self._files.values():
            if indexed.kind != "pipeline_json":
                continue
            if pipeline_name and indexed.pipeline_name != pipeline_name:
                continue
            try:
                from etlantic.authoring.lifecycle import inspect_pipeline_like
                from etlantic.authoring.serialize import read_pipeline_json

                defn = read_pipeline_json(indexed.path)
                graph = inspect_pipeline_like(defn)
                ir = logical_graph_to_ir(graph).to_dict()
                return GraphPreview(
                    pipeline_id=indexed.pipeline_id
                    or indexed.pipeline_name
                    or "unknown",
                    pipeline_name=indexed.pipeline_name or indexed.path.stem,
                    nodes=tuple(ir.get("nodes", [])),
                    edges=tuple(ir.get("edges", [])),
                    layout_key=indexed.content_hash[:16],
                    mermaid=graph_to_mermaid(graph),
                )
            except Exception:
                continue
        return None

    def plan_preview(self, path: str | Path) -> PlanPreview | None:
        from etlantic.authoring.preview import plan_preview as authoring_plan_preview
        from etlantic.authoring.serialize import read_pipeline_json

        defn = read_pipeline_json(Path(path))
        plan, report = authoring_plan_preview(defn, profile="development")
        if plan is None:
            return None
        del report
        return PlanPreview(
            plan_id=plan.plan_id,
            fingerprint=plan.fingerprint,
            profile_name=plan.profile_name,
            node_count=len(plan.logical_graph.nodes),
        )

    def impact_preview(self, origin: str) -> ImpactPreview:
        """Downstream impact: symbols that reference ``origin`` plus diagnostics."""
        affected = [
            {"name": s.name, "kind": s.kind, "uri": s.location.uri}
            for s in self.symbols()
            if s.container == origin or s.name == origin
        ]
        diags = [
            d
            for d in self.diagnostics_for()
            if origin in d.message or origin in "/".join(d.path)
        ]
        return ImpactPreview(
            origin=origin,
            affected=tuple(affected),
            diagnostics=tuple(diags),
            summary=f"{len(affected)} related symbols; {len(diags)} diagnostics",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "files": len(self._files),
            "symbols": len(self.symbols()),
            "last_cold_ms": self.last_cold_ms,
            "last_warm_ms": self.last_warm_ms,
            "memory_estimate_bytes": self._estimate_memory(),
            "policy": self.policy.to_dict(),
        }
