#!/usr/bin/env python3
"""Build the MkDocs site with strict validation and no Material advisory noise."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_MKDOCS_COMMANDS = frozenset({"build", "serve", "gh-deploy", "get-deps", "new", "help"})


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if not args or args[0] not in _MKDOCS_COMMANDS:
        args = ["build", "--strict", *args]
    elif args[0] == "build" and "--strict" not in args:
        args = ["build", "--strict", *args[1:]]

    env = os.environ.copy()
    # Suppress Material for MkDocs advisory about unreleased MkDocs 2.0.
    env.setdefault("NO_MKDOCS_2_WARNING", "1")
    return subprocess.call(
        [sys.executable, "-m", "mkdocs", *args],
        cwd=ROOT,
        env=env,
    )


if __name__ == "__main__":
    raise SystemExit(main())
