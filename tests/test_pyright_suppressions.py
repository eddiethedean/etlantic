"""Regression tests for the Pyright suppression inventory gate."""

from pathlib import Path

import pytest
from scripts.check_pyright_suppressions import suppression_inventory


@pytest.mark.parametrize(
    "directive",
    ["# type: ignore[assignment]", "# pyright: ignore[reportAssignmentType]"],
)
def test_inline_suppression_inventory_pins_its_line(
    tmp_path: Path, directive: str
) -> None:
    source = tmp_path / "example.py"
    source.write_text(f"value = 1  {directive}\n", encoding="utf-8")

    first_inventory = suppression_inventory(tmp_path)
    source.write_text(f"value = 1\n\nvalue = 1  {directive}\n", encoding="utf-8")

    assert first_inventory == (f"example.py:1:{directive}",)
    assert suppression_inventory(tmp_path) == (f"example.py:3:{directive}",)
