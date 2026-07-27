#!/usr/bin/env python3
"""Verify first-party etlantic-plugin-manifest.json files (digest, version, entry points)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MANIFEST_PACKAGES = (
    "etlantic-polars",
    "etlantic-pandas",
    "etlantic-sql",
    "etlantic-pyspark",
    "etlantic-airflow",
    "etlantic-prefect",
    "etlantic-datafusion",
)


def _version_from_pyproject(path: Path) -> str:
    match = re.search(r'(?m)^version = "([^"]+)"', path.read_text(encoding="utf-8"))
    if match is None:
        raise ValueError(f"Could not read version from {path}")
    return match.group(1)


def _entry_points_from_pyproject(path: Path) -> dict[str, dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    groups: dict[str, dict[str, str]] = {}
    for match in re.finditer(
        r'\[project\.entry-points\."([^"]+)"\]\s*\n((?:[^\[]|\[(?!project))*?)(?=\n\[|\Z)',
        text,
        flags=re.S,
    ):
        group = match.group(1)
        section = match.group(2)
        entries: dict[str, str] = {}
        for line in section.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, target = line.partition("=")
            entries[name.strip()] = target.strip().strip('"').strip("'")
        groups[group] = entries
    return groups


def _manifest_path(package: str) -> Path:
    module = package.replace("-", "_")
    return (
        ROOT / "packages" / package / "src" / module / "etlantic-plugin-manifest.json"
    )


def main() -> int:
    sys.path.insert(0, str(ROOT / "src"))
    from etlantic.plugin_manifest import compute_manifest_digest

    errors: list[str] = []
    for package in MANIFEST_PACKAGES:
        manifest_path = _manifest_path(package)
        pyproject_path = ROOT / "packages" / package / "pyproject.toml"
        if not manifest_path.exists():
            errors.append(f"{package}: missing manifest at {manifest_path}")
            continue
        if not pyproject_path.exists():
            errors.append(f"{package}: missing pyproject.toml")
            continue

        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        pkg_version = _version_from_pyproject(pyproject_path)
        manifest_version = str(payload.get("version") or "")
        if manifest_version != pkg_version:
            errors.append(
                f"{package}: manifest version {manifest_version!r} != "
                f"pyproject {pkg_version!r}"
            )

        expected_digest = compute_manifest_digest(payload)
        declared = str(payload.get("digest") or "")
        if declared != expected_digest:
            errors.append(
                f"{package}: digest mismatch declared={declared!r} "
                f"expected={expected_digest!r}"
            )

        declared_entries = payload.get("entries") or []
        if not isinstance(declared_entries, list):
            errors.append(f"{package}: entries must be a list")
            continue

        pyproject_eps = _entry_points_from_pyproject(pyproject_path)
        seen: set[tuple[str, str]] = set()
        for item in declared_entries:
            if not isinstance(item, dict):
                errors.append(f"{package}: invalid entry {item!r}")
                continue
            group = str(item.get("group") or "")
            name = str(item.get("name") or "")
            target = str(item.get("target") or "")
            key = (group, name)
            seen.add(key)
            group_eps = pyproject_eps.get(group)
            if group_eps is None:
                errors.append(
                    f"{package}: manifest entry {group}[{name}] missing from pyproject"
                )
                continue
            if group_eps.get(name) != target:
                errors.append(
                    f"{package}: manifest entry {group}[{name}]={target!r} != "
                    f"pyproject {group_eps.get(name)!r}"
                )

        for group, entries in pyproject_eps.items():
            for name, target in entries.items():
                if (group, name) not in seen:
                    errors.append(
                        f"{package}: pyproject entry {group}[{name}]={target!r} "
                        "missing from manifest entries[]"
                    )

    if errors:
        print("Plugin manifest check FAILED:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        print(
            "\nRegenerate digests after manifest edits:\n"
            "  uv run python scripts/check_plugin_manifests.py --write-digests",
            file=sys.stderr,
        )
        return 1

    print(f"Plugin manifest check OK ({len(MANIFEST_PACKAGES)} packages).")
    return 0


def _write_digests() -> int:
    sys.path.insert(0, str(ROOT / "src"))
    from etlantic.plugin_manifest import compute_manifest_digest

    for package in MANIFEST_PACKAGES:
        manifest_path = _manifest_path(package)
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["digest"] = compute_manifest_digest(payload)
        manifest_path.write_text(
            json.dumps(payload, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        print(f"Updated digest: {manifest_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--write-digests":
        raise SystemExit(_write_digests())
    raise SystemExit(main())
