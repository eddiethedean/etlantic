"""Relational profile /1↔/2 alias matching (0.13)."""

from __future__ import annotations

from etlantic.transform.capabilities import match_requirements
from etlantic.transform.compiler import TransformCapabilities
from etlantic.transform.protocol import (
    KERNEL_PROFILE_V1,
    RELATIONAL_PROFILE_V1,
    RELATIONAL_PROFILE_V2,
)


def test_relational_v2_requirement_satisfied_by_v1_claim() -> None:
    caps = TransformCapabilities(
        profiles=frozenset({KERNEL_PROFILE_V1, RELATIONAL_PROFILE_V1}),
        actions=frozenset({"dtcs:join"}),
        functions=frozenset(),
    )
    report = match_requirements(
        {
            "profiles": [RELATIONAL_PROFILE_V1, RELATIONAL_PROFILE_V2],
            "actions": ["dtcs:join"],
            "functions": [],
        },
        caps,
    )
    assert report.supported is True


def test_relational_v2_not_granted_without_v1_claim() -> None:
    caps = TransformCapabilities(
        profiles=frozenset({KERNEL_PROFILE_V1}),
        actions=frozenset({"dtcs:filter"}),
        functions=frozenset(),
    )
    report = match_requirements(
        {
            "profiles": [RELATIONAL_PROFILE_V2],
            "actions": [],
            "functions": [],
        },
        caps,
    )
    assert report.supported is False
    assert any("portable-relational/2" in f.requirement for f in report.findings)
