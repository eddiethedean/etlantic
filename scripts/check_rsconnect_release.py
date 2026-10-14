#!/usr/bin/env python3
"""Verify the independently versioned Connect preview without live services.

Use ``--tag etlantic-rsconnect-vX.Y.Z`` before tagging. After building, run
``--installed --expected-version X.Y.Z`` with Python's ``-I`` option in a clean
wheel environment. Neither mode contacts Connect, a receiver, or a registry.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from packaging.requirements import Requirement
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "etlantic-rsconnect"
TAG_PREFIX = "etlantic-rsconnect-v"


def _toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _module_version(path: Path) -> str:
    for statement in ast.parse(path.read_text(encoding="utf-8")).body:
        if (
            isinstance(statement, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "__version__"
                for target in statement.targets
            )
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        ):
            return statement.value.value
    raise ValueError("preview module has no literal __version__")


def _requirement(requirements: list[str], name: str) -> Requirement:
    matches = [Requirement(item) for item in requirements]
    matches = [item for item in matches if item.name == name]
    if len(matches) != 1:
        raise ValueError(f"expected one {name} dependency")
    return matches[0]


def inspect_source(root: Path = ROOT, *, tag: str | None = None) -> dict[str, object]:
    package_dir = root / "packages" / PACKAGE
    project = _toml(package_dir / "pyproject.toml")["project"]
    version = str(project["version"])
    if project["name"] != PACKAGE or str(Version(version)) != version:
        raise ValueError("preview package name or version is invalid")
    module_version = _module_version(package_dir / "src/etlantic_rsconnect/__init__.py")
    if version != module_version:
        raise ValueError("preview metadata and module versions differ")
    if tag is not None and tag != f"{TAG_PREFIX}{version}":
        raise ValueError(f"preview tag must be {TAG_PREFIX}{version}")

    core = _toml(root / "pyproject.toml")["project"]
    core_version = str(core["version"])
    core_requirement = _requirement(project["dependencies"], "etlantic")
    if Version(core_version) not in core_requirement.specifier:
        raise ValueError("preview core dependency does not accept the workspace core")
    sdk = _requirement(project["optional-dependencies"]["connect"], "posit-sdk")
    sdk_versions = list(sdk.specifier)
    if (
        len(sdk_versions) != 1
        or sdk_versions[0].operator != "=="
        or "*" in sdk_versions[0].version
    ):
        raise ValueError("the Connect extra must pin one exact SDK version")
    root_extra = _requirement(core["optional-dependencies"]["rsconnect"], PACKAGE)
    if (
        "connect" not in root_extra.extras
        or Version(version) not in root_extra.specifier
    ):
        raise ValueError("the root rsconnect extra does not select this preview")
    locked = [
        item
        for item in cast(list[dict[str, Any]], _toml(root / "uv.lock")["package"])
        if item["name"] == PACKAGE
    ]
    if len(locked) != 1 or locked[0]["version"] != version:
        raise ValueError("the lockfile does not match the preview version")
    notes = (package_dir / "CHANGELOG.md").read_text(encoding="utf-8")
    if f"## [{version}]" not in notes:
        raise ValueError("preview release notes are missing")
    if not (package_dir / "LICENSE").is_file():
        raise ValueError("preview license file is missing")
    return {
        "schema": "etlantic.rsconnect.release_check/1",
        "status": "pass",
        "mode": "source",
        "version": version,
        "core_version": core_version,
        "core_requirement": str(core_requirement),
        "sdk_requirement": str(sdk),
        "tag": tag,
        "qualification": "preview",
        "external_services_required": False,
    }


def _assert_installed(module: ModuleType) -> None:
    if module.__file__ is None or Path(module.__file__).resolve().is_relative_to(ROOT):
        raise ValueError(f"{module.__name__} was imported from the workspace")


def inspect_installed(expected_version: str) -> dict[str, object]:
    import etlantic_rsconnect as connect

    import etlantic
    from etlantic.outbound import OutboundPolicy
    from etlantic.secrets import SecretRef

    _assert_installed(etlantic)
    _assert_installed(connect)
    version = importlib.metadata.version(PACKAGE)
    if version != expected_version or connect.__version__ != version:
        raise ValueError("installed preview version does not match the release")
    if not any(
        path.name == "LICENSE" and ".dist-info/" in str(path)
        for path in importlib.metadata.files(PACKAGE) or []
    ):
        raise ValueError("installed preview does not contain its license notice")
    core_version = importlib.metadata.version("etlantic")
    requirement = _requirement(importlib.metadata.requires(PACKAGE) or [], "etlantic")
    if Version(core_version) not in requirement.specifier:
        raise ValueError("installed core is outside the preview dependency range")
    forbidden = (
        "posit",
        "fastapi",
        "etlantic_fastapi",
        "etlantic_datamover",
        "polars",
        "pandas",
        "pyspark",
        "datafusion",
        "duckdb",
    )
    if any(importlib.util.find_spec(name) is not None for name in forbidden):
        raise ValueError("base preview installation pulled an optional SDK or engine")
    if any(not hasattr(connect, name) for name in connect.__all__):
        raise ValueError("installed preview public exports are incomplete")

    def bundle() -> connect.TriggerBundle:
        return connect.build_trigger_bundle(
            schedule_id="release-schedule",
            schedule_revision_id="release-revision",
            timer_owner_generation=1,
            endpoint_url="https://receiver.example.invalid/trigger",
            credential_ref=SecretRef("env", "receiver", "token"),
            credential_env="ETLANTIC_TRIGGER_TOKEN",
            outbound_policy=OutboundPolicy(
                allowed_hosts=("receiver.example.invalid",),
            ),
        )

    first, second = bundle(), bundle()
    if first.archive != second.archive or first.sha256 != second.sha256:
        raise ValueError("installed bundle generation is not deterministic")
    with tempfile.TemporaryDirectory(prefix="etlantic-connect-release-") as temp:
        directory = first.write_to(Path(temp) / "content")
        runner = str(directory / "etlantic-trigger.py")
        environment = {
            "ETLANTIC_TRIGGER_ARMED": "false",
            "ETLANTIC_TRIGGER_TOKEN": "synthetic-release-sentinel",
            "ETLANTIC_SCHEDULED_AT": "2026-10-14T12:00:00Z",
            "ETLANTIC_DELIVERY_ATTEMPT_ID": "synthetic-attempt",
            "ETLANTIC_CORRELATION_ID": "synthetic-correlation",
        }
        # Windows requires SystemRoot to initialize the standard library.
        if "SYSTEMROOT" in os.environ:
            environment["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
        disarmed = subprocess.run(
            [sys.executable, "-I", "-S", runner],
            cwd=directory,
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if disarmed.returncode or json.loads(disarmed.stdout) != {"status": "disarmed"}:
            raise ValueError("installed standalone runner did not remain disarmed")
        environment["ETLANTIC_TRIGGER_ARMED"] = "true"
        armed = subprocess.run(
            [sys.executable, "-I", "-S", runner],
            cwd=directory,
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if (
            armed.returncode == 0
            or "no qualified Connect occurrence provider" not in armed.stderr
            or "synthetic-release-sentinel" in armed.stdout + armed.stderr
        ):
            raise ValueError("installed standalone runner accepted unbound context")
    return {
        "schema": "etlantic.rsconnect.release_check/1",
        "status": "pass",
        "mode": "installed",
        "version": version,
        "core_version": core_version,
        "qualification": "preview",
        "bundle_sha256": first.sha256,
        "checks": [
            "installed_imports",
            "optional_dependencies_absent",
            "public_exports",
            "license_notice",
            "deterministic_bundle",
            "verified_bundle_manifest",
            "standard_library_runner",
            "disarmed_render",
            "unbound_context_denied",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag")
    parser.add_argument("--installed", action="store_true")
    parser.add_argument("--expected-version")
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.installed and (not args.expected_version or args.tag):
        parser.error(
            "--installed requires --expected-version and does not accept --tag"
        )
    try:
        result = (
            inspect_installed(args.expected_version)
            if args.installed
            else inspect_source(tag=args.tag)
        )
        if args.wheel:
            result["wheel_sha256"] = hashlib.sha256(args.wheel.read_bytes()).hexdigest()
        serialized = json.dumps(result, sort_keys=True, indent=2) + "\n"
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(serialized, encoding="utf-8")
        print(serialized, end="")
    except (
        ValueError,
        OSError,
        KeyError,
        importlib.metadata.PackageNotFoundError,
    ) as exc:
        print(f"Connect preview release check failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
