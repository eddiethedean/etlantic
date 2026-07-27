"""SQL keyed deduplicate must fail closed (no silent full-row DISTINCT)."""

from __future__ import annotations

import pytest

pytest.importorskip("sqlalchemy")

from etlantic.sql.protocol import RelationRef
from etlantic_sql.lowering.actions import apply_action_to_query

pytestmark = pytest.mark.sql


def test_keyed_deduplicate_fails_closed() -> None:
    source = RelationRef(name="t")
    with pytest.raises(ValueError, match="keys/subset is not implemented"):
        apply_action_to_query(
            source,
            ["id", "name"],
            {
                "kind": {
                    "action": "dtcs:deduplicate",
                    "parameters": {"keys": ["id"]},
                }
            },
            parameters={},
            relations={},
            relation_columns={},
        )


def test_full_row_deduplicate_still_works() -> None:
    source = RelationRef(name="t")
    query, cols = apply_action_to_query(
        source,
        ["id", "name"],
        {"kind": {"action": "dtcs:deduplicate", "parameters": {}}},
        parameters={},
        relations={},
        relation_columns={},
    )
    assert query.distinct is True
    assert cols == ["id", "name"]
