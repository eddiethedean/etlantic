#!/usr/bin/env python3
"""Drift-check generated agent guidance against public CLI/SDK surfaces."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from etlantic.agents import (  # noqa: E402
    PUBLIC_CLI_COMMANDS,
    PUBLIC_SDK_IMPORTS,
    SECURITY_RULES,
    render_agents_md,
    render_claude_md,
    render_codex_skill_md,
    render_cursor_rule,
)


def main() -> int:
    text = render_agents_md()
    errors: list[str] = []
    for cmd in PUBLIC_CLI_COMMANDS:
        if f"etlantic {cmd}" not in text and f"`{cmd}`" not in text and cmd not in text:
            errors.append(f"missing CLI command in guidance: {cmd}")
    for imp in PUBLIC_SDK_IMPORTS:
        if imp not in text:
            errors.append(f"missing SDK import in guidance: {imp}")
    for rule in SECURITY_RULES:
        if rule.split(",")[0][:40] not in text and rule not in text:
            # allow shortened matches
            token = rule.split()[0]
            if token not in text:
                errors.append(f"missing security rule fragment: {rule[:60]}")

    # Ensure guidance mentions SARIF and allowlist.
    for required in ("SARIF", "plugin_allowlist", "source rows"):
        if required not in text:
            errors.append(f"missing required phrase: {required}")

    expected = {
        ROOT / "AGENTS.md": render_agents_md(),
        ROOT / "CLAUDE.md": render_claude_md(),
        ROOT / ".codex/skills/etlantic/SKILL.md": render_codex_skill_md(),
        ROOT / ".cursor/rules/etlantic.mdc": render_cursor_rule(),
    }
    for path, rendered in expected.items():
        if not path.exists():
            errors.append(f"missing on-disk guidance file: {path.relative_to(ROOT)}")
            continue
        on_disk = path.read_text(encoding="utf-8")
        if on_disk != rendered:
            errors.append(
                f"on-disk guidance drift: {path.relative_to(ROOT)} "
                '(run `uv run python -c "from etlantic.agents import '
                "generate_agent_guidance; generate_agent_guidance('.')\"`)"
            )

    # Codex skill should mention the full public CLI set.
    skill = render_codex_skill_md()
    for cmd in PUBLIC_CLI_COMMANDS:
        if cmd not in skill:
            errors.append(f"Codex skill missing CLI command: {cmd}")

    if errors:
        print("Agent guidance drift check FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("Agent guidance drift check OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
