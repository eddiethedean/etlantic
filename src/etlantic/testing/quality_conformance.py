"""Engine-independent portable quality conformance suite (0.30)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from etlantic.quality.evaluate import split_by_quality
from etlantic.quality.model import (
    PORTABLE_QUALITY_CAPABILITIES,
    QualityRuleset,
    rule_compare,
    rule_length,
    rule_membership,
    rule_not_null,
    rule_range,
    rule_regex,
    rule_uniqueness,
)


@dataclass(frozen=True, slots=True)
class QualityFixture:
    """One portable quality conformance case."""

    fixture_id: str
    capability: str
    ruleset: QualityRuleset
    rows: tuple[dict[str, Any], ...]
    accepted_count: int
    rejected_count: int


def quality_fixtures() -> tuple[QualityFixture, ...]:
    """Return the portable-core quality fixture corpus."""
    return (
        QualityFixture(
            fixture_id="not_null_basic",
            capability="quality.not_null",
            ruleset=QualityRuleset(rules=(rule_not_null("id"),)),
            rows=({"id": 1}, {"id": None}, {"id": 2}),
            accepted_count=2,
            rejected_count=1,
        ),
        QualityFixture(
            fixture_id="compare_basic",
            capability="quality.compare",
            ruleset=QualityRuleset(rules=(rule_compare("n", "ge", 3),)),
            rows=({"n": 3}, {"n": 2}, {"n": 10}),
            accepted_count=2,
            rejected_count=1,
        ),
        QualityFixture(
            fixture_id="range_basic",
            capability="quality.range",
            ruleset=QualityRuleset(rules=(rule_range("n", min_value=0, max_value=10),)),
            rows=({"n": 0}, {"n": 11}, {"n": 5}),
            accepted_count=2,
            rejected_count=1,
        ),
        QualityFixture(
            fixture_id="regex_basic",
            capability="quality.regex",
            ruleset=QualityRuleset(rules=(rule_regex("email", r"^[^@]+@[^@]+$"),)),
            rows=(
                {"email": "a@b.com"},
                {"email": "bad"},
                {"email": "c@d.org"},
            ),
            accepted_count=2,
            rejected_count=1,
        ),
        QualityFixture(
            fixture_id="length_basic",
            capability="quality.length",
            ruleset=QualityRuleset(
                rules=(rule_length("s", min_length=2, max_length=4),)
            ),
            rows=({"s": "ab"}, {"s": "a"}, {"s": "abcde"}),
            accepted_count=1,
            rejected_count=2,
        ),
        QualityFixture(
            fixture_id="membership_basic",
            capability="quality.membership",
            ruleset=QualityRuleset(rules=(rule_membership("color", ["red", "blue"]),)),
            rows=({"color": "red"}, {"color": "green"}, {"color": "blue"}),
            accepted_count=2,
            rejected_count=1,
        ),
        QualityFixture(
            fixture_id="uniqueness_basic",
            capability="quality.uniqueness",
            ruleset=QualityRuleset(rules=(rule_uniqueness("id"),)),
            rows=({"id": 1}, {"id": 2}, {"id": 1}),
            accepted_count=2,
            rejected_count=1,
        ),
    )


def fixtures_for_capabilities(
    advertised: frozenset[str] | set[str],
) -> tuple[QualityFixture, ...]:
    """Return fixtures whose capability is advertised by the engine."""
    return tuple(fx for fx in quality_fixtures() if fx.capability in advertised)


def assert_quality_fixture(fixture: QualityFixture) -> dict[str, Any]:
    """Run one fixture through the portable evaluator and assert counts."""
    valid, invalid, diagnostics = split_by_quality(list(fixture.rows), fixture.ruleset)
    assert len(valid) == fixture.accepted_count, (
        f"{fixture.fixture_id}: accepted {len(valid)} != {fixture.accepted_count}"
    )
    assert len(invalid) == fixture.rejected_count, (
        f"{fixture.fixture_id}: rejected {len(invalid)} != {fixture.rejected_count}"
    )
    assert len(diagnostics) == fixture.rejected_count
    return {
        "fixture_id": fixture.fixture_id,
        "accepted": len(valid),
        "rejected": len(invalid),
        "capability": fixture.capability,
    }


def run_quality_conformance_suite(
    *,
    advertised_capabilities: frozenset[str] | set[str] | None = None,
) -> list[dict[str, Any]]:
    """Run portable quality fixtures for advertised capabilities.

    When ``advertised_capabilities`` is None, runs the full portable core set.
    Every advertised portable quality capability must have a fixture.
    """
    advertised = (
        frozenset(advertised_capabilities)
        if advertised_capabilities is not None
        else PORTABLE_QUALITY_CAPABILITIES
    )
    portable = PORTABLE_QUALITY_CAPABILITIES & advertised
    covered = {fx.capability for fx in quality_fixtures()}
    missing = sorted(portable - covered)
    if missing:
        raise AssertionError(
            f"Advertised quality capabilities lack fixtures: {missing}"
        )
    results = []
    for fixture in fixtures_for_capabilities(advertised):
        results.append(assert_quality_fixture(fixture))
    return results
