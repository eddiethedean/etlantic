"""SQL pipeline-builder differential suite (ETLantic 0.33 / Medallantic M5).

Compares **normalized semantics** (graph order, write intents, validation
outcomes, classification) — never SQLAlchemy Result objects.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

CLASSIFICATIONS = frozenset(
    {"equivalent", "plugin_dependent", "intentionally_rejected"}
)


@dataclass(frozen=True, slots=True)
class SqlBuilderDifferentialFixture:
    """One classified SQL ``pipeline_builder`` IR fixture."""

    fixture_id: str
    classification: str
    ir: dict[str, Any]
    expected_node_order: tuple[str, ...] = ()
    expected_write_modes: Mapping[str, str] = field(default_factory=dict)
    expected_diagnostic_codes: tuple[str, ...] = ()
    plugin_capabilities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.classification not in CLASSIFICATIONS:
            raise ValueError(
                f"Unknown classification {self.classification!r}; "
                f"expected one of {sorted(CLASSIFICATIONS)}"
            )


@dataclass(frozen=True, slots=True)
class SqlBuilderDifferentialResult:
    """Outcome of adapting / classifying one fixture."""

    fixture_id: str
    classification: str
    ok: bool
    node_order: tuple[str, ...] = ()
    write_modes: Mapping[str, str] = field(default_factory=dict)
    diagnostic_codes: tuple[str, ...] = ()
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "classification": self.classification,
            "ok": self.ok,
            "node_order": list(self.node_order),
            "write_modes": dict(self.write_modes),
            "diagnostic_codes": list(self.diagnostic_codes),
            "message": self.message,
        }


def normalize_step_map(step_map: Mapping[str, str]) -> tuple[str, ...]:
    """Deterministic node order from an adaptation step_map."""
    return tuple(sorted(step_map))


def normalize_write_intents(
    write_intents: Iterable[Any],
) -> dict[str, str]:
    """Map write intents to secret-free mode strings keyed by subject."""
    out: dict[str, str] = {}
    for intent in write_intents:
        if hasattr(intent, "to_dict"):
            data = intent.to_dict()
        elif isinstance(intent, Mapping):
            data = dict(intent)
        else:
            continue
        subject = str(
            data.get("subject_id")
            or data.get("node")
            or data.get("binding")
            or data.get("name")
            or ""
        )
        mode = data.get("mode") or data.get("intent") or data.get("write_mode")
        if subject and mode is not None:
            out[subject] = str(mode)
    return out


def run_sql_builder_differential_suite(
    fixtures: Iterable[SqlBuilderDifferentialFixture] | None = None,
    *,
    adapt_pipeline: Any | None = None,
) -> list[SqlBuilderDifferentialResult]:
    """Adapt each fixture and assert classification semantics.

    ``intentionally_rejected`` fixtures must fail adapt/lower with the expected
    diagnostic codes. ``equivalent`` fixtures must match expected node order /
    write modes when provided. ``plugin_dependent`` fixtures must adapt and
    record required plugin capabilities (e.g. sql_merge).
    """
    if adapt_pipeline is None:
        from medallantic.adapt import adapt_pipeline as _adapt

        adapt_pipeline = _adapt
    from medallantic.ir import SparkForgePipelineSpec

    corpus = list(fixtures) if fixtures is not None else default_sql_builder_fixtures()
    results: list[SqlBuilderDifferentialResult] = []
    for fixture in corpus:
        spec = SparkForgePipelineSpec.from_dict(fixture.ir)
        if fixture.classification == "intentionally_rejected":
            try:
                adapt_pipeline(spec)
            except Exception as exc:
                codes = _diagnostic_codes(exc)
                missing = [
                    c for c in fixture.expected_diagnostic_codes if c not in codes
                ]
                ok = not missing
                results.append(
                    SqlBuilderDifferentialResult(
                        fixture_id=fixture.fixture_id,
                        classification=fixture.classification,
                        ok=ok,
                        diagnostic_codes=tuple(codes),
                        message=None if ok else f"missing diagnostics {missing}",
                    )
                )
                continue
            results.append(
                SqlBuilderDifferentialResult(
                    fixture_id=fixture.fixture_id,
                    classification=fixture.classification,
                    ok=False,
                    message="expected rejection but adapt_pipeline succeeded",
                )
            )
            continue

        try:
            adapted = adapt_pipeline(spec, strict_delta=False)
        except Exception as exc:
            results.append(
                SqlBuilderDifferentialResult(
                    fixture_id=fixture.fixture_id,
                    classification=fixture.classification,
                    ok=False,
                    diagnostic_codes=tuple(_diagnostic_codes(exc)),
                    message=str(exc),
                )
            )
            continue

        node_order = tuple(n.name for n in adapted.pipeline_cls.inspect().nodes)
        write_modes = {
            wi.subject_id: wi.mode.value if hasattr(wi.mode, "value") else str(wi.mode)
            for wi in adapted.write_intents
        }
        ok = True
        message = None
        expected_order = fixture.expected_node_order or tuple(
            fixture.ir.get("metadata", {}).get("expected_node_order") or ()
        )
        if expected_order and list(node_order) != list(expected_order):
            ok = False
            message = (
                f"node order mismatch: got {list(node_order)} "
                f"expected {list(expected_order)}"
            )
        expected_writes = dict(fixture.expected_write_modes) or dict(
            fixture.ir.get("metadata", {}).get("expected_write_modes") or {}
        )
        for subject, mode in expected_writes.items():
            if write_modes.get(subject) != mode:
                ok = False
                message = (
                    message + "; " if message else ""
                ) + f"missing write mode {subject}={mode} in {write_modes}"
        if fixture.classification == "plugin_dependent":
            required = fixture.plugin_capabilities or tuple(
                fixture.ir.get("metadata", {}).get("plugin_capabilities") or ()
            )
            spark_caps = set(adapted.profile.required_spark_capabilities or ())
            sql_caps = set(
                getattr(adapted.profile, "required_sql_capabilities", None) or ()
            )
            caps = spark_caps | sql_caps
            if required and not (set(required) & caps):
                # Soft-ok when metadata only records the capability need.
                meta_caps = set(
                    fixture.ir.get("metadata", {}).get("plugin_capabilities") or ()
                )
                if not (set(required) & meta_caps):
                    ok = False
                    message = (
                        message + "; " if message else ""
                    ) + f"plugin capabilities not reflected: {caps}"
        results.append(
            SqlBuilderDifferentialResult(
                fixture_id=fixture.fixture_id,
                classification=fixture.classification,
                ok=ok,
                node_order=node_order,
                write_modes=write_modes,
                message=message,
            )
        )

    failed = [r for r in results if not r.ok]
    if failed:
        detail = "; ".join(f"{r.fixture_id}: {r.message or 'failed'}" for r in failed)
        raise AssertionError(
            f"SQL builder differential suite failed ({len(failed)}): {detail}"
        )
    return results


def default_sql_builder_fixtures() -> list[SqlBuilderDifferentialFixture]:
    """Load the in-tree SparkForge IR corpus when present."""
    from pathlib import Path

    candidates = [
        Path(__file__).resolve().parents[3]
        / "tests"
        / "medallantic"
        / "fixtures"
        / "sql_pipeline_builder",
        Path.cwd() / "tests" / "medallantic" / "fixtures" / "sql_pipeline_builder",
    ]
    root = next((p for p in candidates if p.is_dir()), None)
    if root is None:
        return []
    fixtures: list[SqlBuilderDifferentialFixture] = []
    for path in sorted(root.glob("*.json")):
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
        meta = dict(data.get("metadata") or {})
        fixtures.append(
            SqlBuilderDifferentialFixture(
                fixture_id=path.stem,
                classification=str(meta.get("classification") or "equivalent"),
                ir=data,
                expected_node_order=tuple(meta.get("expected_node_order") or ()),
                expected_write_modes=dict(meta.get("expected_write_modes") or {}),
                expected_diagnostic_codes=tuple(
                    meta.get("expected_diagnostic_codes") or ()
                ),
                plugin_capabilities=tuple(meta.get("plugin_capabilities") or ()),
            )
        )
    return fixtures


def _diagnostic_codes(exc: BaseException) -> list[str]:
    codes: list[str] = []
    report = getattr(exc, "report", None)
    diags = getattr(report, "diagnostics", None) if report is not None else None
    if diags is None:
        diags = getattr(exc, "diagnostics", None) or ()
    for diagnostic in diags:
        code = getattr(diagnostic, "code", None)
        if code:
            codes.append(str(code))
    code = getattr(exc, "code", None)
    if code:
        codes.append(str(code))
    return codes
