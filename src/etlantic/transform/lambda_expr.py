"""Bounded lambda authoring helpers for higher-order complex-value functions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from etlantic.exceptions import ModelDefinitionError
from etlantic.transform.column import ColumnExpr, coerce_column
from etlantic.transform.protocol import PROFILE_COMPLEX_VALUES


def lambda_(
    *parameters: str,
    body: ColumnExpr | Callable[..., ColumnExpr] | None = None,
) -> ColumnExpr:
    """Build a bounded DTCS lambda Expression node.

    Prefer ``lambda_("element", body=F.col("element") > 0)`` or a callable that
    receives ``ColumnExpr`` parameters bound with ``scope: "lambda"``.
    """
    if not parameters:
        raise ModelDefinitionError("lambda requires at least one parameter name")
    if body is None:
        raise ModelDefinitionError("lambda requires a body expression")

    if callable(body) and not isinstance(body, ColumnExpr):
        args = [
            ColumnExpr(
                node={"kind": "fieldRef", "target": name, "scope": "lambda"},
                path=f"lambda:{name}",
                profiles=frozenset({PROFILE_COMPLEX_VALUES}),
            )
            for name in parameters
        ]
        body_expr = body(*args)
        if not isinstance(body_expr, ColumnExpr):
            raise ModelDefinitionError("lambda body callable must return ColumnExpr")
    else:
        body_expr = coerce_column(body)

    # Reject undeclared outer field capture beyond declared parameters: only
    # allow fieldRefs with scope lambda or explicit non-capture calls/literals.
    _assert_lambda_body(body_expr.node, set(parameters))

    return ColumnExpr(
        node={
            "kind": "lambda",
            "parameters": list(parameters),
            "body": body_expr.node,
        },
        path=f"lambda({','.join(parameters)})",
        functions=body_expr.functions,
        profiles=body_expr.profiles | frozenset({PROFILE_COMPLEX_VALUES}),
    )


def _assert_lambda_body(node: dict[str, Any], params: set[str]) -> None:
    kind = node.get("kind")
    if kind == "fieldRef":
        scope = node.get("scope")
        target = node.get("target")
        if scope == "lambda":
            if target not in params:
                raise ModelDefinitionError(
                    f"lambda fieldRef {target!r} is not a declared parameter"
                )
            return
        if scope == "parameter":
            return
        raise ModelDefinitionError(
            "lambda body must not capture undeclared outer fieldRefs "
            f"(found {target!r}); use scope='lambda' parameters"
        )
    if kind == "literal":
        return
    if kind == "unary":
        _assert_lambda_body(node["expr"], params)
        return
    if kind == "binary":
        _assert_lambda_body(node["left"], params)
        _assert_lambda_body(node["right"], params)
        return
    if kind == "call":
        for arg in node.get("args", []):
            if isinstance(arg, dict):
                _assert_lambda_body(arg, params)
        return
    if kind == "lambda":
        nested = set(node.get("parameters", []))
        _assert_lambda_body(node["body"], nested)
        return


def transform(collection: Any, fn: ColumnExpr) -> ColumnExpr:
    """Higher-order transform over a collection using a lambda ColumnExpr."""
    col = coerce_column(collection)
    if fn.node.get("kind") != "lambda":
        raise ModelDefinitionError("transform requires a lambda ColumnExpr")
    return ColumnExpr(
        node={"kind": "call", "callee": "dtcs:transform", "args": [col.node, fn.node]},
        path="transform",
        functions=col.functions | fn.functions | frozenset({"dtcs:transform"}),
        profiles=col.profiles | fn.profiles | frozenset({PROFILE_COMPLEX_VALUES}),
    )


def exists(collection: Any, fn: ColumnExpr) -> ColumnExpr:
    col = coerce_column(collection)
    if fn.node.get("kind") != "lambda":
        raise ModelDefinitionError("exists requires a lambda ColumnExpr")
    return ColumnExpr(
        node={"kind": "call", "callee": "dtcs:exists", "args": [col.node, fn.node]},
        path="exists",
        functions=col.functions | fn.functions | frozenset({"dtcs:exists"}),
        profiles=col.profiles | fn.profiles | frozenset({PROFILE_COMPLEX_VALUES}),
    )


def forall(collection: Any, fn: ColumnExpr) -> ColumnExpr:
    col = coerce_column(collection)
    if fn.node.get("kind") != "lambda":
        raise ModelDefinitionError("forall requires a lambda ColumnExpr")
    return ColumnExpr(
        node={"kind": "call", "callee": "dtcs:forall", "args": [col.node, fn.node]},
        path="forall",
        functions=col.functions | fn.functions | frozenset({"dtcs:forall"}),
        profiles=col.profiles | fn.profiles | frozenset({PROFILE_COMPLEX_VALUES}),
    )
