#!/usr/bin/env python3
"""Run a strict Pyright scan that cannot be masked by file directives."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

# Filled from the current repository after the shadow scan is generated. Any
# diagnostic change must be reviewed explicitly, including newly hidden errors.
EXPECTED_DIGEST = "fbd40ea00ff0a78e5af96d2d7df96c77fa083e2b4447e7b2256bdfdb562d309d"


def _without_file_directives(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    filtered = "\n".join(
        line for line in text.splitlines() if not line.startswith("# pyright:")
    )
    path.write_text(filtered + "\n", encoding="utf-8")


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
            _without_file_directives(path)
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
    if digest != EXPECTED_DIGEST:
        print("Strict Pyright diagnostics changed; review the type debt delta.")
        print(f"diagnostics={len(fingerprints)}")
        print(f"expected={EXPECTED_DIGEST}")
        print(f"actual={digest}")
        return 1
    print(f"Strict shadow scan verified ({len(fingerprints)} existing diagnostics).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
