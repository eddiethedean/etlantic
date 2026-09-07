"""Secret-free, default-deny DuckDB configuration."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

from etlantic.runtime.logging import is_sensitive_key


@dataclass(frozen=True, slots=True)
class DuckDBConfig:
    """Runtime configuration that can safely be carried in a plan.

    Paths are logical references until the connection is opened.  The plugin
    never serializes resolved paths or connection handles.
    """

    database: str = ":memory:"
    read_only: bool = False
    threads: int = 1
    memory_limit: str | None = None
    temp_directory: str | None = None
    allowed_paths: tuple[str, ...] = ()
    allowed_directories: tuple[str, ...] = ()
    enable_external_access: bool = False
    autoinstall_known_extensions: bool = False
    autoload_known_extensions: bool = False
    allow_community_extensions: bool = False
    allow_unsigned_extensions: bool = False
    allow_persistent_secrets: bool = False
    allow_unredacted_secrets: bool = False
    max_result_rows: int = 1_000_000
    max_statements: int = 10_000
    metadata: Mapping[str, str] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "database", str(self.database))
        object.__setattr__(
            self,
            "temp_directory",
            str(self.temp_directory) if self.temp_directory is not None else None,
        )
        object.__setattr__(
            self, "allowed_paths", _immutable_paths(self.allowed_paths, "allowed_paths")
        )
        object.__setattr__(
            self,
            "allowed_directories",
            _immutable_paths(self.allowed_directories, "allowed_directories"),
        )
        if not isinstance(self.metadata, Mapping):
            raise TypeError("DuckDB metadata must be a mapping")
        metadata = {str(key): str(value) for key, value in self.metadata.items()}
        object.__setattr__(self, "metadata", MappingProxyType(metadata))
        if self.read_only and self.database == ":memory:":
            raise ValueError("DuckDB read_only mode is unavailable for :memory:")
        if self.threads < 1:
            raise ValueError("DuckDB threads must be positive")
        if self.max_result_rows < 0 or self.max_statements < 1:
            raise ValueError("DuckDB resource limits must be positive")
        if self.enable_external_access:
            raise ValueError("DuckDB external access must remain disabled")
        if self.autoinstall_known_extensions or self.autoload_known_extensions:
            raise ValueError("DuckDB extension installation/loading is disabled")
        if self.allow_community_extensions or self.allow_unsigned_extensions:
            raise ValueError("DuckDB community/unsigned extensions are disabled")
        if self.allow_persistent_secrets or self.allow_unredacted_secrets:
            raise ValueError("DuckDB persistent/unredacted secrets are disabled")
        if any(is_sensitive_key(key) for key in self.metadata):
            raise ValueError("DuckDB metadata keys must not identify secrets")

    @classmethod
    def from_database(
        cls,
        database: str | Path = ":memory:",
        *,
        read_only: bool = False,
        **kwargs: Any,
    ) -> DuckDBConfig:
        return cls(database=str(database), read_only=read_only, **kwargs)

    def to_dict(self) -> dict[str, object]:
        def logical_ref(value: str) -> str:
            digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
            return f"<logical:sha256:{digest}>"

        return {
            "database": (
                self.database
                if self.database == ":memory:"
                else logical_ref(self.database)
            ),
            "read_only": self.read_only,
            "threads": self.threads,
            "memory_limit": self.memory_limit,
            "temp_directory": (
                logical_ref(self.temp_directory) if self.temp_directory else None
            ),
            "allowed_paths": [logical_ref(value) for value in self.allowed_paths],
            "allowed_directories": [
                logical_ref(value) for value in self.allowed_directories
            ],
            "enable_external_access": self.enable_external_access,
            "autoinstall_known_extensions": self.autoinstall_known_extensions,
            "autoload_known_extensions": self.autoload_known_extensions,
            "allow_community_extensions": self.allow_community_extensions,
            "allow_unsigned_extensions": self.allow_unsigned_extensions,
            "allow_persistent_secrets": self.allow_persistent_secrets,
            "allow_unredacted_secrets": self.allow_unredacted_secrets,
            "max_result_rows": self.max_result_rows,
            "max_statements": self.max_statements,
            "metadata": {
                str(key): logical_ref(str(value))
                for key, value in sorted(self.metadata.items())
            },
        }

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def resolve_database(self, *, root: str | Path | None = None) -> str:
        """Resolve a database path only at runtime and within an optional root."""
        if self.database == ":memory:":
            return self.database
        candidate = Path(self.database)
        allowed_files = {Path(path).resolve() for path in self.allowed_paths}
        if candidate.is_absolute() and candidate.resolve() in allowed_files:
            return str(candidate.resolve())
        roots = (
            [Path(root)]
            if root is not None
            else [Path(path) for path in self.allowed_directories]
        )
        if roots:
            for root_path in roots:
                resolved_root = root_path.resolve()
                resolved = (
                    candidate if candidate.is_absolute() else resolved_root / candidate
                ).resolve()
                if resolved == resolved_root or resolved_root in resolved.parents:
                    return str(resolved)
            raise ValueError("DuckDB database path escapes the approved root")
        raise ValueError("file-backed DuckDB requires an approved root")

    def resolve_temp_directory(self) -> str | None:
        """Resolve the spill directory only inside an approved path."""
        if self.temp_directory is None:
            return None
        candidate = Path(self.temp_directory)
        allowed_files = {Path(path).resolve() for path in self.allowed_paths}
        if candidate.is_absolute() and candidate.resolve() in allowed_files:
            return str(candidate.resolve())
        for root in self.allowed_directories:
            root_path = Path(root).resolve()
            resolved = (
                candidate if candidate.is_absolute() else root_path / candidate
            ).resolve()
            if resolved == root_path or root_path in resolved.parents:
                return str(resolved)
        raise ValueError("DuckDB temporary directory requires an approved root")


def _immutable_paths(values: object, field_name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError(f"DuckDB {field_name} must be a sequence of paths")
    return tuple(str(value) for value in values)
