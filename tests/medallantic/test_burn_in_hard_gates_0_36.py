"""0.36 Medallantic hard gates: boundary audit + corpora promotion."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CORE_SRC = ROOT / "src" / "etlantic"

# Medallion vocabulary must not leak into core.
_LAYER_RE = re.compile(
    r"\b(bronze|silver|gold)\b",
    re.IGNORECASE,
)

# Allowlisted mentions (docs strings pointing to Medallantic / SparkForge).
_ALLOW_PATH_SUBSTR = (
    "/docs/",  # not under core src
)


def test_core_has_no_medallion_layer_types() -> None:
    offenders: list[str] = []
    for path in CORE_SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), start=1):
            if "medallantic" in line.lower() or "sparkforge" in line.lower():
                continue
            if "never" in line.lower() and _LAYER_RE.search(line):
                continue
            if _LAYER_RE.search(line) and not line.strip().startswith("#"):
                # Comments documenting the boundary are OK.
                if ("bronze/silver/gold" in line or "medallion" in line.lower()) and (
                    "must not" in line.lower() or "never" in line.lower()
                ):
                    continue
                offenders.append(f"{path.relative_to(ROOT)}:{i}:{line.strip()[:120]}")
    assert not offenders, "Medallion vocabulary leaked into core:\n" + "\n".join(
        offenders[:20]
    )


@pytest.mark.medallantic
def test_differential_corpora_importable() -> None:
    from etlantic.testing import (
        default_sparkforge_fixtures,
        default_sql_builder_fixtures,
        run_sparkforge_differential_suite,
        run_sql_builder_differential_suite,
    )

    sf = default_sparkforge_fixtures()
    assert sf
    sql = default_sql_builder_fixtures()
    assert sql
    assert callable(run_sparkforge_differential_suite)
    assert callable(run_sql_builder_differential_suite)


@pytest.mark.medallantic
def test_adapter_retention_imports() -> None:
    # Transitional adapters must still import in 0.36 (removal only on major).
    from medallantic.migrate import sparkforge as sf_migrate
    from medallantic.migrate import sql as sql_migrate

    assert sf_migrate is not None
    assert sql_migrate is not None


@pytest.mark.medallantic
def test_mdl_diagnostic_codes_stable() -> None:
    from medallantic import diagnostics as diag

    required = {
        "MDL200": diag.MDL200_INVENTORY,
        "MDL210": diag.MDL210_MANUAL,
        "MDL220": diag.MDL220_UNSUPPORTED,
        "MDL230": diag.MDL230_GENERATED,
    }
    for code, const in required.items():
        assert const == code
