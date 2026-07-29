"""Medallion profile templates composing core production envelopes."""

from __future__ import annotations

from typing import Any

from etlantic.profile import (
    Profile,
    development_profile,
    production_profile,
    test_profile,
)


def medallion_development_profile(**overrides: Any) -> Profile:
    """Development profile with medallion observability defaults."""
    base = development_profile(
        name="medallion-development",
        observability_providers={"console": "json-console"},
        run_history_provider="file",
        event_consumers={"trends": "memory-trend"},
        observability_delivery="best_effort",
        metadata={
            "plugin:medallantic": {
                "accept_rates": {"bronze": 0.0, "silver": 0.95, "gold": 0.98},
            }
        },
    )
    return base.with_updates(**overrides) if overrides else base


def medallion_test_profile(**overrides: Any) -> Profile:
    """Test profile with strict validation and in-memory history."""
    base = test_profile(
        name="medallion-test",
        observability_providers={"console": "json-console"},
        run_history_provider="memory",
        observability_delivery="best_effort",
        metadata={
            "plugin:medallantic": {
                "accept_rates": {"bronze": 0.0, "silver": 0.95, "gold": 0.98},
            }
        },
    )
    return base.with_updates(**overrides) if overrides else base


def medallion_production_profile(**overrides: Any) -> Profile:
    """Production template — requires explicit plugin allowlist before deploy."""
    base = production_profile(
        name="medallion-production",
        observability_providers={"console": "json-console"},
        run_history_provider="file",
        observability_delivery="durable_audit",
        metadata={
            "plugin:medallantic": {
                "accept_rates": {"bronze": 0.0, "silver": 0.95, "gold": 0.98},
            }
        },
    )
    return base.with_updates(**overrides) if overrides else base
