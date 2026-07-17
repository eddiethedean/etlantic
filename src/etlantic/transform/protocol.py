"""Protocol constants, budgets, and portable definition records."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

AUTHORING_PROFILE = "etlantic.transform/1"
PLAN_PROTOCOL = "dtcs.transform-plan/2"
DTCS_SPEC_VERSION = "3.0.0"

DEFAULT_PROFILE = "dtcs:profile/portable-relational-kernel/2"
KERNEL_PROFILE_V1 = "dtcs:profile/portable-relational-kernel/1"
KERNEL_PROFILE_V2 = "dtcs:profile/portable-relational-kernel/2"
RELATIONAL_PROFILE_V1 = "dtcs:profile/portable-relational/1"
RELATIONAL_PROFILE_V2 = "dtcs:profile/portable-relational/2"

PROFILE_STRING_ADVANCED = "dtcs:profile/portable-string-advanced/1"
PROFILE_CONVERSION = "dtcs:profile/portable-conversion/1"
PROFILE_STATISTICS = "dtcs:profile/portable-statistics/1"
PROFILE_COMPLEX_VALUES = "dtcs:profile/portable-complex-values/1"
PROFILE_COMPLEX_TYPES = "dtcs:profile/portable-complex-types/1"
PROFILE_RESHAPE = "dtcs:profile/portable-reshape/1"
PROFILE_RELATIONAL_EXTENDED = "dtcs:profile/portable-relational-extended/1"
PROFILE_TEMPORAL_IANA = "dtcs:profile/portable-temporal-iana/1"
PROFILE_NONDETERMINISTIC = "dtcs:profile/portable-nondeterministic/1"
PROFILE_WINDOW_V1 = "dtcs:profile/portable-window/1"
PROFILE_WINDOW_V2 = "dtcs:profile/portable-window/2"

REGISTRY_VERSIONS = {
    "actions": "3.0.0",
    "functions": "3.0.0",
    "operators": "1.0.0",
    "types": "1.0.0",
}


@dataclass(frozen=True, slots=True)
class TransformBudgets:
    """Security and resource budgets for portable definition building."""

    max_document_bytes: int = 8 * 1024 * 1024
    max_depth: int = 128
    max_nodes: int = 100_000
    max_literal_chars: int = 1_048_576
    max_collection_items: int = 10_000


DEFAULT_BUDGETS = TransformBudgets()


class Missing:
    """Sentinel for the DTCS missing value state."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "MISSING"


class Invalid:
    """Sentinel for the DTCS invalid value state."""

    __slots__ = ("reason",)

    def __init__(self, reason: str | None = None) -> None:
        self.reason = reason

    def __repr__(self) -> str:
        if self.reason is None:
            return "INVALID"
        return f"INVALID({self.reason!r})"


MISSING = Missing()
INVALID = Invalid()


@dataclass(frozen=True, slots=True)
class PortableDefinition:
    """Built portable transformation plan and authoring metadata."""

    transformation_id: str
    authoring_profile: str
    plan: dict[str, Any]
    fingerprint: str
    requirements: dict[str, list[str]]
    diagnostics: tuple[Any, ...] = ()
    extensions: dict[str, Any] = field(default_factory=dict)


@dataclass
class PortableDefinitionRecord:
    """Registered portable authoring callable and cached build artifact."""

    callable: Callable[..., Any]
    definition: PortableDefinition | None = None
    build_error: str | None = None
