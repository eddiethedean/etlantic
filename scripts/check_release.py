#!/usr/bin/env python3
"""Release readiness checks for the current package version (no tagging)."""

from __future__ import annotations

import json
import re
import subprocess
import sys
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
    "etlantic-prefect",
    "etlantic-keyring",
    "etlantic-sqlmodel",
)
FACADE_PACKAGES = ("medallantic",)
REDIRECT_PACKAGES = ("etlantic-sparkforge",)
# Thin reference adapters align with core Beta maturity.
REFERENCE_PACKAGES = ("etlantic-fastapi",)
# Experimental packages may use Alpha classifiers and are optional in release CI.
EXPERIMENTAL_PACKAGES = (
    "etlantic-datafusion",
    "etlantic-s3",
    "etlantic-iceberg",
    "etlantic-snowflake",
    "etlantic-openlineage",
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


def pypi_project_exists(name: str) -> bool:
    url = f"https://pypi.org/pypi/{name}/json"
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            return resp.status == 200
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
    if f"| {major_minor}.x |" not in security:
        errors.append(f"SECURITY.md missing current supported line {major_minor}.x")

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
        if "Development Status :: 3 - Alpha" in text:
            errors.append(f"{pkg} still uses Alpha classifier")
        if "Development Status :: 5 - Production/Stable" in text:
            errors.append(
                f"{pkg} should use Beta, not Production/Stable (Beta pilot envelope)"
            )
        if "Development Status :: 4 - Beta" not in text:
            errors.append(f"{pkg} missing Beta classifier")
        major_minor = ".".join(version.split(".")[:2])
        next_minor = f"{major_minor.split('.')[0]}.{int(major_minor.split('.')[1]) + 1}"
        expected_dep = f"etlantic>={major_minor}.0,<{next_minor}"
        if expected_dep not in text:
            errors.append(f"{pkg} missing core dependency {expected_dep}")

    for pkg in FACADE_PACKAGES:
        path = ROOT / "packages" / pkg / "pyproject.toml"
        if not path.exists():
            errors.append(f"facade package missing: {pkg}")
            continue
        pkg_version = version_from(path, r'(?m)^version = "([^"]+)"')
        if pkg_version != version:
            errors.append(f"{pkg} version {pkg_version} != {version}")
        text = path.read_text(encoding="utf-8")
        if "[project.urls]" not in text:
            errors.append(f"{pkg} missing [project.urls]")
        if "Development Status :: 4 - Beta" not in text:
            errors.append(f"{pkg} facade package should use Beta classifier")
        if "Development Status :: 5 - Production/Stable" in text:
            errors.append(
                f"{pkg} facade package should use Beta, not Production/Stable "
                "(IR/migration adapter honesty)"
            )
        major_minor = ".".join(version.split(".")[:2])
        next_minor = f"{major_minor.split('.')[0]}.{int(major_minor.split('.')[1]) + 1}"
        expected_dep = f"etlantic>={major_minor}.0,<{next_minor}"
        if expected_dep not in text:
            errors.append(f"{pkg} missing core dependency {expected_dep}")

    for pkg in REDIRECT_PACKAGES:
        path = ROOT / "packages" / pkg / "pyproject.toml"
        if not path.exists():
            errors.append(f"redirect package missing: {pkg}")
            continue
        pkg_version = version_from(path, r'(?m)^version = "([^"]+)"')
        if pkg_version != version:
            errors.append(f"{pkg} version {pkg_version} != {version}")
        text = path.read_text(encoding="utf-8")
        if "Development Status :: 7 - Inactive" not in text:
            errors.append(f"{pkg} redirect package should use Inactive classifier")
        if "medallantic>=" not in text:
            errors.append(f"{pkg} redirect must depend on medallantic")

    for pkg in REFERENCE_PACKAGES:
        path = ROOT / "packages" / pkg / "pyproject.toml"
        if not path.exists():
            errors.append(f"reference package missing: {pkg}")
            continue
        pkg_version = version_from(path, r'(?m)^version = "([^"]+)"')
        if pkg_version != version:
            errors.append(f"{pkg} version {pkg_version} != {version}")
        text = path.read_text(encoding="utf-8")
        if "[project.urls]" not in text:
            errors.append(f"{pkg} missing [project.urls]")
        if "classifiers =" not in text:
            errors.append(f"{pkg} missing classifiers")
        if "Development Status :: 4 - Beta" not in text:
            errors.append(f"{pkg} reference package should use Beta classifier")
        if "Development Status :: 5 - Production/Stable" in text:
            errors.append(f"{pkg} should use Beta, not Production/Stable")
        major_minor = ".".join(version.split(".")[:2])
        next_minor = f"{major_minor.split('.')[0]}.{int(major_minor.split('.')[1]) + 1}"
        expected_dep = f"etlantic>={major_minor}.0,<{next_minor}"
        if expected_dep not in text:
            errors.append(f"{pkg} missing core dependency {expected_dep}")

    for pkg in EXPERIMENTAL_PACKAGES:
        path = ROOT / "packages" / pkg / "pyproject.toml"
        if not path.exists():
            errors.append(f"experimental package missing: {pkg}")
            continue
        pkg_version = version_from(path, r'(?m)^version = "([^"]+)"')
        if pkg_version != version:
            errors.append(f"{pkg} version {pkg_version} != {version}")
        text = path.read_text(encoding="utf-8")
        major_minor = ".".join(version.split(".")[:2])
        next_minor = f"{major_minor.split('.')[0]}.{int(major_minor.split('.')[1]) + 1}"
        expected_dep = f"etlantic>={major_minor}.0,<{next_minor}"
        if expected_dep not in text:
            errors.append(f"{pkg} missing core dependency {expected_dep}")
        if "Development Status :: 3 - Alpha" not in text:
            errors.append(f"{pkg} experimental package should use Alpha classifier")

    root_pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    pin_suffix = f"=={version}"
    for pkg in (
        *PACKAGES,
        *FACADE_PACKAGES,
        *REDIRECT_PACKAGES,
        *REFERENCE_PACKAGES,
        *EXPERIMENTAL_PACKAGES,
    ):
        if f"{pkg}{pin_suffix}" not in root_pyproject:
            errors.append(
                f"root pyproject.toml missing optional dependency pin {pkg}{pin_suffix}"
            )

    if "Development Status :: 3 - Alpha" in root_pyproject:
        errors.append("root pyproject.toml still uses Alpha classifier")
    if "Development Status :: 4 - Beta" not in root_pyproject:
        errors.append("root pyproject.toml missing Beta classifier")
    if "Development Status :: 5 - Production/Stable" in root_pyproject:
        errors.append("root pyproject.toml should use Beta, not Production/Stable")
    release_yml = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    checks_yml = (ROOT / ".github/workflows/checks.yml").read_text(encoding="utf-8")
    for pkg in (
        *PACKAGES,
        *FACADE_PACKAGES,
        *REDIRECT_PACKAGES,
        *REFERENCE_PACKAGES,
        *EXPERIMENTAL_PACKAGES,
    ):
        expected = pkg.replace("-", "_")
        if expected not in release_yml:
            errors.append(f"release.yml missing publish artifact stem {expected}")
        if pkg not in checks_yml:
            errors.append(f"checks.yml missing package build coverage for {pkg}")

    names = (
        "etlantic",
        *PACKAGES,
        *FACADE_PACKAGES,
        *REDIRECT_PACKAGES,
        *REFERENCE_PACKAGES,
        *EXPERIMENTAL_PACKAGES,
    )
    pypi_checked = True
    try:
        missing_version = [name for name in names if not pypi_exists(name, version)]
        brand_new = [name for name in names if not pypi_project_exists(name)]
    except (urllib.error.URLError, TimeoutError) as exc:
        pypi_checked = False
        missing_version = []
        brand_new = []
        reason = getattr(exc, "reason", exc)
        errors.append(f"PyPI availability check unavailable: {reason}")
    print(f"Release readiness for {version}")
    if brand_new:
        print(
            "Brand-new PyPI project names (first upload creates the project; "
            f"{len(brand_new)}/{len(names)}):"
        )
        for name in brand_new:
            note = ""
            if name in EXPERIMENTAL_PACKAGES:
                note = " (experimental)"
            elif name in REFERENCE_PACKAGES:
                note = " (reference adapter)"
            elif name in FACADE_PACKAGES:
                note = " (facade)"
            elif name in REDIRECT_PACKAGES:
                note = " (compatibility redirect)"
            print(f"  - {name}{note}  (will publish as {name}=={version})")
        print(
            "Release CI paces only new-project creates (10 minutes between them). "
            "Prefer a user-scoped PYPI_API_TOKEN. If the account is already "
            "rate-limited, wait for the rolling hour window before tagging."
        )
    if missing_version:
        existing_missing = [n for n in missing_version if n not in brand_new]
        if existing_missing:
            print(
                "Existing PyPI projects missing this version "
                f"({len(existing_missing)}/{len(names)}):"
            )
            for name in existing_missing:
                note = ""
                if name in EXPERIMENTAL_PACKAGES:
                    note = " (experimental)"
                elif name in REFERENCE_PACKAGES:
                    note = " (reference adapter)"
                print(f"  - {name}=={version}{note}")
    if pypi_checked and not missing_version:
        print(f"All packages already present on PyPI at {version}.")

    # Fail closed when tests/examples still import 0.26-removed root symbols.
    guard = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_removed_root_imports.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    if guard.returncode != 0:
        detail = (guard.stdout or guard.stderr or "").strip()
        errors.append(
            "removed root import guard failed" + (f": {detail}" if detail else "")
        )
    else:
        print((guard.stdout or "").strip() or "Removed root import guard passed.")

    freeze = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_protocol_freeze.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    if freeze.returncode != 0:
        detail = (freeze.stdout or freeze.stderr or "").strip()
        errors.append("protocol freeze gate failed" + (f": {detail}" if detail else ""))
    else:
        print((freeze.stdout or "").strip() or "Protocol freeze gate passed.")

    if errors:
        print("Release readiness FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("In-repo release readiness checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
