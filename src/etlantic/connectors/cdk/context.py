"""Redacted runtime context: SecretRef only, never resolved secret values."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from etlantic.connectors.errors import ConnectorConfigError
from etlantic.secrets import SecretRef


@dataclass(slots=True)
class RedactedRuntimeContext:
    """Run-scoped connector context that holds :class:`SecretRef` only.

    Public key/value pairs are stored in ``values``. Secret material must be
    referenced via ``secret_refs`` — resolved secret *values* are rejected.
    """

    values: dict[str, Any] = field(default_factory=dict)
    secret_refs: dict[str, SecretRef] = field(default_factory=dict)
    run_id: str | None = None
    pipeline_id: str | None = None

    def __post_init__(self) -> None:
        self.values = dict(self.values)
        normalized: dict[str, SecretRef] = {}
        for key, ref in dict(self.secret_refs).items():
            if isinstance(ref, SecretRef):
                normalized[str(key)] = ref
            elif isinstance(ref, Mapping):
                normalized[str(key)] = SecretRef.from_dict(dict(ref))
            else:
                raise ConnectorConfigError(
                    f"secret_refs[{key!r}] must be SecretRef or mapping",
                    code="PMCONN920",
                )
        self.secret_refs = normalized
        self._reject_resolved_secrets(self.values, path="values")

    @staticmethod
    def _reject_resolved_secrets(obj: Any, *, path: str) -> None:
        if isinstance(obj, Mapping):
            for key, child in obj.items():
                key_s = str(key)
                if key_s.lower() in {"secret", "secret_value", "password", "token"}:
                    raise ConnectorConfigError(
                        f"{path} must not contain resolved secret key {key_s!r}",
                        code="PMCONN921",
                    )
                RedactedRuntimeContext._reject_resolved_secrets(
                    child, path=f"{path}.{key_s}"
                )
        elif isinstance(obj, (list, tuple)):
            for index, item in enumerate(obj):
                RedactedRuntimeContext._reject_resolved_secrets(
                    item, path=f"{path}[{index}]"
                )
        elif type(obj).__name__ == "SecretValue":
            raise ConnectorConfigError(
                f"{path} must not hold SecretValue; use SecretRef",
                code="PMCONN922",
            )

    def get(self, key: str, default: Any = None) -> Any:
        if key in self.values:
            return self.values[key]
        return default

    def __getitem__(self, key: str) -> Any:
        return self.values[key]

    def __contains__(self, key: object) -> bool:
        return key in self.values or key in self.secret_refs

    def keys(self) -> Iterator[str]:
        seen: set[str] = set()
        for key in self.values:
            seen.add(key)
            yield key
        for key in self.secret_refs:
            if key not in seen:
                yield key

    def secret_ref(self, name: str) -> SecretRef | None:
        return self.secret_refs.get(name)

    def to_public_dict(self) -> dict[str, Any]:
        """Serialize public context plus secret *references* (never values)."""
        return {
            "run_id": self.run_id,
            "pipeline_id": self.pipeline_id,
            "values": dict(self.values),
            "secret_refs": {k: v.to_dict() for k, v in self.secret_refs.items()},
        }

    def as_mapping(self) -> dict[str, Any]:
        """Flat mapping suitable for connector ``context=`` arguments."""
        out = dict(self.values)
        if self.run_id is not None:
            out.setdefault("run_id", self.run_id)
        if self.pipeline_id is not None:
            out.setdefault("pipeline_id", self.pipeline_id)
        if self.secret_refs:
            out["secret_refs"] = {k: v.to_dict() for k, v in self.secret_refs.items()}
        return out

    def __repr__(self) -> str:
        ref_names = sorted(self.secret_refs)
        value_keys = sorted(str(k) for k in self.values)
        return (
            f"RedactedRuntimeContext(run_id={self.run_id!r}, "
            f"pipeline_id={self.pipeline_id!r}, "
            f"value_keys={value_keys!r}, "
            f"secret_ref_names={ref_names!r})"
        )


__all__ = ["RedactedRuntimeContext"]
