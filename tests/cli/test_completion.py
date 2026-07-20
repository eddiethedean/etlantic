"""Shell completion smoke tests."""

from __future__ import annotations

import click
from typer.main import get_command

from etlantic.cli import app


def test_click_completion_command_exists() -> None:
    click_app = get_command(app)
    names = click_app.list_commands(click.Context(click_app))
    assert "init" in names
    assert "doctor" in names
    assert "profile" in names
    assert "report" in names
