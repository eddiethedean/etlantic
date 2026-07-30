#!/usr/bin/env python3
"""Ensure docs/10_REFERENCE/CLI.md mentions the live Typer CLI surface."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from typer.main import get_command

ROOT = Path(__file__).resolve().parents[1]
CLI_MD = ROOT / "docs/10_REFERENCE/CLI.md"

# Key nested commands that must appear explicitly in CLI.md (string presence).
REQUIRED_SUBCOMMANDS = (
    "report query",
    "viz dot",
    "viz html",
    "viz lineage",
)


def _collect_command_names(cmd: click.Command, prefix: str = "") -> set[str]:
    """Collect space-separated command paths from a Click/Typer command tree."""
    names: set[str] = set()
    # Typer may wrap Click; duck-type groups instead of isinstance(click.Group).
    if not hasattr(cmd, "list_commands") or not hasattr(cmd, "get_command"):
        return names
    ctx = click.Context(cmd)
    for name in cmd.list_commands(ctx):
        if name.startswith("_"):
            continue
        full = f"{prefix} {name}".strip() if prefix else name
        names.add(full)
        sub = cmd.get_command(ctx, name)
        if sub is not None:
            names |= _collect_command_names(sub, full)
    return names


def collect_cli_commands() -> set[str]:
    sys.path.insert(0, str(ROOT / "src"))
    from etlantic.cli import app

    return _collect_command_names(get_command(app))


def top_level_commands(all_names: set[str]) -> set[str]:
    return {name for name in all_names if " " not in name}


def main() -> int:
    if not CLI_MD.is_file():
        print(f"CLI docs check FAILED: missing {CLI_MD.relative_to(ROOT)}")
        return 1

    text = CLI_MD.read_text(encoding="utf-8")
    commands = collect_cli_commands()
    errors: list[str] = []

    for cmd in sorted(top_level_commands(commands)):
        # Prefer a section heading; fall back to any mention of the command token.
        heading = f"## `{cmd}`"
        mentioned = (
            heading in text or f"`{cmd}`" in text or f" {cmd}" in text or cmd in text
        )
        if not mentioned:
            errors.append(f"CLI.md missing top-level command: {cmd}")

    for required in REQUIRED_SUBCOMMANDS:
        # Simple string presence: bare "report query" or "`report query`".
        if required not in text and f"`{required}`" not in text:
            errors.append(f"CLI.md missing required subcommand mention: {required}")

    if errors:
        print("CLI docs check FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(
        f"CLI docs check OK "
        f"({len(top_level_commands(commands))} top-level, "
        f"{len(commands)} total commands collected)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
