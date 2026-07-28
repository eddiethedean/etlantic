"""Facade-package conformance kit (definition round-trip + graph equivalence)."""

from __future__ import annotations

import ast
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from etlantic.authoring.definition import PipelineDefinition
from etlantic.authoring.lifecycle import plan_pipeline_like, validate_pipeline_like
from etlantic.authoring.normalize import logical_graph_from_definition
from etlantic.authoring.serialize import (
    pipeline_from_json,
    pipeline_to_json,
)
from etlantic.interchange.normalize import graphs_equivalent

_PRIVATE_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+etlantic\._|import\s+etlantic\._)",
    re.MULTILINE,
)


def assert_facade_public_imports(package_root: str | Path) -> None:
    """Fail if ``package_root`` imports private ``etlantic._*`` modules.

    Uses both a line regex and AST walk so comments/strings alone do not fail,
    while ``from etlantic._foo import bar`` does.
    """
    root = Path(package_root)
    if not root.exists():
        raise AssertionError(f"Facade package root does not exist: {root}")
    offenders: list[str] = []
    for path in sorted(root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if not _PRIVATE_IMPORT_RE.search(text):
            # Fast path: skip AST when no private import pattern appears.
            try:
                tree = ast.parse(text, filename=str(path))
            except SyntaxError:
                continue
            if not _ast_has_private_etlantic_import(tree):
                continue
        else:
            try:
                tree = ast.parse(text, filename=str(path))
            except SyntaxError as exc:
                raise AssertionError(
                    f"Cannot parse {path} while checking facade imports: {exc}"
                ) from exc
            if not _ast_has_private_etlantic_import(tree):
                continue
        offenders.append(str(path))
    if offenders:
        raise AssertionError(
            "Facade packages must not import private etlantic._* modules; "
            f"found in: {offenders}"
        )


def _ast_has_private_etlantic_import(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("etlantic._"):
                    return True
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.startswith("etlantic._"):
                return True
            if mod == "etlantic":
                for alias in node.names:
                    if alias.name.startswith("_"):
                        return True
    return False


def run_facade_conformance_suite(
    defn: PipelineDefinition | Callable[[], PipelineDefinition],
    *,
    profile: Any | None = None,
    facade_package: str | Path | None = None,
) -> PipelineDefinition:
    """Assert facade definition construction, round-trip, and plan determinism.

    Checks:
    1. JSON round-trip via ``pipeline_to_json`` / ``pipeline_from_json``
    2. Graph equivalence (fingerprints) across the round-trip
    3. Validation succeeds (or raises with a clear assertion)
    4. Two plans for the same profile share the same fingerprint
    5. Optional: no private ``etlantic._*`` imports under ``facade_package``
    """
    original = defn() if callable(defn) else defn
    if not isinstance(original, PipelineDefinition):
        raise TypeError(
            f"Facade conformance expects PipelineDefinition, got {type(original)!r}"
        )

    text = pipeline_to_json(original)
    round_tripped = pipeline_from_json(text)
    left = logical_graph_from_definition(original)
    right = logical_graph_from_definition(round_tripped)
    if not graphs_equivalent(left, right):
        raise AssertionError(
            "Facade definition graph changed across JSON round-trip "
            f"({original.pipeline_id!r})"
        )
    if pipeline_to_json(round_tripped, indent=None) != pipeline_to_json(
        original, indent=None
    ):
        raise AssertionError(
            "Facade definition JSON is not byte-stable after round-trip "
            f"({original.pipeline_id!r})"
        )

    report = validate_pipeline_like(round_tripped, profile=profile)
    if report.has_errors:
        raise AssertionError(
            f"Facade definition failed validation: "
            f"{[d.code for d in report.diagnostics if d.severity.value == 'error']}"
        )

    plan_a = plan_pipeline_like(round_tripped, profile=profile)
    plan_b = plan_pipeline_like(round_tripped, profile=profile)
    if plan_a.fingerprint != plan_b.fingerprint:
        raise AssertionError(
            "Facade plan fingerprint is not deterministic for the same definition "
            f"and profile ({original.pipeline_id!r})"
        )

    if facade_package is not None:
        assert_facade_public_imports(facade_package)

    return round_tripped


__all__ = [
    "assert_facade_public_imports",
    "run_facade_conformance_suite",
]
