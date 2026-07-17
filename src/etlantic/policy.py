"""Named validation and quality-gate policies."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class PolicyMode(StrEnum):
    """How a policy treats findings."""

    DEFAULT = "default"
    STRICT = "strict"
    PERMISSIVE = "permissive"


@dataclass(frozen=True, slots=True)
class ValidationPolicy:
    """Named validation / quality-gate policy selected by profile or caller."""

    name: str
    mode: PolicyMode = PolicyMode.DEFAULT
    warnings_as_errors: bool = False
    require_implementations: bool = False
    require_bindings: bool = False
    require_published_contract_ids: bool = False
    allowed_capability_fallbacks: frozenset[str] = field(default_factory=frozenset)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize policy."""
        return {
            "name": self.name,
            "mode": self.mode.value,
            "warnings_as_errors": self.warnings_as_errors,
            "require_implementations": self.require_implementations,
            "require_bindings": self.require_bindings,
            "require_published_contract_ids": self.require_published_contract_ids,
            "allowed_capability_fallbacks": sorted(self.allowed_capability_fallbacks),
            "metadata": dict(self.metadata),
        }


DEFAULT_POLICY = ValidationPolicy(name="default", mode=PolicyMode.DEFAULT)
STRICT_POLICY = ValidationPolicy(
    name="strict",
    mode=PolicyMode.STRICT,
    warnings_as_errors=True,
    require_implementations=True,
    require_bindings=True,
)
PERMISSIVE_POLICY = ValidationPolicy(
    name="permissive",
    mode=PolicyMode.PERMISSIVE,
    require_implementations=False,
    require_bindings=False,
)

VALIDATION_POLICIES: dict[str, ValidationPolicy] = {
    "default": DEFAULT_POLICY,
    "strict": STRICT_POLICY,
    "permissive": PERMISSIVE_POLICY,
}


def register_validation_policy(policy: ValidationPolicy) -> ValidationPolicy:
    """Register a named validation policy for later ``resolve_validation_policy``."""
    VALIDATION_POLICIES[policy.name] = policy
    return policy


def resolve_validation_policy(name: str | ValidationPolicy | None) -> ValidationPolicy:
    """Resolve a policy name or object.

    Unknown names fail closed rather than inventing an empty default policy.
    """
    if name is None:
        return DEFAULT_POLICY
    if isinstance(name, ValidationPolicy):
        return name
    key = str(name)
    if key in VALIDATION_POLICIES:
        return VALIDATION_POLICIES[key]
    raise KeyError(
        f"Unknown validation policy {key!r}; register it with "
        "register_validation_policy() or use default/strict/permissive."
    )
