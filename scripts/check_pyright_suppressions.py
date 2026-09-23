#!/usr/bin/env python3
"""Keep repository-wide Pyright exceptions explicit and reviewable."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

# File-level exceptions are temporary compatibility boundaries.  Locking their
# exact inventory prevents a new blanket suppression from silently widening the
# strict-checking escape hatch; intentional changes must update this digest in
# the same review.
EXPECTED_DIGEST = "03fe9a3af281ba12c85cce3e181cb3e6e08d2d9e64a99669d5b83768c4092554"


def _inventory(root: Path) -> tuple[str, ...]:
    result = subprocess.run(
        ["rg", "-n", "^# pyright:", "--glob", "*.py"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return tuple(sorted(line for line in result.stdout.splitlines() if line))


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    inventory = _inventory(root)
    payload = "\n".join(inventory).encode()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != EXPECTED_DIGEST:
        print(
            "Pyright file-level exception inventory changed. Review the "
            "suppressions and update EXPECTED_DIGEST intentionally."
        )
        print(f"expected={EXPECTED_DIGEST}")
        print(f"actual={digest}")
        return 1
    print(
        f"Pyright file-level exception inventory verified ({len(inventory)} entries)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
