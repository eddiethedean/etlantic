"""pygls language server wrapping etlantic.ide analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lsprotocol import types as lsp
from pygls.server import LanguageServer

from etlantic.ide.analysis import WorkspaceIndex
from etlantic.ide.commands import execute_command
from etlantic.ide.protocol import IdeCommand
from etlantic.ide.trust import TrustedWorkspacePolicy
from etlantic_lsp._version import __version__

CUSTOM_GRAPH = "etlantic/graphPreview"
CUSTOM_PLAN = "etlantic/planPreview"
CUSTOM_IMPACT = "etlantic/impactPreview"
CUSTOM_COMMAND = "etlantic/executeCommand"


class EtlanticLanguageServer(LanguageServer):
    """LSP host for ETLantic workspace analysis."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.workspace_index: WorkspaceIndex | None = None
        self.policy = TrustedWorkspacePolicy.disabled()
        self.trusted_imports = False

    def configure_trust(
        self,
        *,
        trusted_imports: bool,
        allow_roots: tuple[str, ...] | list[str],
    ) -> None:
        self.trusted_imports = trusted_imports
        roots = tuple(str(r) for r in allow_roots if r)
        if trusted_imports and roots:
            self.policy = TrustedWorkspacePolicy(
                enabled=True,
                allow_roots=roots,
                allow_imports=True,
            )
        else:
            self.policy = TrustedWorkspacePolicy.disabled()


def _workspace_roots(params: lsp.InitializeParams) -> list[str]:
    roots: list[str] = []
    for folder in params.workspace_folders or []:
        uri = getattr(folder, "uri", None) or ""
        if uri.startswith("file://"):
            roots.append(uri[len("file://") :])
    if not roots and params.root_uri and params.root_uri.startswith("file://"):
        roots.append(params.root_uri[len("file://") :])
    if not roots and params.root_path:
        roots.append(str(params.root_path))
    return roots


def _init_options(params: lsp.InitializeParams) -> dict[str, Any]:
    options = params.initialization_options
    return dict(options) if isinstance(options, dict) else {}


