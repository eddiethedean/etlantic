#!/usr/bin/env python3
"""Synchronize lockstep package versions and their current-facing references.

Preview with ``--dry-run`` before applying. Applying updates tracked version
surfaces, refreshes ``uv.lock`` and plugin manifest digests, and verifies the
digests. It does not decide release publication state or regenerate
version-derived fixtures; review those after the command. See
``docs/11_DEVELOPMENT/RELEASE_PROCESS.md#version-bump-workflow``.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILES = (
    Path("src/etlantic/_version.py"),
    Path("pyproject.toml"),
)
EXCLUDED_PARTS = {".git", ".venv", "build", "dist", "site", "__pycache__"}


def read_version() -> str:
    text = (ROOT / VERSION_FILES[0]).read_text(encoding="utf-8")
    match = re.search(r'^__version__ = "([^\"]+)"$', text, re.MULTILINE)
    if not match:
        raise SystemExit("Could not read src/etlantic/_version.py")
    return match.group(1)


def tracked_paths() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
    )
    return [ROOT / name.decode() for name in result.stdout.split(b"\0") if name]


def is_version_surface(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    parts = relative.parts
    if EXCLUDED_PARTS.intersection(parts):
        return False
    # These are dated release records. Their version references are historical
    # evidence and must not be rewritten by a later release; live current_minor
    # frontmatter is synchronized separately below.
    if parts[:2] == ("docs", "11_DEVELOPMENT") and (
        ("evidence" in parts and path.name != "README.md")
        or "IMPLEMENTATION_REPORT" in path.name
    ):
        return False
    if path.name == "uv.lock":
        return False  # regenerated with uv lock after the metadata edits
    if relative.as_posix() in {"CHANGELOG.md", "docs/CHANGELOG.md"}:
        return False  # changelog history and publication wording need context
    return path.suffix in {".py", ".toml", ".json", ".md", ".yml", ".yaml"}


def replace_current_minor_markers(text: str, old: str, new: str) -> str:
    if old != new:
        # Dependency policy is an open minor-line floor, never a patch pin.
        text = re.sub(
            rf'(?m)^(current_minor:\s*)"{re.escape(old)}"',
            rf'\g<1>"{new}"',
            text,
        )
        text = text.replace(f"**Current {old} boundary:", f"**Current {new} boundary:")
    return text


def replace_version(text: str, old: str, new: str) -> str:
    old_minor = ".".join(old.split(".")[:2])
    new_minor = ".".join(new.split(".")[:2])
    version_pattern = re.compile(
        rf"(?<![A-Za-z0-9])(?P<prefix>v?){re.escape(old)}"
        r"(?![A-Za-z0-9_+-]|\.\d)"
    )
    text = version_pattern.sub(lambda match: f"{match.group('prefix')}{new}", text)
    if old_minor != new_minor:
        # Dependency policy is an open minor-line floor, never a patch pin.
        text = text.replace(f">={old_minor}.0", f">={new_minor}.0")
        text = text.replace(f'"{old_minor}.0"', f'"{new_minor}.0"')
        text = replace_current_minor_markers(text, old_minor, new_minor)
    return text


def update_release_facts(path: Path, old: str, new: str) -> str:
    facts = json.loads(path.read_text(encoding="utf-8"))
    old_minor = str(facts["current_minor"])
    new_minor = ".".join(new.split(".")[:2])
    facts["current_version"] = new
    if isinstance(facts.get("suitable_for"), str):
        facts["suitable_for"] = replace_version(facts["suitable_for"], old, new)
    facts["current_minor"] = new_minor
    if new_minor != old_minor:
        new_major, new_number = new_minor.split(".")
        facts["previous_minor"] = old_minor
        facts["next_minor"] = f"{new_major}.{int(new_number) + 1}"
    facts["docs_version_slug"] = f"v{new}"
    facts["docs_base_url"] = re.sub(
        r"/en/v[^/]+/", f"/en/v{new}/", facts["docs_base_url"]
    )
    facts["pypi_url"] = f"https://pypi.org/project/etlantic/{new}/"
    facts["github_release_url"] = (
        f"https://github.com/eddiethedean/etlantic/releases/tag/v{new}"
    )
    return json.dumps(facts, indent=2, ensure_ascii=False) + "\n"


def write_text_lf(path: Path, content: str) -> None:
    """Write repository text with stable LF line endings on every platform."""
    path.write_text(content, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synchronize ETLantic's lockstep 0.x.y package version.",
        epilog=(
            "Preview changes first with --dry-run. The apply step also runs "
            "uv lock and regenerates/checks plugin manifest digests. Review "
            "release facts, release wording, and generated fixtures afterward; "
            "this command does not tag or publish. See "
            "docs/11_DEVELOPMENT/RELEASE_PROCESS.md#version-bump-workflow."
        ),
    )
    parser.add_argument(
        "version", metavar="VERSION", help="new increasing 0.x.y version"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="List changes without writing files"
    )
    args = parser.parse_args()
    if not re.fullmatch(r"0\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", args.version):
        parser.error("version must be a semantic 0.x.y version")

    old = read_version()
    if args.version == old:
        parser.error(f"{args.version} is already the current version")
    old_pair = tuple(int(part) for part in old.split("."))
    new_pair = tuple(int(part) for part in args.version.split("."))
    if new_pair <= old_pair:
        parser.error(f"new version must be greater than current version {old}")
    facts = json.loads((ROOT / "docs/release-facts.json").read_text(encoding="utf-8"))
    if facts.get("current_version") != old:
        parser.error(
            "docs/release-facts.json current_version must match "
            f"src/etlantic/_version.py ({old}) before bumping"
        )
    changes: dict[Path, str] = {}
    old_minor = ".".join(old.split(".")[:2])
    new_minor = ".".join(args.version.split(".")[:2])
    for path in tracked_paths():
        if not path.is_file():
            continue
        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        updated = original
        if path.suffix == ".md" and path.is_relative_to(ROOT / "docs"):
            updated = replace_current_minor_markers(updated, old_minor, new_minor)
        if not is_version_surface(path):
            if updated != original:
                changes[path] = updated
            continue
        updated = (
            update_release_facts(path, old, args.version)
            if path.relative_to(ROOT).as_posix() == "docs/release-facts.json"
            else replace_version(updated, old, args.version)
        )
        if updated != original:
            changes[path] = updated

    # Preserve historical changelog entries while moving the active unreleased
    # section and its links to the new version.
    changelog = ROOT / "CHANGELOG.md"
    original = changelog.read_text(encoding="utf-8")
    active = re.search(
        rf"(?ms)^## \[{re.escape(old)}\] - Unreleased\n.*?(?=^## \[|\Z)",
        original,
    )
    if active:
        section = replace_version(active.group(0), old, args.version)
        original = original[: active.start()] + section + original[active.end() :]
        original = re.sub(
            rf"(?m)^\[{re.escape(old)}\]: https://github.com/eddiethedean/etlantic/releases/tag/v{re.escape(old)}\n?",
            "",
            original,
            count=1,
        )
    else:
        first_section = re.search(r"(?m)^## \[", original)
        if first_section is None:
            parser.error("CHANGELOG.md has no release sections")
        section = (
            f"## [{args.version}] - Unreleased\n\n"
            "### Changed\n\n"
            f"- Bump the core and first-party distribution versions to {args.version}.\n\n"
        )
        original = (
            original[: first_section.start()]
            + section
            + original[first_section.start() :]
        )
    original = re.sub(
        r"(?m)^\[Unreleased\]: .*?$",
        f"[Unreleased]: https://github.com/eddiethedean/etlantic/compare/v{args.version}...HEAD",
        original,
        count=1,
    )
    version_link = f"[{args.version}]: https://github.com/eddiethedean/etlantic/releases/tag/v{args.version}"
    if not re.search(rf"(?m)^\[{re.escape(args.version)}\]:", original):
        original = original.replace(
            f"[Unreleased]: https://github.com/eddiethedean/etlantic/compare/v{args.version}...HEAD\n",
            f"[Unreleased]: https://github.com/eddiethedean/etlantic/compare/v{args.version}...HEAD\n{version_link}\n",
            1,
        )
    if original != changelog.read_text(encoding="utf-8"):
        changes[changelog] = original

    if args.dry_run:
        print(f"Would update {len(changes)} files from {old} to {args.version}:")
        for path in sorted(changes):
            print(f"  {path.relative_to(ROOT)}")
        print(
            "Apply also refreshes uv.lock, plugin manifest digests, the "
            "DuckDB 0.49 evidence bundle, and the adaptive 0.52 evidence."
        )
        return 0

    for path, content in changes.items():
        write_text_lf(path, content)

    subprocess.run(["uv", "lock"], cwd=ROOT, check=True)
    subprocess.run(
        [sys.executable, "scripts/check_plugin_manifests.py", "--write-digests"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "scripts/check_plugin_manifests.py"], cwd=ROOT, check=True
    )
    subprocess.run(
        [
            "uv",
            "run",
            "--group",
            "duckdb",
            "python",
            "scripts/check_duckdb_0_49.py",
            "--write",
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [
            "uv",
            "run",
            "--group",
            "duckdb",
            "python",
            "scripts/check_duckdb_0_49.py",
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "scripts/check_adaptive_0_52.py", "--write"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "scripts/check_adaptive_0_52.py"], cwd=ROOT, check=True
    )
    print(
        f"Synchronized ETLantic from {old} to {args.version} ({len(changes)} source files)."
    )
    print(
        "Refreshed the DuckDB 0.49 and adaptive 0.52 evidence bundles. "
        "Review release facts, "
        "changelog notes, support claims, and remaining generated goldens "
        "before release checks."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
