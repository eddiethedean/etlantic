import * as path from "path";
import * as vscode from "vscode";
import {
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
  TransportKind,
} from "vscode-languageclient/node";

let client: LanguageClient | undefined;
const seenAttemptIds = new Set<string>();

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  const config = vscode.workspace.getConfiguration("etlantic");
  const lspPath = config.get<string>("lspPath") || "etlantic-lsp";
  const pythonPath = config.get<string>("pythonPath") || "";

  const serverOptions: ServerOptions = {
    run: {
      command: pythonPath ? pythonPath : lspPath,
      args: pythonPath ? ["-m", "etlantic_lsp"] : [],
      transport: TransportKind.stdio,
    },
    debug: {
      command: pythonPath ? pythonPath : lspPath,
      args: pythonPath ? ["-m", "etlantic_lsp"] : [],
      transport: TransportKind.stdio,
    },
  };

  const clientOptions: LanguageClientOptions = {
    documentSelector: [
      { scheme: "file", language: "python" },
      { scheme: "file", pattern: "**/*.json" },
    ],
    synchronize: {
      fileEvents: vscode.workspace.createFileSystemWatcher("**/*.{py,json}"),
    },
  };

  client = new LanguageClient("etlantic", "ETLantic Language Server", serverOptions, clientOptions);
  context.subscriptions.push(client);
  await client.start();

  context.subscriptions.push(
    vscode.commands.registerCommand("etlantic.validate", () => runIdeCommand("validate")),
    vscode.commands.registerCommand("etlantic.plan", () => runIdeCommand("plan")),
    vscode.commands.registerCommand("etlantic.explain", () => runIdeCommand("explain")),
    vscode.commands.registerCommand("etlantic.run", () => runIdeCommand("run_selected")),
    vscode.commands.registerCommand("etlantic.showGraph", showGraph),
    vscode.commands.registerCommand("etlantic.reconnectRun", reconnectRun),
    vscode.languages.registerCodeLensProvider(
      [{ language: "python" }, { pattern: "**/*.json" }],
      new EtlanticCodeLensProvider()
    )
  );

  const runView = new RunPanelProvider();
  vscode.window.registerTreeDataProvider("etlantic.runPanel", runView);
  vscode.window.registerTreeDataProvider("etlantic.previews", new PreviewPanelProvider());
}

export async function deactivate(): Promise<void> {
  if (client) {
    await client.stop();
  }
}

async function activeTarget(): Promise<string | undefined> {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    return undefined;
  }
  return editor.document.uri.fsPath;
}

async function runIdeCommand(name: string): Promise<void> {
  if (!client) {
    return;
  }
  const target = await activeTarget();
  if (!target) {
    vscode.window.showWarningMessage("Open a pipeline file first.");
    return;
  }
  const result = await client.sendRequest("etlantic/executeCommand", {
    name,
    arguments: { target, profile: "development" },
  });
  const channel = vscode.window.createOutputChannel("ETLantic");
  channel.appendLine(JSON.stringify(result, null, 2));
  channel.show(true);
  if (name === "plan" && result && (result as { payload?: { fingerprint?: string } }).payload) {
    const fingerprint = (result as { payload: { fingerprint: string } }).payload.fingerprint;
    vscode.window.showInformationMessage(`Plan fingerprint: ${fingerprint}`);
  }
}

async function showGraph(): Promise<void> {
  if (!client) {
    return;
  }
  const preview = await client.sendRequest("etlantic/graphPreview", {});
  const panel = vscode.window.createWebviewPanel(
    "etlanticGraph",
    "ETLantic Graph",
    vscode.ViewColumn.Beside,
    { enableScripts: false }
  );
  const mermaid =
    preview && (preview as { mermaid?: string }).mermaid
      ? String((preview as { mermaid: string }).mermaid)
      : "graph TD\n  A[No pipeline JSON indexed]";
  panel.webview.html = `<!DOCTYPE html><html><body>
    <h1>Pipeline graph</h1>
    <pre role="img" aria-label="Mermaid pipeline graph">${escapeHtml(mermaid)}</pre>
  </body></html>`;
}

async function reconnectRun(): Promise<void> {
  const config = vscode.workspace.getConfiguration("etlantic");
  const base = config.get<string>("controlPlaneBaseUrl") || "";
  if (!base) {
    vscode.window.showWarningMessage("Set etlantic.controlPlaneBaseUrl to reconnect.");
    return;
  }
  const runId = await vscode.window.showInputBox({ prompt: "Run / attempt id" });
  if (!runId) {
    return;
  }
  if (seenAttemptIds.has(runId)) {
    vscode.window.showInformationMessage("Already reconnected; refusing duplicate attempt.");
    return;
  }
  seenAttemptIds.add(runId);
  // Public CP surface only — host opens events URL; no local authz bypass.
  const url = `${base.replace(/\/$/, "")}/v1/runs/${encodeURIComponent(runId)}/events`;
  vscode.env.openExternal(vscode.Uri.parse(url));
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

class EtlanticCodeLensProvider implements vscode.CodeLensProvider {
  provideCodeLenses(document: vscode.TextDocument): vscode.CodeLens[] {
    const top = new vscode.Range(0, 0, 0, 0);
    return [
      new vscode.CodeLens(top, { title: "Validate", command: "etlantic.validate" }),
      new vscode.CodeLens(top, { title: "Plan", command: "etlantic.plan" }),
      new vscode.CodeLens(top, { title: "Explain", command: "etlantic.explain" }),
      new vscode.CodeLens(top, { title: "Run", command: "etlantic.run" }),
      new vscode.CodeLens(top, { title: "Graph", command: "etlantic.showGraph" }),
    ];
  }
}

class RunPanelProvider implements vscode.TreeDataProvider<vscode.TreeItem> {
  getTreeItem(element: vscode.TreeItem): vscode.TreeItem {
    return element;
  }
  getChildren(): vscode.TreeItem[] {
    return [
      new vscode.TreeItem("Local runs use IdeCommand → public SDK"),
      new vscode.TreeItem("Reconnect via control-plane events (no duplicate attempts)"),
    ];
  }
}

class PreviewPanelProvider implements vscode.TreeDataProvider<vscode.TreeItem> {
  getTreeItem(element: vscode.TreeItem): vscode.TreeItem {
    return element;
  }
  getChildren(): vscode.TreeItem[] {
    return [
      new vscode.TreeItem("Graph / lineage / plan / impact previews"),
      new vscode.TreeItem("Objective / erasure metadata previews (no subject values)"),
    ];
  }
}

// Keep path import referenced for packaging clarity.
void path;
