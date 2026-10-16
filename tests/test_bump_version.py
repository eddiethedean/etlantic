"""Regression tests for version token replacement in the release helper."""

from pathlib import Path

from scripts.bump_version import (
    ROOT,
    is_version_surface,
    replace_version,
    write_text_lf,
)


def test_replace_version_updates_exact_tokens_without_touching_neighboring_versions() -> (
    None
):
    text = "Current 0.57.1; next 0.57.10; release v0.57.1."

    assert replace_version(text, "0.57.1", "0.60.0") == (
        "Current 0.60.0; next 0.57.10; release v0.60.0."
    )


def test_write_text_lf_uses_repository_line_endings(tmp_path: Path) -> None:
    path = tmp_path / "versioned-file.txt"

    write_text_lf(path, "first line\nsecond line\n")

    assert path.read_bytes() == b"first line\nsecond line\n"


def test_historical_release_documents_are_not_version_surfaces() -> None:
    paths = (
        ROOT / "docs/01_GETTING_STARTED/WHATS_NEW_0_57.md",
        ROOT / "docs/11_DEVELOPMENT/MIGRATION_0_56_TO_0_57.md",
        ROOT / "docs/11_DEVELOPMENT/EXIT_GATE_0_57.md",
        ROOT / "docs/11_DEVELOPMENT/IMPLEMENTATION_PLAN_0_58.md",
    )

    assert all(not is_version_surface(path) for path in paths)
