# pyright: reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownVariableType=false, reportUnusedFunction=false
"""Regression tests for portable IR correctness bugs fixed in 0.11."""

from __future__ import annotations

from etlantic import Data, Input, Output, Parameter, Transformation
from etlantic.transform import Window
from etlantic.transform import functions as F
from etlantic.transform.column import with_column_assignment
from etlantic.transform.dataframe import input_frame


class Left(Data):
    id: int
    value: int


class Right(Data):
    id: int
    label: str


class Out(Data):
    id: int
    value: int
    label: str


class Sorted(Data):
    id: int
    name: str


def test_join_preserves_both_filtered_branches() -> None:
    class JoinBoth(Transformation):
        left: Input[Left]
        right: Input[Right]
        result: Output[Out]

    @JoinBoth.portable
    def define(left, right):
        return left.filter(F.col("value") > 0).join(
            right.filter(F.col("id") > 0), on="id", how="inner"
        )

    plan = JoinBoth.to_transform_plan()
    # Ensure both filter action ids appear in the plan document.
    dumped = str(plan)
    assert dumped.count("dtcs:filter") >= 2 or "filter" in dumped.lower()
    filter_ids = [
        node["id"]
        for node in plan.get("nodes", [])
        if isinstance(node, dict)
        and isinstance(node.get("kind"), dict)
        and node["kind"].get("action") == "dtcs:filter"
    ]
    # transform-plan/2 uses semanticActions; fall back to scanning nested structure
    if not filter_ids:
        semantic = plan.get("semanticActions") or {}
        filter_ids = [
            key
            for key, value in semantic.items()
            if isinstance(value, dict) and value.get("action") == "dtcs:filter"
        ]
    if not filter_ids:
        # Walk any dict/list tree for action == dtcs:filter with distinct ids
        found: list[str] = []

        def walk(obj: object) -> None:
            if isinstance(obj, dict):
                if obj.get("action") == "dtcs:filter" and "id" in obj:
                    found.append(str(obj["id"]))
                for value in obj.values():
                    walk(value)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(plan)
        filter_ids = found

    assert len(set(filter_ids)) >= 2, f"expected two distinct filters, got {filter_ids}"


def test_sort_string_is_field_ref_not_literal() -> None:
    frame = input_frame("rows", schema_fields=("name",)).sort("name")
    keys = frame.actions[-1].parameters["keys"]
    assert keys[0]["expression"] == {"kind": "fieldRef", "target": "name"}


def test_window_order_by_string_is_field_ref() -> None:
    w = Window.partitionBy("id").orderBy("ts")
    payload = w.to_dict()
    assert payload["orderBy"][0]["expression"] == {
        "kind": "fieldRef",
        "target": "ts",
    }


def test_wrapping_window_preserves_window_metadata() -> None:
    w = Window.partitionBy("id").orderBy(F.col("ts").asc())
    wrapped = F.to_string(F.ntile(4).over(w))
    assert wrapped.window is not None
    assignment = with_column_assignment("name", wrapped)
    assert "window" in assignment
    assert assignment["window"]["partitionBy"] == ["id"]


def test_to_transform_plan_is_deep_copy() -> None:
    class T(Transformation):
        rows: Input[Sorted]
        result: Output[Sorted]

    @T.portable
    def define(rows):
        return rows.select("id", "name")

    plan = T.to_transform_plan()
    fingerprint = T.portable_fingerprint()
    # Mutate returned plan deeply
    if "identity" in plan and isinstance(plan["identity"], dict):
        plan["identity"]["name"] = "mutated"
    else:
        plan["mutated"] = True
    assert T.portable_fingerprint() == fingerprint
    assert T.to_transform_plan() is not plan


def test_parameter_type_maps_from_contract() -> None:
    class P(Transformation):
        rows: Input[Sorted]
        limit: Parameter[int]
        result: Output[Sorted]

    @P.portable
    def define(rows, limit):
        return rows.limit(1)

    # Parameter typing is on COM before export; inspect via builder requirements path
    from etlantic.transform.dtcs_builder import build_com_plan, invoke_portable

    defn = invoke_portable(P, define)
    assert defn is not None
    # After export, parameters live in the portable plan; kind should not force string-only
    # when the COM used integer. Spot-check COM construction directly:
    produced = {"result": input_frame("rows").limit(1)}
    com, _ = build_com_plan(
        transformation_id="t",
        transformation_name="P",
        inputs=list(P.inputs()),
        outputs=list(P.outputs()),
        parameters=list(P.parameters()),
        produced=produced,
    )
    assert com["parameters"]["limit"]["type"]["kind"] == "integer"


def test_window_frame_bounds_are_json_safe() -> None:
    w = Window.orderBy("id").rowsBetween(F.col("id"), Window.currentRow)
    frame = w.to_dict()["frame"]
    assert isinstance(frame["start"], dict)
    assert frame["start"]["kind"] == "fieldRef"
    assert frame["end"] == Window.currentRow
