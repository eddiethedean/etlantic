#!/usr/bin/env python3
"""Release readiness checks for the current package version (no tagging)."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = (
    "etlantic-polars",
    "etlantic-pandas",
    "etlantic-sql",
    "etlantic-pyspark",
    "etlantic-airflow",
    "etlantic-keyring",
    "etlantic-sqlmodel",
    "etlantic-sparkforge",
)


def version_from(path: Path, pattern: str) -> str:
    match = re.search(pattern, path.read_text(encoding="utf-8"))
    if match is None:
        raise SystemExit(f"Could not find version in {path}")
    return match.group(1)


def pypi_exists(name: str, version: str) -> bool:
    url = f"https://pypi.org/pypi/{name}/{version}/json"
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            payload = json.load(resp)
        return payload.get("info", {}).get("version") == version
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        raise


def main() -> int:
    errors: list[str] = []
    version = version_from(
        ROOT / "src/etlantic/_version.py", r'__version__ = "([^"]+)"'
    )
    project = version_from(ROOT / "pyproject.toml", r'(?m)^version = "([^"]+)"')
    if version != project:
        errors.append(f"core version mismatch: module={version} project={project}")

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if f"## [{version}]" not in changelog:
        errors.append(f"CHANGELOG.md missing section ## [{version}]")
    if f"[{version}]:" not in changelog:
        errors.append(f"CHANGELOG.md missing footer link [{version}]:")

    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    major_minor = ".".join(version.split(".")[:2])
    if f"| {major_minor}.x | Current alpha line" not in security:
        errors.append(f"SECURITY.md missing current alpha line {major_minor}.x")

    for pkg in PACKAGES:
        path = ROOT / "packages" / pkg / "pyproject.toml"
        pkg_version = version_from(path, r'(?m)^version = "([^"]+)"')
        if pkg_version != version:
            errors.append(f"{pkg} version {pkg_version} != {version}")
        text = path.read_text(encoding="utf-8")
        if "[project.urls]" not in text:
            errors.append(f"{pkg} missing [project.urls]")
        if "classifiers =" not in text:
            errors.append(f"{pkg} missing classifiers")

    release_yml = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    for pkg in PACKAGES:
        expected = pkg.replace("-", "_")
        if expected not in release_yml:
            errors.append(f"release.yml missing publish artifact stem {expected}")

    missing_projects = [
        name for name in ("etlantic", *PACKAGES) if not pypi_exists(name, version)
    ]
    print(f"Release readiness for {version}")
    if missing_projects:
        print(
            "PyPI projects/files not yet published for this version "
            f"({len(missing_projects)}/{1 + len(PACKAGES)}):"
        )
        for name in missing_projects:
            print(f"  - {name}=={version}")
        print(
            "Before tagging a first-time name set, pre-register empty projects on "
            "PyPI to avoid 429 Too many new projects created."
        )
    else:
        print(f"All packages already present on PyPI at {version}.")

    if errors:
        print("Release readiness FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("In-repo release readiness checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
