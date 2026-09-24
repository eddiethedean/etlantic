#!/usr/bin/env python3
"""Run a strict Pyright scan that cannot be masked by suppressions."""

from __future__ import annotations

import hashlib
import io
import json
import platform
import shutil
import subprocess
import tempfile
import tokenize
from pathlib import Path
from typing import Any

# Filled from the current repository after the shadow scan is generated. Any
# diagnostic change must be reviewed explicitly, including newly hidden errors.
EXPECTED_DIGESTS = {
    # Pyright's import/type surface differs by host platform because the
    # synchronized dependency set includes platform-specific distributions.
    "Darwin": "087a70a1897f9edf112c91100a7e2a153860127b2ef0ff484df0b835b309d1b5",
    "Linux": "a6f8bfc6a7cfc3ecba92e1182bc5e39f0d000f2b26fca7b47834e94502b173ba",
}


def _is_suppression(comment: str) -> bool:
    stripped = comment.lstrip()
    return stripped.startswith("# pyright:") or stripped.startswith("# type: ignore")


def _without_suppressions(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    tokens = tokenize.generate_tokens(io.StringIO(text).readline)
    for token in tokens:
        if token.type != tokenize.COMMENT or not _is_suppression(token.string):
            continue
        start_line, start_column = token.start
        end_line, end_column = token.end
        if start_line != end_line:
            continue
        line = lines[start_line - 1]
        lines[start_line - 1] = (
            line[:start_column] + " " * (end_column - start_column) + line[end_column:]
        )
    path.write_text("".join(lines), encoding="utf-8")


def _diagnostic_fingerprints(payload: dict[str, Any], root: Path) -> tuple[str, ...]:
    resolved_root = root.resolve()
    fingerprints: list[str] = []
    for diagnostic in payload.get("generalDiagnostics", []):
        path = Path(str(diagnostic["file"])).resolve().relative_to(resolved_root)
        start = diagnostic["range"]["start"]
        fingerprints.append(
            json.dumps(
                [
                    path.as_posix(),
                    int(start["line"]),
                    int(start["character"]),
                    str(diagnostic.get("rule") or ""),
                    str(diagnostic.get("message") or ""),
                ],
                ensure_ascii=True,
                separators=(",", ":"),
            )
        )
    return tuple(sorted(fingerprints))


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    pyright = shutil.which("pyright")
    if pyright is None:
        print("Pyright executable is unavailable")
        return 1

    with tempfile.TemporaryDirectory(prefix="etlantic-pyright-") as directory:
        shadow = Path(directory) / "repo"
        shutil.copytree(
            root,
            shadow,
            ignore=shutil.ignore_patterns(
                ".git",
                ".venv",
                "__pycache__",
                ".mypy_cache",
                ".pytest_cache",
            ),
        )
        for path in shadow.rglob("*.py"):
            _without_suppressions(path)
        result = subprocess.run(
            [pyright, "--outputjson", "--project", str(shadow / "pyproject.toml")],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )

    if result.returncode not in {0, 1}:
        print(result.stderr.strip() or "Pyright shadow scan failed")
        return 1
    if not result.stdout.strip():
        print(result.stderr.strip() or "Pyright produced no JSON output")
        return 1
    payload = json.loads(result.stdout)
    fingerprints = _diagnostic_fingerprints(payload, shadow)
    digest = hashlib.sha256("\n".join(fingerprints).encode()).hexdigest()
    system = platform.system()
    expected_digest = EXPECTED_DIGESTS.get(system)
    if expected_digest is None:
        print(f"Strict Pyright baseline is unavailable for platform {system!r}.")
        return 1
    if digest != expected_digest:
        print("Strict Pyright diagnostics changed; review the type debt delta.")
        print(f"diagnostics={len(fingerprints)}")
        print(f"expected={expected_digest}")
        print(f"actual={digest}")
        return 1
    print(f"Strict shadow scan verified ({len(fingerprints)} existing diagnostics).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