def create_server() -> EtlanticLanguageServer:
    server = EtlanticLanguageServer("etlantic-lsp", __version__)

    @server.feature(lsp.INITIALIZE)
    def initialize(params: lsp.InitializeParams) -> None:  # type: ignore[misc]
        roots = _workspace_roots(params)
        root = Path(roots[0]) if roots else None
        if root is not None:
            server.workspace_index = WorkspaceIndex(root=root)
            server.workspace_index.refresh()
        options = _init_options(params)
        server.configure_trust(
            trusted_imports=bool(options.get("trustedImports", False)),
            allow_roots=roots,
        )

    @server.feature(lsp.WORKSPACE_DID_CHANGE_CONFIGURATION)
    def on_config_change(params: lsp.DidChangeConfigurationParams) -> None:  # type: ignore[misc]
        settings = params.settings
        payload = settings if isinstance(settings, dict) else {}
        etlantic = payload.get("etlantic") if isinstance(payload, dict) else {}
        if not isinstance(etlantic, dict):
            etlantic = {}
        roots: list[str] = []
        if server.workspace_index is not None:
            roots = [str(server.workspace_index.root)]
        server.configure_trust(
            trusted_imports=bool(etlantic.get("trustedImports", False)),
            allow_roots=roots,
        )

    @server.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
    @server.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
    @server.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
    def refresh_doc(params: Any) -> None:  # type: ignore[misc]
        _refresh_and_publish(server, getattr(params, "text_document", None))

    @server.feature(lsp.TEXT_DOCUMENT_COMPLETION)
    def completions(params: lsp.CompletionParams) -> lsp.CompletionList:  # type: ignore[misc]
        index = server.workspace_index
        items: list[lsp.CompletionItem] = []
        if index is not None:
            for sym in index.symbols():
                items.append(
                    lsp.CompletionItem(
                        label=sym.name,
                        kind=_completion_kind(sym.kind),
                        detail=sym.kind,
                        documentation=sym.detail,
                    )
                )
        # Always offer common ETLantic keywords
        for label in (
            "Pipeline",
            "Data",
            "Transformation",
            "Extract",
            "Load",
            "Input",
            "Output",
            "Parameter",
        ):
            items.append(
                lsp.CompletionItem(label=label, kind=lsp.CompletionItemKind.Class)
            )
        return lsp.CompletionList(is_incomplete=False, items=items)

    @server.feature(lsp.TEXT_DOCUMENT_HOVER)
    def hover(params: lsp.HoverParams) -> lsp.Hover | None:  # type: ignore[misc]
        index = server.workspace_index
        if index is None:
            return None
        word = _word_at(server, params)
        if not word:
            return None
        matches = [s for s in index.symbols(word) if s.name == word]
        if not matches:
            return None
        sym = matches[0]
        return lsp.Hover(
            contents=lsp.MarkupContent(
                kind=lsp.MarkupKind.Markdown,
                value=f"**{sym.name}** (`{sym.kind}`)\n\n{sym.detail or ''}",
            )
        )

    @server.feature(lsp.TEXT_DOCUMENT_DEFINITION)
    def definition(params: lsp.DefinitionParams) -> list[lsp.Location]:  # type: ignore[misc]
        index = server.workspace_index
        if index is None:
            return []
        word = _word_at(server, params)
        if not word:
            return []
        return [_to_location(link) for link in index.find_definition(word)]

    @server.feature(lsp.TEXT_DOCUMENT_REFERENCES)
    def references(params: lsp.ReferenceParams) -> list[lsp.Location]:  # type: ignore[misc]
        index = server.workspace_index
        if index is None:
            return []
        word = _word_at(server, params)
        if not word:
            return []
        return [_to_location(link) for link in index.find_references(word)]

    @server.feature(lsp.TEXT_DOCUMENT_DOCUMENT_SYMBOL)
    def document_symbols(  # type: ignore[misc]
        params: lsp.DocumentSymbolParams,
    ) -> list[lsp.DocumentSymbol]:
        index = server.workspace_index
        if index is None:
            return []
        uri = params.text_document.uri
        path = uri.replace("file://", "")
        symbols: list[lsp.DocumentSymbol] = []
        for sym in index.symbols():
            if sym.location.uri != path and not path.endswith(sym.location.uri):
                continue
            line = (sym.location.line or 1) - 1
            col = sym.location.column or 0
            end_line = (sym.location.end_line or sym.location.line or 1) - 1
            end_col = sym.location.end_column or col + len(sym.name)
            symbols.append(
                lsp.DocumentSymbol(
                    name=sym.name,
                    kind=_symbol_kind(sym.kind),
                    range=lsp.Range(
                        start=lsp.Position(line=max(line, 0), character=max(col, 0)),
                        end=lsp.Position(
                            line=max(end_line, 0), character=max(end_col, 0)
                        ),
                    ),
                    selection_range=lsp.Range(
                        start=lsp.Position(line=max(line, 0), character=max(col, 0)),
                        end=lsp.Position(
                            line=max(line, 0), character=max(col, 0) + len(sym.name)
                        ),
                    ),
                )
            )
        return symbols

    @server.feature(lsp.WORKSPACE_SYMBOL)
    def workspace_symbols(  # type: ignore[misc]
        params: lsp.WorkspaceSymbolParams,
    ) -> list[lsp.SymbolInformation]:
        index = server.workspace_index
        if index is None:
            return []
        out: list[lsp.SymbolInformation] = []
        for sym in index.symbols(params.query or None):
            out.append(
                lsp.SymbolInformation(
                    name=sym.name,
                    kind=_symbol_kind(sym.kind),
                    location=_to_location(sym.location),
                )
            )
        return out

    @server.feature(lsp.TEXT_DOCUMENT_RENAME)
    def rename(params: lsp.RenameParams) -> lsp.WorkspaceEdit | None:  # type: ignore[misc]
        index = server.workspace_index
        if index is None:
            return None
        word = _word_at(server, params)
        if not word:
            return None
        preview = index.rename_preview(word, params.new_name)
        changes: dict[str, list[lsp.TextEdit]] = {}
        for edit in preview["edits"]:
            uri = f"file://{edit['uri']}"
            line = max(int(edit["line"]) - 1, 0)
            col = max(int(edit["column"]), 0)
            text_edit = lsp.TextEdit(
                range=lsp.Range(
                    start=lsp.Position(line=line, character=col),
                    end=lsp.Position(line=line, character=col + len(word)),
                ),
                new_text=params.new_name,
            )
            changes.setdefault(uri, []).append(text_edit)
        return lsp.WorkspaceEdit(changes=changes)

    @server.feature(lsp.TEXT_DOCUMENT_CODE_ACTION)
    def code_actions(params: lsp.CodeActionParams) -> list[lsp.CodeAction]:  # type: ignore[misc]
        actions: list[lsp.CodeAction] = []
        for diagnostic in params.context.diagnostics:
            data = diagnostic.data if isinstance(diagnostic.data, dict) else {}
            for action in data.get("actions", []) or []:
                actions.append(
                    lsp.CodeAction(
                        title=str(action.get("title") or action.get("kind") or "Fix"),
                        kind=lsp.CodeActionKind.QuickFix,
                        diagnostics=[diagnostic],
                        edit=None,
                        command=lsp.Command(
                            title=str(action.get("title") or "review"),
                            command="etlantic.reviewAction",
                            arguments=[action],
                        ),
                    )
                )
        return actions

    @server.feature(CUSTOM_GRAPH)
    def graph_preview(params: dict[str, Any]) -> dict[str, Any]:  # type: ignore[misc]
        index = server.workspace_index
        if index is None:
            return {}
        preview = index.graph_preview(params.get("pipeline_name"))
        return preview.to_dict() if preview else {}

    @server.feature(CUSTOM_PLAN)
    def plan_preview(params: dict[str, Any]) -> dict[str, Any]:  # type: ignore[misc]
        index = server.workspace_index
        if index is None:
            return {}
        path = params.get("path")
        if not path:
            return {}
        preview = index.plan_preview(path)
        return preview.to_dict() if preview else {}

    @server.feature(CUSTOM_IMPACT)
    def impact_preview(params: dict[str, Any]) -> dict[str, Any]:  # type: ignore[misc]
        index = server.workspace_index
        if index is None:
            return {}
        origin = str(params.get("origin") or "")
        return index.impact_preview(origin).to_dict()

    @server.feature(CUSTOM_COMMAND)
    def run_ide_command(params: dict[str, Any]) -> dict[str, Any]:  # type: ignore[misc]
        command = IdeCommand(
            name=str(params.get("name")),
            arguments=dict(params.get("arguments") or {}),
        )
        return execute_command(command, policy=server.policy).to_dict()

    return server


