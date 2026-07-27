#!/usr/bin/env python3
"""Fail closed when first-party transform-compiler packaging drifts."""

from __future__ import annotations

import sys
from importlib.metadata import entry_points
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FIRST_PARTY = {
    "polars": {
        "package": "etlantic-polars",
        "runtime_group": "etlantic.dataframe_plugins",
    },
    "pandas": {
        "package": "etlantic-pandas",
        "runtime_group": "etlantic.dataframe_plugins",
    },
    "pyspark": {
        "package": "etlantic-pyspark",
        "runtime_group": "etlantic.spark_plugins",
    },
    "sql": {
        "package": "etlantic-sql",
        "runtime_group": "etlantic.sql_plugins",
    },
    "datafusion": {
        "package": "etlantic-datafusion",
        "runtime_group": "etlantic.dataframe_plugins",
    },
}


def _entry_point_names(group: str) -> set[str]:
    try:
        eps = entry_points(group=group)
    except TypeError:  # pragma: no cover
        eps = entry_points().get(group, [])  # type: ignore[attr-defined]
    return {ep.name for ep in eps}


def _pyproject_declares(engine: str, group: str) -> bool:
    path = ROOT / "packages" / FIRST_PARTY[engine]["package"] / "pyproject.toml"
    text = path.read_text(encoding="utf-8")
    marker = f'[project.entry-points."{group}"]'
    if marker not in text:
        return False
    section = text.split(marker, 1)[1].split("\n[", 1)[0]
    return f"{engine} =" in section


def main() -> int:
    errors: list[str] = []
    compilers = _entry_point_names("etlantic.transform_compilers")
    for engine, meta in FIRST_PARTY.items():
        if engine not in compilers:
            errors.append(f"missing transform_compilers entry point {engine!r}")
        if not _pyproject_declares(engine, "etlantic.transform_compilers"):
            errors.append(
                f"{meta['package']} pyproject missing transform_compilers[{engine}]"
            )
        if not _pyproject_declares(engine, meta["runtime_group"]):
            errors.append(
                f"{meta['package']} pyproject missing {meta['runtime_group']}[{engine}]"
            )

    guide = (ROOT / "docs/07_PLUGIN_SDK/BUILDING_A_PLUGIN.md").read_text(
        encoding="utf-8"
    )
    if "etlantic.transform_compilers" not in guide:
        errors.append(
            "BUILDING_A_PLUGIN.md missing transform_compilers entry-point docs"
        )
    if "First-party portable policy (0.17)" not in guide:
        errors.append("BUILDING_A_PLUGIN.md missing 0.17 first-party portable policy")

    matrix = (ROOT / "docs/10_REFERENCE/PORTABLE_COMPILER_MATRIX.md").read_text(
        encoding="utf-8"
    )
    for token in (
        "portable-string-advanced/1",
        "portable-conversion/1",
        "portable-statistics/1",
        "portable-window/1",
        "portable-complex-values/1",
        "portable-complex-types/1",
        "portable-reshape/1",
    ):
        if token not in matrix:
            errors.append(f"PORTABLE_COMPILER_MATRIX.md missing {token}")

    try:
        from etlantic.transform.discovery import discover_transform_compilers

        matrix_functions = {
            "dtcs:profile/portable-string-advanced/1": frozenset(
                {
                    "dtcs:trim",
                    "dtcs:ltrim",
                    "dtcs:rtrim",
                    "dtcs:regex_extract",
                    "dtcs:regex_replace",
                    "dtcs:split",
                }
            ),
            "dtcs:profile/portable-conversion/1": frozenset(
                {
                    "dtcs:to_string",
                    "dtcs:try_cast",
                    "dtcs:cast",
                    "dtcs:to_integer",
                }
            ),
            "dtcs:profile/portable-statistics/1": frozenset(
                {"dtcs:variance", "dtcs:stddev", "dtcs:corr"}
            ),
            "dtcs:profile/portable-window/1": frozenset(
                {
                    "dtcs:row_number",
                    "dtcs:rank",
                    "dtcs:dense_rank",
                    "dtcs:lag",
                    "dtcs:lead",
                    "dtcs:first_value",
                    "dtcs:last_value",
                }
            ),
            "dtcs:profile/portable-complex-values/1": frozenset(
                {"dtcs:array", "dtcs:object", "dtcs:size"}
            ),
            "dtcs:profile/portable-complex-types/1": frozenset(
                {"dtcs:field", "dtcs:index", "dtcs:element_at"}
            ),
        }

        found = discover_transform_compilers()
        for engine in ("polars", "pyspark"):
            compiler = found.get(engine)
            if compiler is None:
                continue
            profiles = set(compiler.info.capabilities.profiles)
            functions = set(compiler.info.capabilities.functions)
            for token in (
                "dtcs:profile/portable-string-advanced/1",
                "dtcs:profile/portable-window/1",
                "dtcs:profile/portable-reshape/1",
            ):
                if token not in profiles:
                    errors.append(f"{engine} compiler missing graduated claim {token}")
            for profile, required in matrix_functions.items():
                if profile not in profiles:
                    continue
                missing = sorted(required - functions)
                if missing:
                    errors.append(
                        f"{engine} claims {profile} but missing functions: "
                        + ", ".join(missing)
                    )
            if (
                "dtcs:profile/portable-complex-values/1" in profiles
                and engine == "pyspark"
                and "dtcs:map" not in functions
            ):
                errors.append(f"{engine} complex-values claim missing dtcs:map")
    except Exception as exc:  # pragma: no cover
        errors.append(f"transform compiler discovery failed: {exc}")

    if errors:
        print("Transform compiler drift check failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print("Transform compiler drift check OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
