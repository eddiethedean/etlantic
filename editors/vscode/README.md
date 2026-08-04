# ETLantic VS Code extension (reference client)

Version **0.44.0** (lockstep with ETLantic developer intelligence).

## Develop

```bash
cd editors/vscode
npm install
npm run compile
```

Press F5 in VS Code to launch an Extension Development Host. Ensure
`etlantic-lsp` is on `PATH` or set `etlantic.pythonPath` /
`etlantic.lspPath`.

## Package

```bash
npm run package
```

Produces an `.vsix` for local install. This extension is **Experimental**;
other editors should use `etlantic-lsp` directly.

## Accessibility

- Graph webview uses a `<pre role="img">` with an accessible label.
- Commands are keyboard-reachable via the Command Palette.
- No color-only status indicators in the reference panels.
