#!/usr/bin/env python3
"""Keep repository-wide Pyright exceptions explicit and reviewable."""

from __future__ import annotations

import hashlib
import io
import tokenize
from pathlib import Path

# Pyright/type-ignore comments are temporary compatibility boundaries. Locking
# their exact inventory prevents a new suppression from silently widening the
# strict-checking escape hatch; intentional changes must update this digest in
# the same review.
EXPECTED_DIGEST = "728ac8d7129d39c50f75a74d5851679f0d89fd1145986706136c6b398d62c0d4"

_IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "dist",
        "build",
        "site",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        "__pycache__",
    }
)


def _is_suppression(comment: str) -> bool:
    stripped = comment.lstrip()
    return stripped.startswith("# pyright:") or stripped.startswith("# type: ignore")


def _inventory(root: Path) -> tuple[str, ...]:
    inventory: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if _IGNORED_DIRECTORIES.intersection(path.relative_to(root).parts):
            continue
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        try:
            tokens = tokenize.generate_tokens(io.StringIO(source).readline)
            for token in tokens:
                if token.type != tokenize.COMMENT or not _is_suppression(token.string):
                    continue
                line_number = token.start[0]
                inventory.append(
                    f"{path.relative_to(root).as_posix()}:{line_number}:"
                    f"{lines[line_number - 1]}"
                )
        except tokenize.TokenError:
            # Pyright will report malformed Python separately; preserve any
            # suppressions tokenized before the syntax error for this gate.
            continue
    return tuple(sorted(inventory))


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    inventory = _inventory(root)
    payload = "\n".join(inventory).encode()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != EXPECTED_DIGEST:
        print(
            "Pyright suppression inventory changed. Review the "
            "suppressions and update EXPECTED_DIGEST intentionally."
        )
        print(f"expected={EXPECTED_DIGEST}")
        print(f"actual={digest}")
        return 1
    print(f"Pyright suppression inventory verified ({len(inventory)} entries).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
