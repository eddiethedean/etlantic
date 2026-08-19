# Human-governed AI

> **Status: Available in ETLantic 0.48.0.** Budget ~15 minutes after
> [Quickstart](QUICKSTART.md). PyPI only — no MCP extra and no clone.

Treat every proposal as untrusted. This tutorial **validates** a proposal; it
does not apply files, submit runs, or call `/v1/approvals*`.

## 1. Start from the init project

Reuse the Quickstart directory. Confirm the sample still validates:

```bash
python -m etlantic validate pipeline.py:SamplePipeline --profile development
```

## 2. Assemble a context bundle

```bash
python -m etlantic context bundle pipeline.py:SamplePipeline --profile development --format json
```

Expected: JSON with `"schema": "etlantic.context_bundle/1"` and `"ok": true`.
The bundle is redacted (no secret values, no source rows). Overflow or
redaction failures emit `PMCTX*` and a non-zero exit.

## 3. Generate agent instruction files

```bash
python -m etlantic generate --kind agents
```

Expected: `AGENTS.md`, `.codex/skills/etlantic/SKILL.md`, `CLAUDE.md`, and a
Cursor rule under `.cursor/`. Marked user regions are preserved. Replacing
unmarked files requires `--overwrite`.

## 4. Validate a read-only proposal

Write `proposal.json` (inspect/validate only — never `run.submit`):

```json
{
  "schema": "etlantic.proposal/1",
  "task_id": "scaffold_model",
  "kind": "files",
  "files": [
    {
      "path": "notes.md",
      "content": "# Review notes\nNo execution.\n"
    }
  ],
  "requested_actions": ["inspect", "validate"]
}
```

```bash
python -m etlantic proposal validate proposal.json --target pipeline.py:SamplePipeline --format json
```

Expected: `"ok": true` and `"applied": false`. Apply stays a current 0.42
approval on the control plane. The CLI never writes the proposed files.

## 5. See fail-closed behavior

Change `requested_actions` to `["run.submit"]` and re-run validate. Expected:
non-zero exit and `PMPROP*` (`untrusted` / forbidden action).

## What this is not

- Experimental `etlantic-mcp` is optional and fake-first — skip it here.
- Write MCP tools, vendor AI SDKs, and autonomous submit are out of 0.48.
- See [What's new in 0.48](WHATS_NEW_0_48.md) and
  [Agents API](../10_REFERENCE/API_AGENTS.md).
