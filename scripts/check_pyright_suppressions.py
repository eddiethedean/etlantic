#!/usr/bin/env python3
"""Keep repository-wide Pyright exceptions explicit and reviewable."""

from __future__ import annotations

import hashlib
import io
import tokenize
from pathlib import Path

# Pyright/type-ignore comments are temporary compatibility boundaries. Locking
# their exact inventory prevents a new suppression from silently widening the
# strict-checking escape hatch. Paths and directive text are pinned; line
# numbers are omitted for file-level settings so unrelated edits do not require
# re-pinning the gate. Inline ignores retain their line because their location
# determines which diagnostic they suppress.
# AC056-020 action-scope checks shifted later source lines;
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
# AC #230 bounds paginated scope scans with a high watermark so a full retry
# queue cannot stall discovery. No suppression was added or removed; the
# inventory is re-pinned after source-line shifts.
# Issue #217 preserves unknown effects through recovery and store snapshots.
# No suppression changed; the 784-entry inventory is re-pinned after line shifts.
# Issue #219 retains fenced late action effects; existing suppression locations
# shift, with no directives added or removed (784 entries).
# Phase 0.56 #221/222 update control-plane and SQLModel sources, shifting
# existing suppression locations without adding or removing directives.
# Managed checkpoint persistence shifts existing runtime/service directives;
# the reviewed 789-entry inventory is re-pinned with no suppression changes.
# Issue #243 completes principal-scoped idempotency. No suppression was added
# or removed; the 784-entry inventory is re-pinned after source-line shifts.
# Merged phase 0.56 quota durability adds five reviewed SQLModel snapshot
# adapter suppressions: one for the ORM-generated table attribute and four for
# restoring private MemoryQuotaProvider state as part of the durable snapshot.
# The 789-entry inventory is pinned after those additions and line shifts.
# AC056-031 effect classification and managed recovery changes shifted existing
# directives. Token review found no suppressions added or removed; re-pin the
# 789-entry inventory.
# AC056 removes the legacy profile migration and opt-in loading paths. The
# 789-entry suppression inventory is unchanged, with refreshed source lines.
# Phase 0.57 extracts schedule route handlers and adds backend/service/provider
# surfaces. The existing route-decorator suppression remains; no directives
# were added or removed. Re-pin the 789-entry inventory after source shifts.
# Prefect test isolation shifts an existing inline ignore; no directives were
# added or removed. Inline ignore locations are now part of the inventory, so
# re-pin the unchanged 789-entry 0.58.0 baseline after source shifts.
# Phase 0.58 adds six reviewed boundaries: Prefect's dynamic scheduler surface,
# typed fixtures for the managed contract suite, and test-only backend method
# injection plus structural dispatcher doubles. A newly added async-result
# ignore was replaced with an explicit Awaitable cast. Re-pin the 795-entry
# inventory after reviewing those changes.
# The test backend now lives in a separately buildable wheel fixture; its
# reviewed method-assignment exception moved with the package.
# Direct scheduler hardening replaces a narrow legacy ignore with a reviewed
# Prefect dynamic-API boundary, and the managed contract fixtures add their
# file-scoped/test-backend boundaries. The reviewed inventory is 794 entries.
# The phase 0.58 dispatch-reconciliation authorization guard and its CP1 matrix
# coverage shift existing inline ignores without adding or removing directives.
# Dispatcher lifecycle registration and the disposal-race regression move the
# existing Prefect test fixture ignore; the reviewed 794-entry inventory is
# unchanged.
# Dispatcher diagnostics and FastAPI route-pin coverage shift existing inline
# fixture ignores. A redundant structural-test ignore was replaced with a cast;
# the reviewed inventory remains 794 entries and is re-pinned here.
# Direct scheduler test annotations add one import line above an existing inline
# ignore. No suppression was added or removed; re-pin the shifted 794-entry list.
# Targeted cancellation reconciliation and its regression shift five existing
# inline ignores across the durable store and phase 0.58 tests; none changed.
# Phase 0.58 snapshot and canceled-dispatch persistence tests seed internal
# durable records directly, so each adds one file-scoped private-usage boundary.
EXPECTED_DIGEST = "f878c63f818c7c5830f9ccb8cc5d9de71d59e1777bdb2c279ca450119948af4c"

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


def suppression_inventory(root: Path) -> tuple[str, ...]:
    """Return suppression tokens, pinning locations for inline ignores."""
    inventory: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if _IGNORED_DIRECTORIES.intersection(path.relative_to(root).parts):
            continue
        source = path.read_text(encoding="utf-8")
        try:
            tokens = tokenize.generate_tokens(io.StringIO(source).readline)
            for token in tokens:
                if token.type != tokenize.COMMENT or not _is_suppression(token.string):
                    continue
                relative_path = path.relative_to(root).as_posix()
                directive = token.string
                inline = directive.lstrip().startswith(
                    ("# type: ignore", "# pyright: ignore")
                )
                location = f":{token.start[0]}" if inline else ""
                inventory.append(f"{relative_path}{location}:{directive}")
        except tokenize.TokenError:
            # Pyright will report malformed Python separately; preserve any
            # suppressions tokenized before the syntax error for this gate.
            continue
    return tuple(sorted(inventory))


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    inventory = suppression_inventory(root)
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
