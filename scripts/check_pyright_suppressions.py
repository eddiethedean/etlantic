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
# the same review. AC056-020 action-scope checks shifted later source lines;
# prior AC056-019/044/031/015 work shifted other positions. AC056-021's
# validation imports and branches shift locations again. Phase 0.56 adds two
# reviewed file-scoped exceptions: FastAPI route decorators appear unused to
# Pyright's module scan, and the same-engine schedule adapter coordinates a
# transaction through the durable adapter's internal snapshot API.
# The private-usage exception was removed after exposing the SQLModel durable
# adapter's same-transaction operation as a public coordination method. The
# managed preparation service, managed resume command, route and authorization
# matrix shift existing directives; token review found no additions or removals.
# AC #215 persists the accepted execution scope on CP3 submissions and carries
# it through report recovery and artifact retention. AC #226 enumerates full
# accepted scopes through the durable provider contract. Source lines shifted,
# with no suppression added or removed; the 784-entry inventory is re-pinned.
# AC #227 paginates retention scope discovery and centralizes accepted-context
# reconstruction. No suppression was added or removed; the 784-entry inventory
# is re-pinned after source-line shifts.
EXPECTED_DIGEST = "e76413443b413c05e957b486df6283fbdb670bef21758b1caea559e4b732281a"

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