def _refresh_and_publish(server: EtlanticLanguageServer, text_document: Any) -> None:
    if server.workspace_index is None:
        return
    path = None
    if text_document is not None and getattr(text_document, "uri", None):
        path = Path(text_document.uri.replace("file://", ""))
        server.workspace_index.refresh(paths=[path])
    else:
        server.workspace_index.refresh()
    if path is None:
        return
    diagnostics = server.workspace_index.diagnostics_for(path)
    lsp_diags: list[lsp.Diagnostic] = []
    for d in diagnostics:
        line = (d.location.line - 1) if d.location and d.location.line else 0
        col = d.location.column if d.location and d.location.column else 0
        lsp_diags.append(
            lsp.Diagnostic(
                range=lsp.Range(
                    start=lsp.Position(line=max(line, 0), character=max(col, 0)),
                    end=lsp.Position(line=max(line, 0), character=max(col, 0) + 1),
                ),
                message=d.message,
                severity=_severity(d.severity),
                code=d.code,
                source="etlantic",
                data={"actions": list(d.actions), "impact": d.impact},
            )
        )
    server.publish_diagnostics(text_document.uri, lsp_diags)


def _word_at(server: EtlanticLanguageServer, params: Any) -> str | None:
    try:
        doc = server.workspace.get_text_document(params.text_document.uri)
        return doc.word_at_position(params.position)
    except Exception:
        return None


def _to_location(link: Any) -> lsp.Location:
    line = max((link.line or 1) - 1, 0)
    col = max(link.column or 0, 0)
    end_line = max((link.end_line or link.line or 1) - 1, 0)
    end_col = max(link.end_column or col + 1, 0)
    uri = link.uri if str(link.uri).startswith("file:") else f"file://{link.uri}"
    return lsp.Location(
        uri=uri,
        range=lsp.Range(
            start=lsp.Position(line=line, character=col),
            end=lsp.Position(line=end_line, character=end_col),
        ),
    )


def _severity(value: str) -> lsp.DiagnosticSeverity:
    return {
        "error": lsp.DiagnosticSeverity.Error,
        "warning": lsp.DiagnosticSeverity.Warning,
        "info": lsp.DiagnosticSeverity.Information,
        "hint": lsp.DiagnosticSeverity.Hint,
    }.get(value, lsp.DiagnosticSeverity.Information)


def _symbol_kind(kind: str) -> lsp.SymbolKind:
    return {
        "pipeline": lsp.SymbolKind.Class,
        "transformation": lsp.SymbolKind.Class,
        "data": lsp.SymbolKind.Struct,
        "port": lsp.SymbolKind.Field,
        "binding": lsp.SymbolKind.Variable,
        "contract": lsp.SymbolKind.File,
    }.get(kind, lsp.SymbolKind.Object)


def _completion_kind(kind: str) -> lsp.CompletionItemKind:
    return {
        "pipeline": lsp.CompletionItemKind.Class,
        "transformation": lsp.CompletionItemKind.Class,
        "data": lsp.CompletionItemKind.Struct,
        "port": lsp.CompletionItemKind.Field,
        "binding": lsp.CompletionItemKind.Variable,
    }.get(kind, lsp.CompletionItemKind.Text)


def run_stdio() -> None:
    server = create_server()
    server.start_io()
