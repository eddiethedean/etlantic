# Migration 0.43 → 0.44

> **Status: Available for ETLantic 0.44.0.** Upgrade notes for adopters moving
> from the published 0.43 CP-GA line to the published 0.44 developer-intelligence
> line.

## Summary

| Area | Change |
|---|---|
| Package pin | `etlantic==0.44.0` (do not mix 0.43 and 0.44 minors) |
| Plugin floor | `etlantic>=0.44.0,<0.45` |
| New optional package | `etlantic-lsp` language server (`etlantic[lsp]`) |
| New optional extra | `etlantic[notebook]` (IPython / ipywidgets) |
| New surface | `etlantic.ide` protocol + static analysis APIs |
| CP claim | Unchanged from 0.43 Supported isolation profiles |
| IDE schemas | Additive; existing command schema names remain |

## Upgrade steps

1. Complete adoption on **0.43.x** (CP-GA as needed).

2. Pin core and official plugins / Medallantic together:

   ```bash
   python -m pip install --upgrade 'etlantic==0.44.0'
   # plus matching plugins / medallantic at ==0.44.0
   ```

3. Optional language server:

   ```bash
   python -m pip install 'etlantic[lsp]==0.44.0'
   etlantic-lsp --help
   ```

4. Optional notebook displays:

   ```bash
   python -m pip install 'etlantic[notebook]==0.44.0'
   ```

5. Editors: install the VS Code reference extension from
   `editors/vscode` (see RELEASE_PROCESS) or point any LSP client at
   `etlantic-lsp`.

## Compatibility

- Control-plane wire schemas remain those of 0.43; 0.44 does not change CP-GA
  isolation claims.
- IDE command/result JSON schemas remain additive.
- Downgrade to 0.43 is supported with matching plugin minors; remove
  `etlantic-lsp` / notebook extras if unused.

## See also

- [What's New 0.44](../01_GETTING_STARTED/WHATS_NEW_0_44.md)
- [Exit gate 0.44](EXIT_GATE_0_44.md)
- [ADR-020](adr/ADR-020-DEVELOPER-INTELLIGENCE.md)
