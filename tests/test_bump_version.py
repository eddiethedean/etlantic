"""Regression tests for version token replacement in the release helper."""

from scripts.bump_version import replace_version


def test_replace_version_updates_exact_tokens_without_touching_neighboring_versions() -> (
    None
):
    text = "Current 0.57.1; next 0.57.10; release v0.57.1."

    assert replace_version(text, "0.57.1", "0.57.2") == (
        "Current 0.57.2; next 0.57.10; release v0.57.2."
    )
