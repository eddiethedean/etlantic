"""Read-only inspection of schemas required by the managed SQLModel backend."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from importlib import import_module
from typing import Any, cast

from sqlalchemy import Table, UniqueConstraint, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from etlantic_sqlmodel.control_plane.durable_stores import DURABLE_TABLES
from etlantic_sqlmodel.control_plane.input_resource_stores import INPUT_RESOURCE_TABLES
from etlantic_sqlmodel.control_plane.models import (
    DefinitionRow,
    EventIdempotencyRow,
    EventRow,
    RunReportRow,
    SubmissionRow,
)
from etlantic_sqlmodel.control_plane.registry_stores import REGISTRY_TABLES
from etlantic_sqlmodel.control_plane.schedule_stores import SCHEDULE_TABLES

SCHEMA_REQUIREMENTS_SCHEMA = "etlantic_sqlmodel.schema_requirements/2"
_VERSION_TABLE = "etlantic_sqlmodel_schema_version"
_SAFE_VERSION = re.compile(r"[0-9]{3}_[a-z0-9][a-z0-9_.-]{0,59}\Z")


def _model_table(model: Any) -> Table:
    return cast(Table, model.__table__)


def _reflected_key(value: object) -> tuple[str, ...] | None:
    if not isinstance(value, (list, tuple)):
        return None
    names = cast(Sequence[object], value)
    if any(not isinstance(name, str) for name in names):
        return None
    return tuple(cast(str, name) for name in names)


def _has_usable_default(column: Mapping[str, Any]) -> bool:
    """Return whether a reflected default can satisfy a required new column."""
    value = column.get("default")
    if value is None:
        return False
    if not isinstance(value, str):
        return True
    unwrapped = value.strip().rstrip(";").strip()

    def strip_outer_parentheses(expression: str) -> str:
        while expression.startswith("(") and expression.endswith(")"):
            depth = 0
            closes_at_end = False
            for index, character in enumerate(expression):
                if character == "(":
                    depth += 1
                elif character == ")":
                    depth -= 1
                    if depth == 0:
                        closes_at_end = index == len(expression) - 1
                        break
            if not closes_at_end:
                break
            expression = expression[1:-1].strip()
        return expression

    unwrapped = strip_outer_parentheses(unwrapped)
    base, cast_separator, _cast_type = unwrapped.partition("::")
    if cast_separator and strip_outer_parentheses(base.strip()).casefold() == "null":
        return False
    if unwrapped.casefold() == "null":
        return False
    cast_expression = re.fullmatch(
        r"cast\s*\(\s*(.*?)\s+as\s+.+\)", unwrapped, re.IGNORECASE
    )
    return not (
        cast_expression is not None
        and strip_outer_parentheses(cast_expression.group(1).strip()).casefold()
        == "null"
    )


class SchemaCompatibility(StrEnum):
    """Safe, database-observed schema compatibility classifications."""

    FRESH = "fresh"
    BEHIND = "behind"
    COMPATIBLE = "compatible"
    UNKNOWN_OR_AHEAD = "unknown_or_ahead"
    PARTIAL_OR_CORRUPT = "partial_or_corrupt"
    UNREACHABLE = "unreachable"


@dataclass(frozen=True, slots=True)
class SchemaObjectRequirement:
    name: str
    columns: tuple[str, ...]
    primary_key: tuple[str, ...] = ()
    unique_keys: tuple[tuple[str, ...], ...] = ()
    non_nullable_columns: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "columns": list(self.columns),
            "primary_key": list(self.primary_key),
            "unique_keys": [list(key) for key in self.unique_keys],
            "non_nullable_columns": list(self.non_nullable_columns),
        }


@dataclass(frozen=True, slots=True)
class SchemaRequirements:
    schema: str
    provider: str
    required_version: str
    objects: tuple[SchemaObjectRequirement, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "provider": self.provider,
            "required_version": self.required_version,
            "objects": [item.to_dict() for item in self.objects],
        }


@dataclass(frozen=True, slots=True)
class SchemaInspectionResult:
    schema: str
    compatibility: SchemaCompatibility
    required_version: str
    observed_version: str | None
    reason_code: str
    missing_objects: tuple[str, ...] = ()
    missing_columns: tuple[str, ...] = ()
    missing_constraints: tuple[str, ...] = ()
    incompatible_columns: tuple[str, ...] = ()

    @property
    def compatible(self) -> bool:
        return self.compatibility is SchemaCompatibility.COMPATIBLE

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "compatibility": self.compatibility.value,
            "compatible": self.compatible,
            "required_version": self.required_version,
            "observed_version": self.observed_version,
            "reason_code": self.reason_code,
            "missing_objects": list(self.missing_objects),
            "missing_columns": list(self.missing_columns),
            "missing_constraints": list(self.missing_constraints),
            "incompatible_columns": list(self.incompatible_columns),
        }


def _required_objects() -> tuple[SchemaObjectRequirement, ...]:
    tables: set[Table] = {
        *(
            _model_table(model)
            for model in (
                DefinitionRow,
                SubmissionRow,
                EventRow,
                EventIdempotencyRow,
            )
        ),
        *(_model_table(model) for model in REGISTRY_TABLES),
        *(_model_table(model) for model in DURABLE_TABLES),
        *(_model_table(model) for model in SCHEDULE_TABLES),
        _model_table(RunReportRow),
    }
    tables.update(INPUT_RESOURCE_TABLES)
    requirements: list[SchemaObjectRequirement] = []
    for table in sorted(tables, key=lambda value: value.name):
        unique_keys = {
            tuple(column.name for column in constraint.columns)
            for constraint in table.constraints
            if isinstance(constraint, UniqueConstraint)
        }
        unique_keys.update(
            tuple(column.name for column in index.columns)
            for index in table.indexes
            if index.unique
        )
        requirements.append(
            SchemaObjectRequirement(
                name=table.name,
                columns=tuple(sorted(column.name for column in table.columns)),
                primary_key=tuple(column.name for column in table.primary_key.columns),
                unique_keys=tuple(sorted(unique_keys)),
                non_nullable_columns=tuple(
                    sorted(
                        column.name for column in table.columns if not column.nullable
                    )
                ),
            )
        )
    return tuple(requirements)


def schema_requirements() -> SchemaRequirements:
    """Return the provider-owned structural floor for managed backend stores."""
    migrations = import_module("etlantic_sqlmodel.migrations")
    return SchemaRequirements(
        schema=SCHEMA_REQUIREMENTS_SCHEMA,
        provider="etlantic-sqlmodel",
        required_version=str(migrations.VERSIONS[-1]),
        objects=_required_objects(),
    )


def inspect_schema(engine: Engine) -> SchemaInspectionResult:
    """Inspect schema version and required objects without DDL or commits.

    SQLAlchemy metadata lookups and the version SELECT run on a connection.
    Database failures are reduced to a stable, credential-free reason code.
    """
    requirements = schema_requirements()
    migrations = import_module("etlantic_sqlmodel.migrations")
    migration_versions = tuple(migrations.VERSIONS)
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            version_marker_exists = inspector.has_table(_VERSION_TABLE)
            existing_managed = {
                item.name
                for item in requirements.objects
                if inspector.has_table(item.name)
            }
            if not version_marker_exists:
                managed_names = {item.name for item in requirements.objects}
                if existing_managed:
                    return SchemaInspectionResult(
                        schema=requirements.schema,
                        compatibility=SchemaCompatibility.PARTIAL_OR_CORRUPT,
                        required_version=requirements.required_version,
                        observed_version=None,
                        reason_code="version_marker_missing_from_existing_schema",
                        missing_objects=tuple(sorted(managed_names - existing_managed)),
                    )
                return SchemaInspectionResult(
                    schema=requirements.schema,
                    compatibility=SchemaCompatibility.FRESH,
                    required_version=requirements.required_version,
                    observed_version=None,
                    reason_code="schema_not_initialized",
                )

            marker_columns = {
                item["name"] for item in inspector.get_columns(_VERSION_TABLE)
            }
            if not {"id", "version"}.issubset(marker_columns):
                return SchemaInspectionResult(
                    schema=requirements.schema,
                    compatibility=SchemaCompatibility.PARTIAL_OR_CORRUPT,
                    required_version=requirements.required_version,
                    observed_version=None,
                    reason_code="version_marker_malformed",
                )

            rows = connection.execute(
                text(f"SELECT id, version FROM {_VERSION_TABLE} LIMIT 2")
            ).fetchall()
            if len(rows) != 1 or rows[0][0] != 1 or not isinstance(rows[0][1], str):
                return SchemaInspectionResult(
                    schema=requirements.schema,
                    compatibility=SchemaCompatibility.PARTIAL_OR_CORRUPT,
                    required_version=requirements.required_version,
                    observed_version=None,
                    reason_code="version_marker_row_malformed",
                )
            observed = rows[0][1]
            if len(observed) > 64 or not _SAFE_VERSION.fullmatch(observed):
                return SchemaInspectionResult(
                    schema=requirements.schema,
                    compatibility=SchemaCompatibility.UNKNOWN_OR_AHEAD,
                    required_version=requirements.required_version,
                    observed_version=None,
                    reason_code="version_value_invalid",
                )
            if observed not in migration_versions:
                return SchemaInspectionResult(
                    schema=requirements.schema,
                    compatibility=SchemaCompatibility.UNKNOWN_OR_AHEAD,
                    required_version=requirements.required_version,
                    observed_version=observed[:64],
                    reason_code="version_not_recognized_by_provider",
                )
            if observed != requirements.required_version:
                return SchemaInspectionResult(
                    schema=requirements.schema,
                    compatibility=SchemaCompatibility.BEHIND,
                    required_version=requirements.required_version,
                    observed_version=observed,
                    reason_code="schema_upgrade_required",
                )

            missing_objects: list[str] = []
            missing_columns: list[str] = []
            missing_constraints: list[str] = []
            incompatible_columns: list[str] = []
            for requirement in requirements.objects:
                if requirement.name not in existing_managed:
                    missing_objects.append(requirement.name)
                    continue
                column_details = inspector.get_columns(requirement.name)
                observed_columns = {item["name"] for item in column_details}
                observed_nullable = {
                    item["name"]: item.get("nullable") for item in column_details
                }
                missing_columns.extend(
                    f"{requirement.name}.{name}"
                    for name in requirement.columns
                    if name not in observed_columns
                )
                incompatible_columns.extend(
                    f"{requirement.name}.{column_name}"
                    for column_name in requirement.non_nullable_columns
                    if column_name in observed_columns
                    and observed_nullable[column_name] is True
                )
                model_nullable_columns = set(requirement.columns) - set(
                    requirement.non_nullable_columns
                )
                incompatible_columns.extend(
                    f"{requirement.name}.{column_name}"
                    for column_name in model_nullable_columns
                    if column_name in observed_columns
                    and observed_nullable[column_name] is False
                )
                required_names = set(requirement.columns)
                incompatible_columns.extend(
                    f"{requirement.name}.{item['name']}"
                    for item in column_details
                    if item["name"] not in required_names
                    and item.get("nullable") is False
                    and not _has_usable_default(item)
                    and item.get("identity") is None
                    and item.get("computed") is None
                )
                observed_pk = tuple(
                    inspector.get_pk_constraint(requirement.name).get(
                        "constrained_columns"
                    )
                    or ()
                )
                if requirement.primary_key and observed_pk != requirement.primary_key:
                    missing_constraints.append(f"{requirement.name}.<primary_key>")
                observed_unique_keys = {
                    key
                    for item in inspector.get_unique_constraints(requirement.name)
                    if (key := _reflected_key(item.get("column_names"))) is not None
                }
                for item in inspector.get_indexes(requirement.name):
                    dialect_options = item.get("dialect_options")
                    is_partial = isinstance(dialect_options, Mapping) and any(
                        key.casefold().endswith("_where") and value is not None
                        for key, value in dialect_options.items()
                    )
                    if (
                        (item.get("unique") is True or item.get("unique") == 1)
                        and not is_partial
                        and (key := _reflected_key(item.get("column_names")))
                        is not None
                    ):
                        observed_unique_keys.add(key)
                missing_unique = set(requirement.unique_keys) - observed_unique_keys
                missing_constraints.extend(
                    f"{requirement.name}.<unique:{','.join(key)}>"
                    for key in sorted(missing_unique)
                )
            if (
                missing_objects
                or missing_columns
                or missing_constraints
                or incompatible_columns
            ):
                return SchemaInspectionResult(
                    schema=requirements.schema,
                    compatibility=SchemaCompatibility.PARTIAL_OR_CORRUPT,
                    required_version=requirements.required_version,
                    observed_version=observed,
                    reason_code="required_schema_object_missing",
                    missing_objects=tuple(sorted(missing_objects)),
                    missing_columns=tuple(sorted(missing_columns)),
                    missing_constraints=tuple(sorted(missing_constraints)),
                    incompatible_columns=tuple(sorted(incompatible_columns)),
                )
            return SchemaInspectionResult(
                schema=requirements.schema,
                compatibility=SchemaCompatibility.COMPATIBLE,
                required_version=requirements.required_version,
                observed_version=observed,
                reason_code="schema_compatible",
            )
    except (SQLAlchemyError, OSError, RuntimeError):
        return SchemaInspectionResult(
            schema=requirements.schema,
            compatibility=SchemaCompatibility.UNREACHABLE,
            required_version=requirements.required_version,
            observed_version=None,
            reason_code="schema_inspection_failed",
        )


__all__ = [
    "SCHEMA_REQUIREMENTS_SCHEMA",
    "SchemaCompatibility",
    "SchemaInspectionResult",
    "SchemaObjectRequirement",
    "SchemaRequirements",
    "inspect_schema",
    "schema_requirements",
]
