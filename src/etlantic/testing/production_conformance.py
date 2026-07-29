"""Production envelope conformance helpers (0.34)."""

from __future__ import annotations

from dataclasses import dataclass, field

from etlantic.plugin_trust import is_production_profile
from etlantic.profile import Profile


@dataclass
class ProductionConformanceResult:
    checks: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures


def check_production_profile(profile: Profile) -> ProductionConformanceResult:
    result = ProductionConformanceResult()
    result.checks.append("production_security_mode")
    if not is_production_profile(profile):
        result.failures.append("Profile security_mode is not production")
    result.checks.append("non_empty_allowlist")
    if not dict(profile.plugin_allowlist or {}):
        result.failures.append("Production profile requires non-empty plugin_allowlist")
    return result


def run_production_conformance_suite(profile: Profile) -> ProductionConformanceResult:
    """Run lightweight production profile checks."""
    return check_production_profile(profile)


def assert_production_conformance(profile: Profile) -> None:
    result = run_production_conformance_suite(profile)
    if not result.passed:
        raise AssertionError("; ".join(result.failures))
