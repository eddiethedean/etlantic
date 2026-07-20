"""Pipeline target loading helpers for the CLI."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

import typer


def load_target(target: str) -> type[Any]:
    """Load ``module.path:ClassName`` or a file path ``file.py:ClassName``."""
    if ":" not in target:
        raise typer.BadParameter("Target must be module:Class or path.py:Class")
    module_part, class_name = target.rsplit(":", 1)
    path = Path(module_part)
    if path.suffix == ".py" and path.exists():
        module_name = f"_etlantic_cli_{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise typer.BadParameter(f"Cannot import {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    else:
        module = importlib.import_module(module_part)
    try:
        return getattr(module, class_name)
    except AttributeError as exc:
        raise typer.BadParameter(
            f"Module {module_part!r} has no attribute {class_name!r}"
        ) from exc


def build_selection(
    *,
    run_one: str | None,
    run_until: str | None,
    nodes: str | None,
) -> dict[str, Any] | None:
    if run_one and run_until:
        raise typer.BadParameter("Use only one of --run-one or --run-until.")
    selection: dict[str, Any] = {}
    if run_one:
        selection["run_one"] = run_one
    if run_until:
        selection["run_until"] = run_until
    if nodes:
        selection["nodes"] = [n.strip() for n in nodes.split(",") if n.strip()]
    return selection or None
