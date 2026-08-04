"""Agent guidance generators (AGENTS.md, CLAUDE.md, Codex SKILL, Cursor rules)."""

from __future__ import annotations

import textwrap
from pathlib import Path

PUBLIC_CLI_COMMANDS = (
    "init",
    "doctor",
    "validate",
    "inspect",
    "plan",
    "profile",
    "run",
    "compile",
    "generate",
    "diff",
    "plugin",
    "schema",
    "reliability",
    "erasure",
    "viz",
    "report",
    "watch",
)

PUBLIC_SDK_IMPORTS = (
    "etlantic.dataframe",
    "etlantic.sql",
    "etlantic.spark",
    "etlantic.orchestration",
    "etlantic.viz",
    "etlantic.secrets",
    "etlantic.testing",
    "etlantic.quality",
    "etlantic.connectors",
    "etlantic.control_plane",
)

SECURITY_RULES = (
    "Never embed secret values in plans, reports, contracts, or agent guidance.",
    "Production profiles require Profile.plugin_allowlist and fail closed.",
    "Schema history stores fingerprints/metadata only — never source rows.",
    "Prefer public SDK imports; do not rely on private underscore modules.",
    "Medallion bronze/silver/gold stay in SparkForge / medallantic — never in core.",
)


def render_agents_md() -> str:
    cmds = ", ".join(f"`etlantic {c}`" for c in PUBLIC_CLI_COMMANDS)
    imports = textwrap.fill(
        "Also supported: " + ", ".join(f"`{i}`" for i in PUBLIC_SDK_IMPORTS),
        width=80,
        break_long_words=False,
        break_on_hyphens=False,
    )
    rules = "\n".join(f"- {r}" for r in SECURITY_RULES)
    return f"""# AGENTS.md — ETLantic

## Purpose

Guide coding agents working in ETLantic projects. Prefer public CLI and SDK
surfaces; fail closed on secrets, plugin trust, and schema mutations.

## Public CLI

{cmds}

## Public SDK imports

Recommended: `import etlantic as etl` (curated root + lazy namespaces).

{imports}

## FastAPI dual surface

- **CP1 control plane:** `ETLanticAPI` / `include_router` / `create_app`
  (durable accept, authz, `/health` + `/ready`)
- **Non-CP reference:** `create_reference_app` (thin authoring demo only)
- Continuous directory watchers are **not** in core; use optional submitters
  (for example `etlantic_fastapi.landing_sensor`)

## Security

{rules}

## Workflows

1. Validate before generate/compile: `etlantic validate TARGET --format json`
2. Plan deterministically: `etlantic plan TARGET --format json`
3. Compile only from a valid plan (requires `etlantic-airflow` for `--target airflow`):
   `etlantic compile TARGET --target airflow -o dags/`
4. Emit CI diagnostics as SARIF: `etlantic validate TARGET --format sarif`
5. Use `etlantic.testing` conformance suites for third-party plugins
6. Diagrams: `Pipeline.to_mermaid()` or `etlantic.viz` / `etlantic viz`
"""


def render_claude_md() -> str:
    return (
        "# CLAUDE.md — ETLantic\n\n"
        + render_agents_md().split("\n", 1)[1]
        + "\n## Claude-specific notes\n\n"
        "- Prefer editing contracts/pipelines over inventing backend-specific DAGs.\n"
        "- When unsure, run `etlantic plan explain` and attach JSON output.\n"
    )


def render_codex_skill_md() -> str:
    return """---
name: etlantic
description: Validate, plan, compile, and generate ETLantic pipelines safely.
---

# ETLantic skill

Use public CLI commands (`init`, `doctor`, `validate`, `inspect`, `plan`,
`profile`, `run`, `compile`, `generate`, `diff`, `plugin`, `schema`,
`reliability`, `erasure`, `viz`, `report`, `watch`) and
prefer `import etlantic as etl` (curated root + lazy namespaces) or
public SDK imports (`etlantic.dataframe`, `.sql`, `.spark`, `.orchestration`,
`.viz`, `.secrets`, `.testing`, `.quality`, `.connectors`, `.control_plane`).

For FastAPI, use `ETLanticAPI` / `include_router` / `create_app` for the CP1
control plane. `create_reference_app` is only a thin, non-CP authoring demo.
Continuous landing-zone directory watchers are optional submitters, never core
behavior. `etlantic watch` is read-only static revalidation (no execution).

Never write secret values into plans or reports. Production profiles require
`plugin_allowlist`. Schema observe/acknowledge must not store source rows.
Medallion bronze/silver/gold stay in SparkForge / medallantic — never
in core. Airflow compile needs the optional `etlantic-airflow` package.
"""


def render_cursor_rule() -> str:
    return """---
description: ETLantic public API and security guardrails
globs:
  - "**/*.py"
---

# ETLantic

- Prefer `import etlantic as etl`; also use public imports: dataframe, sql, spark, orchestration, viz, secrets, testing, quality, connectors, control_plane.
- CLI: validate → plan → compile/generate; prefer `--format json` or `sarif` in CI.
- Airflow compile requires optional `etlantic-airflow`.
- FastAPI CP1 uses `ETLanticAPI` / `include_router` / `create_app`; `create_reference_app` is a thin non-CP demo, and watchers remain optional submitters.
- Fail closed: secrets, production plugin allowlists, schema history without rows.
- Medallion bronze/silver/gold stay in SparkForge / medallantic — never in core.
- Do not redesign orchestration protocols; wrap existing `compile_plan` / plugins.
"""


def generate_agent_guidance(
    root: str | Path, *, overwrite: bool = True
) -> dict[str, Path]:
    """Write agent guidance files under ``root``."""
    base = Path(root)
    base.mkdir(parents=True, exist_ok=True)
    mapping = {
        "AGENTS.md": render_agents_md(),
        "CLAUDE.md": render_claude_md(),
        ".codex/skills/etlantic/SKILL.md": render_codex_skill_md(),
        ".cursor/rules/etlantic.mdc": render_cursor_rule(),
    }
    written: dict[str, Path] = {}
    for rel, content in mapping.items():
        path = base / rel
        if path.exists() and not overwrite:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            content if content.endswith("\n") else content + "\n", encoding="utf-8"
        )
        written[rel] = path
    return written
