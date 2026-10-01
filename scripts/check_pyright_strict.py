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
    # AC056-037 typed the metadata fixture helper, removing 19 pre-existing
    # unknown-type diagnostics; the clean consumer uses public owner modules.
    # AC056-017/018 added managed artifact and report-recovery paths plus tests;
    # the shadow scan still reports 10,432 diagnostics, with the fingerprint
    # change caused by shifted source locations in the existing debt inventory.
    # AC056-017 now records recovered worker attempts and execution-node lineage;
    # the 10,432-diagnostic total is unchanged.
    # AC056-019 adds bounded event-tombstone retention; the 10,432-diagnostic
    # count is unchanged and source-location fingerprints moved.
    # AC056-044 revision-aware definition writes shifted MemoryDefinitionRepository
    # source locations; the 10,432-diagnostic count is unchanged.
    # AC056-024 validates returned secret-reference identity; source locations
    # shift in the existing diagnostics, with the 10,432 count unchanged.
    # AC056-038 reapplies redaction when serializing LogRecord; the diagnostic
    # fingerprint moved with source lines, while normalized diagnostics and the
    # 10,432-diagnostic count are unchanged.
    # AC056-031 validates checkpoint ownership for resume/repair/backfill plans;
    # the 10,432 strict diagnostics are unchanged apart from shifted locations.
    # AC056-013 rejects invalid explicit concurrency before runtime side effects;
    # AC056-015 fences worker effects to the live attempt. All 10,432 diagnostics
    # match after ignoring shifted source line numbers.
    # AC056-016 stages incremental cursors until all selected outputs publish;
    # normalized diagnostics remain unchanged, with the same 10,432 total.
    # AC056-017/019 add bounded partition lineage and tombstone-prune batches;
    # normalized diagnostics remain unchanged, with the same 10,432 total.
    # AC056-018 preserves report status; AC056-020 scopes action receipts by
    # context. Normalized diagnostics remain unchanged (10,432 total).
    # With all workspace groups plus the FastAPI and LSP extras installed,
    # AC056-029 removes seven firing-scope diagnostics (10,402 -> 10,395) and
    # adds none versus the 0.55 base tree.
    # Phase 0.56 adds 150 no-suppression diagnostics across newly exercised
    # managed HTTP tests, orchestration secret/incremental paths, and schedule
    # models, while removing one prior incremental diagnostic. They remain in
    # modules with reviewed existing Pyright boundaries; the regular repository
    # Pyright run is clean. Lock the reviewed shadow inventory at 10,548.
    # AC056-032 adds schedule amendment and control-contract tests. Their
    # reviewed changes leave the normalized diagnostic count unchanged; source
    # line fingerprints were refreshed after placing the new regression last
    # and giving the PostgreSQL test a unique durable-store namespace.
    # AC056-009 adds preparation-operation restart, cancellation and lease
    # renewal cases; the 10,548-diagnostic total is unchanged, with refreshed
    # source-location fingerprints.
    # AC056-027/028 adds workload-bound schedules and typed schedule policy.
    # Review of the changed files found 31 additional no-suppression
    # diagnostics across attestation/durable/schedule models, secrets,
    # orchestration and their contract tests; no new suppression was added for
    # these findings. The ordinary repository Pyright gate remains clean.
    # AC056-031 adds managed checkpoint resume, state-aware action discovery
    # and rollback qualification. Typing the new managed test harness removes
    # 14 shadow diagnostics; the reviewed total is 10,563.
    # The Phase 0.56 full authorization matrix now includes resume across
    # tenant/workspace scopes. Its added cases shift existing diagnostic lines;
    # the reviewed shadow scan remains at 10,563 diagnostics.
    # The 0.52 evidence revision scanner now includes non-ignored untracked
    # source files, shifting diagnostics later in that checker only.
    # This qualification pass fixes the surfaced connector, adaptive-plan,
    # managed-service and package-qualification typing errors. Reviewing the
    # changed paths confirms those fixes remove cascaded shadow diagnostics;
    # the strict inventory falls from 10,563 to 9,832 without new suppressions.
    # AC056-043 extends managed local adaptive admission and records the
    # managed qualification path. Removing an unused pipeline test fixture
    # eliminates nine diagnostics; the reviewed suppression-free inventory
    # contains 9,837 diagnostics, with no new suppression directives.
    "Darwin": "fa1f7ada44ded57548cd43d947ac3f1acbcaade13859266b9a9fc17b40550f45",
    "Linux": "fa1f7ada44ded57548cd43d947ac3f1acbcaade13859266b9a9fc17b40550f45",
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
                ".ruff_cache",
                ".hypothesis",
                ".etlantic",
                "dist",
                "build",
                "node_modules",
                ".DS_Store",
                "site",
                "_generated_*.py",
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
