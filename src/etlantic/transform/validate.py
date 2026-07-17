"""Portable definition validation and PMXFORM diagnostics."""

from __future__ import annotations

from typing import Any

from etlantic.diagnostics import Diagnostic, Severity, ValidationReport
from etlantic.exceptions import ModelDefinitionError
from etlantic.transform.protocol import DEFAULT_BUDGETS, TransformBudgets


def _diag(
    code: str,
    message: str,
    *,
    path: tuple[str, ...] = (),
    help: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Diagnostic:
    return Diagnostic(
        code=code,
        severity=Severity.ERROR,
        message=message,
        path=path,
        help=help,
        metadata=metadata or {},
        phase="portable_authoring",
    )


def count_nodes(node: Any) -> int:
    if isinstance(node, dict):
        return 1 + sum(count_nodes(v) for v in node.values())
    if isinstance(node, list):
        return sum(count_nodes(v) for v in node)
    return 0


def max_depth(node: Any, depth: int = 0) -> int:
    if isinstance(node, dict):
        if not node:
            return depth
        return max(max_depth(v, depth + 1) for v in node.values())
    if isinstance(node, list):
        if not node:
            return depth
        return max(max_depth(v, depth + 1) for v in node)
    return depth


def _walk_reject(node: Any, *, path: str, diagnostics: list[Diagnostic]) -> None:
    if callable(node) and not isinstance(node, type):
        diagnostics.append(
            _diag(
                "PMXFORM801",
                "Portable definitions must not capture callables",
                path=(path,),
            )
        )
        return
    if isinstance(node, (bytes, bytearray, memoryview)):
        diagnostics.append(
            _diag(
                "PMXFORM802",
                "Binary literals are not allowed in portable IR",
                path=(path,),
            )
        )
        return
    # Secret-like duck typing without importing optional secrets internals heavily
    type_name = type(node).__name__
    if type_name in {"SecretValue", "SecretRef"} or (
        hasattr(node, "reveal") and hasattr(node, "redacted")
    ):
        diagnostics.append(
            _diag(
                "PMXFORM803",
                "Secret values must not be captured as portable literals",
                path=(path,),
            )
        )
        return
    if isinstance(node, dict):
        for key, value in node.items():
            _walk_reject(value, path=f"{path}.{key}", diagnostics=diagnostics)
    elif isinstance(node, list):
        for idx, value in enumerate(node):
            _walk_reject(value, path=f"{path}[{idx}]", diagnostics=diagnostics)


def validate_output_binding(
    *,
    declared_outputs: set[str],
    produced: dict[str, Any],
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    missing = declared_outputs - set(produced)
    extra = set(produced) - declared_outputs
    for name in sorted(missing):
        diagnostics.append(
            _diag(
                "PMXFORM201",
                f"Declared output {name!r} is missing from the portable definition return value",
                path=("outputs", name),
            )
        )
    for name in sorted(extra):
        diagnostics.append(
            _diag(
                "PMXFORM202",
                f"Portable definition returned undeclared output {name!r}",
                path=("outputs", name),
            )
        )
    return diagnostics


def validate_plan_budgets(
    plan: dict[str, Any],
    *,
    budgets: TransformBudgets = DEFAULT_BUDGETS,
) -> list[Diagnostic]:
    import json

    diagnostics: list[Diagnostic] = []
    encoded = json.dumps(plan, sort_keys=True, default=str)
    if len(encoded.encode("utf-8")) > budgets.max_document_bytes:
        diagnostics.append(
            _diag(
                "PMXFORM810",
                f"Portable plan exceeds max_document_bytes={budgets.max_document_bytes}",
            )
        )
    nodes = count_nodes(plan)
    if nodes > budgets.max_nodes:
        diagnostics.append(
            _diag(
                "PMXFORM811",
                f"Portable plan node count {nodes} exceeds max_nodes={budgets.max_nodes}",
            )
        )
    depth = max_depth(plan)
    if depth > budgets.max_depth:
        diagnostics.append(
            _diag(
                "PMXFORM812",
                f"Portable plan depth {depth} exceeds max_depth={budgets.max_depth}",
            )
        )
    _walk_reject(plan, path="plan", diagnostics=diagnostics)
    return diagnostics


def report_or_raise(
    diagnostics: list[Diagnostic], *, raise_on_error: bool = True
) -> ValidationReport:
    report = ValidationReport(
        diagnostics=tuple(diagnostics), phases=("portable_authoring",)
    )
    if raise_on_error and report.has_errors:
        raise ModelDefinitionError(
            "; ".join(d.message for d in report.errors) or "portable definition invalid"
        )
    return report
