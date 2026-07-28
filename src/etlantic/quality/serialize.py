"""Canonical serialization and fingerprinting for ``etlantic.quality/1``."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from etlantic.quality.model import QUALITY_SCHEMA, QualityExpression
from etlantic.quality.upgrade import upgrade_quality_dict


def _sort_structure(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _sort_structure(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [_sort_structure(v) for v in value]
    return value


def quality_to_dict(expr: QualityExpression) -> dict[str, Any]:
    """Serialize a quality expression including optional fingerprint."""
    return expr.to_dict()


def canonical_quality_dict(expr: QualityExpression) -> dict[str, Any]:
    """Return a deterministically ordered dict for hashing."""
    data = copy.deepcopy(expr.to_dict())
    data.pop("fingerprint", None)
    return _sort_structure(data)


def canonical_quality_json(expr: QualityExpression) -> str:
    """Return canonical JSON for fingerprinting."""
    return json.dumps(
        canonical_quality_dict(expr),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def quality_fingerprint(expr: QualityExpression) -> str:
    """Compute a stable SHA-256 fingerprint of the canonical expression."""
    return hashlib.sha256(canonical_quality_json(expr).encode("utf-8")).hexdigest()


def verify_quality_fingerprint(expr: QualityExpression) -> None:
    """Recompute fingerprint and compare to ``expr.fingerprint``."""
    expected = quality_fingerprint(expr)
    if expr.fingerprint != expected:
        raise ValueError(
            f"QualityExpression fingerprint mismatch: "
            f"embedded={expr.fingerprint!r} computed={expected!r}"
        )


def quality_from_dict(
    data: dict[str, Any],
    *,
    verify: bool = True,
    fingerprint: bool = True,
    recompute_fingerprint: bool = False,
) -> QualityExpression:
    """Deserialize a quality expression, upgrading schema when needed.

    Args:
        data: Mapping with ``schema`` ``etlantic.quality/1``.
        verify: When True, verify embedded fingerprint if present.
        fingerprint: When True and fingerprint missing, compute and attach one.
        recompute_fingerprint: When True, always replace fingerprint with the
            recomputed canonical hash (plan metadata must not trust drift).
    """
    upgraded = upgrade_quality_dict(data)
    expr = QualityExpression.from_dict(upgraded)
    if recompute_fingerprint or (fingerprint and expr.fingerprint is None):
        expr = QualityExpression(
            schema=expr.schema,
            expression_id=expr.expression_id,
            ruleset=expr.ruleset,
            fingerprint=quality_fingerprint(expr),
            metadata=expr.metadata,
        )
    elif verify and expr.fingerprint is not None:
        verify_quality_fingerprint(expr)
    if expr.schema != QUALITY_SCHEMA:
        raise ValueError(
            f"QualityExpression schema {expr.schema!r} != {QUALITY_SCHEMA!r}"
        )
    return expr
