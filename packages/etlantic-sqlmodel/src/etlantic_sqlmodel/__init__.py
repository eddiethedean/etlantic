"""etlantic-sqlmodel — ContractModel ↔ SQLModel bridge (no sessions)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, get_args, get_origin

from sqlmodel.main import SQLModelMetaclass

from etlantic.contracts import Data, is_data_contract_type
from etlantic.dataframe.helpers import logical_type_from_annotation
from etlantic.diagnostics import Diagnostic, Severity, ValidationReport
from etlantic.schema_drift import (
    NormalizedField,
    NormalizedSchema,
    diff_normalized_schemas,
    normalize_schema_from_fields,
    normalize_schema_from_model,
)
from sqlmodel import Field, SQLModel

__version__ = "0.21.0"

__all__ = [
    "SqlModelIntegrationPlugin",
    "__version__",
    "compare_metadata",
    "contract_to_sqlmodel",
    "contract_to_sqlmodel_source",
    "create_plugin",
    "run_conformance_checks",
    "sqlmodel_to_contract",
]

_PYTHON_FROM_LOGICAL: dict[str, type[Any]] = {
    "string": str,
    "str": str,
    "integer": int,
    "int": int,
    "number": float,
    "float": float,
    "boolean": bool,
    "bool": bool,
    "timestamp": datetime,
    "datetime": datetime,
    "date": date,
    "decimal": Decimal,
}


def contract_to_sqlmodel(
    contract_cls: type[Data],
    *,
    table_name: str | None = None,
    primary_key: tuple[str, ...] | None = None,
) -> type[SQLModel]:
    """Generate a SQLModel table class from a ``Data`` / ContractModel class."""
    if not is_data_contract_type(contract_cls):
        raise TypeError("Expected a Data / ContractModel subclass")

    resolved_table = table_name or _default_table_name(contract_cls)
    pk_fields = set(primary_key or ())
    annotations: dict[str, Any] = {}
    attrs: dict[str, Any] = {
        "__tablename__": resolved_table,
        "__table_args__": {"extend_existing": True},
        "__annotations__": annotations,
    }
    for name, field_info in contract_cls.model_fields.items():
        python_type = _python_type_from_annotation(field_info.annotation)
        if not field_info.is_required():
            python_type = python_type | None
        annotations[name] = python_type
        if name in pk_fields:
            attrs[name] = Field(primary_key=True)
        elif field_info.default is not ...:
            attrs[name] = Field(default=field_info.default)
        elif not field_info.is_required():
            attrs[name] = Field(default=None)

    model_name = f"{contract_cls.__name__}Table"
    return SQLModelMetaclass(model_name, (SQLModel,), attrs, table=True)


def contract_to_sqlmodel_source(
    contract_cls: type[Data],
    *,
    table_name: str | None = None,
    primary_key: tuple[str, ...] | None = None,
) -> str:
    """Generate importable SQLModel source for a ``Data`` / ContractModel class."""
    if not is_data_contract_type(contract_cls):
        raise TypeError("Expected a Data / ContractModel subclass")

    resolved_table = table_name or _default_table_name(contract_cls)
    pk_fields = set(primary_key or ())
    model_name = f"{contract_cls.__name__}Table"
    imports: set[str] = set()
    field_lines: list[str] = []

    for name, field_info in contract_cls.model_fields.items():
        python_type = _python_type_from_annotation(field_info.annotation)
        type_name, extra_imports = _annotation_source(python_type, optional=False)
        imports.update(extra_imports)
        optional = not field_info.is_required()
        if optional:
            type_name = f"{type_name} | None"
        if name in pk_fields:
            field_lines.append(f"    {name}: {type_name} = Field(primary_key=True)")
        elif field_info.default is not ...:
            default_repr = _default_source(field_info.default, imports)
            field_lines.append(
                f"    {name}: {type_name} = Field(default={default_repr})"
            )
        elif optional:
            field_lines.append(f"    {name}: {type_name} = Field(default=None)")
        else:
            field_lines.append(f"    {name}: {type_name}")

    import_lines = ["from sqlmodel import Field, SQLModel"]
    if "datetime" in imports:
        import_lines.insert(0, "from datetime import datetime")
    if "date" in imports:
        import_lines.insert(0, "from datetime import date")
    if "Decimal" in imports:
        import_lines.insert(0, "from decimal import Decimal")
    # De-duplicate datetime imports when both date and datetime needed
    if "datetime" in imports and "date" in imports:
        import_lines = [
            line
            for line in import_lines
            if line
            not in {"from datetime import date", "from datetime import datetime"}
        ]
        import_lines.insert(0, "from datetime import date, datetime")

    body = "\n".join(field_lines) if field_lines else "    pass"
    return (
        "\n".join(import_lines)
        + "\n\n\n"
        + f"class {model_name}(SQLModel, table=True):\n"
        + f'    __tablename__ = "{resolved_table}"\n'
        + f"{body}\n"
    )


def _annotation_source(
    python_type: type[Any], *, optional: bool
) -> tuple[str, set[str]]:
    _ = optional
    mapping = {
        str: ("str", set()),
        int: ("int", set()),
        float: ("float", set()),
        bool: ("bool", set()),
        datetime: ("datetime", {"datetime"}),
        date: ("date", {"date"}),
        Decimal: ("Decimal", {"Decimal"}),
    }
    if python_type in mapping:
        return mapping[python_type]
    return ("str", set())


def _default_source(value: Any, imports: set[str]) -> str:
    if isinstance(value, Decimal):
        imports.add("Decimal")
        return f"Decimal({str(value)!r})"
    if isinstance(value, datetime):
        imports.add("datetime")
        return repr(value)
    if isinstance(value, date):
        imports.add("date")
        return repr(value)
    return repr(value)


def sqlmodel_to_contract(model_cls: type[Any]) -> dict[str, Any]:
    """Extract draft contract metadata from a SQLModel table class."""
    if not _is_sqlmodel_table(model_cls):
        raise TypeError("Expected a SQLModel table class")

    fields: list[dict[str, Any]] = []
    table = getattr(model_cls, "__table__", None)
    columns = {str(col.name): col for col in table.columns} if table is not None else {}

    for name, field_info in getattr(model_cls, "model_fields", {}).items():
        column = columns.get(name)
        logical = logical_type_from_annotation(field_info.annotation)
        fields.append(
            {
                "name": name,
                "logical_type": logical,
                "required": field_info.is_required(),
                "nullable": _is_nullable(field_info.annotation)
                or (bool(column.nullable) if column is not None else False),
                "primary_key": bool(getattr(column, "primary_key", False)),
                "sql_type": str(column.type) if column is not None else None,
            }
        )

    return {
        "class_name": model_cls.__name__,
        "table_name": getattr(model_cls, "__tablename__", None),
        "schema": getattr(table, "schema", None) if table is not None else None,
        "fields": fields,
        "source": "sqlmodel",
        "review_required": _review_flags(fields),
    }


def compare_metadata(
    left: Any,
    right: Any,
) -> ValidationReport:
    """Compare contract and SQLModel metadata; return a ValidationReport."""
    left_schema = _canonicalize_schema(
        _coerce_normalized_schema(left, label="left"),
    )
    right_schema = _canonicalize_schema(
        _coerce_normalized_schema(right, label="right"),
    )
    change_set = diff_normalized_schemas(left_schema, right_schema)

    diagnostics: list[Diagnostic] = []
    for change in change_set.changes:
        severity = (
            Severity.ERROR
            if change.impact.value in {"breaking", "unknown"}
            else Severity.WARNING
        )
        diagnostics.append(
            Diagnostic(
                code="PSQL410",
                severity=severity,
                message=(
                    f"{change.kind} at {change.path}: "
                    f"{change.previous!r} -> {change.current!r}"
                ),
                path=(change.path,),
                metadata={
                    "impact": change.impact.value,
                    "previous": change.previous,
                    "current": change.current,
                },
            )
        )

    if not diagnostics and left_schema.fingerprint() == right_schema.fingerprint():
        diagnostics.append(
            Diagnostic(
                code="PSQL411",
                severity=Severity.INFO,
                message="Metadata fingerprints match.",
            )
        )

    return ValidationReport.from_diagnostics(diagnostics, phases=("sqlmodel",))


def create_plugin() -> SqlModelIntegrationPlugin:
    """Entry-point factory for tooling and conformance helpers."""
    return SqlModelIntegrationPlugin()


class SqlModelIntegrationPlugin:
    """Schema bridge helpers without ORM sessions or migrations."""

    name = "etlantic-sqlmodel"
    version = __version__

    def contract_to_table(
        self,
        contract_cls: type[Data],
        *,
        table_name: str | None = None,
        primary_key: tuple[str, ...] | None = None,
    ) -> type[SQLModel]:
        return contract_to_sqlmodel(
            contract_cls,
            table_name=table_name,
            primary_key=primary_key,
        )

    def table_metadata(self, model_cls: type[Any]) -> dict[str, Any]:
        return sqlmodel_to_contract(model_cls)

    def compare(
        self,
        left: Any,
        right: Any,
    ) -> ValidationReport:
        return compare_metadata(left, right)


def run_conformance_checks(
    contract_cls: type[Data],
    *,
    table_name: str | None = None,
    primary_key: tuple[str, ...] | None = None,
) -> ValidationReport:
    """Round-trip contract → SQLModel → metadata and compare schemas."""
    model = contract_to_sqlmodel(
        contract_cls,
        table_name=table_name,
        primary_key=primary_key,
    )
    metadata = sqlmodel_to_contract(model)
    report = compare_metadata(contract_cls, model)
    if metadata.get("review_required"):
        extra = ValidationReport.from_diagnostics(
            [
                Diagnostic(
                    code="PSQL412",
                    severity=Severity.WARNING,
                    message=(
                        "SQLModel metadata includes fields requiring human review."
                    ),
                    metadata={"review_required": metadata["review_required"]},
                )
            ],
            phases=("sqlmodel",),
        )
        return report.merge(extra)
    return report


_CANONICAL_LOGICAL: dict[str, str] = {
    "int": "integer",
    "integer": "integer",
    "str": "string",
    "string": "string",
    "float": "number",
    "number": "number",
    "bool": "boolean",
    "boolean": "boolean",
    "datetime": "timestamp",
    "timestamp": "timestamp",
    "date": "date",
    "decimal": "decimal",
}


def _canonical_logical(logical: str) -> str:
    return _CANONICAL_LOGICAL.get(logical, logical)


def _canonicalize_schema(schema: NormalizedSchema) -> NormalizedSchema:
    fields = tuple(
        NormalizedField(
            name=field.name,
            logical_type=_canonical_logical(field.logical_type),
            required=field.required,
            nullable=field.nullable,
            metadata=dict(field.metadata),
        )
        for field in schema.fields
    )
    return NormalizedSchema(
        identity=schema.identity,
        fields=fields,
        metadata=dict(schema.metadata),
    )


def _coerce_normalized_schema(value: Any, *, label: str) -> NormalizedSchema:
    if isinstance(value, NormalizedSchema):
        return value
    if is_data_contract_type(value):
        return normalize_schema_from_model(value, identity=f"{label}:contract")
    if _is_sqlmodel_table(value):
        metadata = sqlmodel_to_contract(value)
        identity = (
            f"{label}:sqlmodel:"
            f"{metadata.get('table_name') or getattr(value, '__name__', 'table')}"
        )
        return normalize_schema_from_fields(metadata["fields"], identity=identity)
    if isinstance(value, dict) and "fields" in value:
        identity = str(value.get("identity") or f"{label}:metadata")
        return normalize_schema_from_fields(list(value["fields"]), identity=identity)
    raise TypeError(
        f"Unsupported {label} metadata type {type(value)!r}; "
        "expected Data contract, SQLModel table, NormalizedSchema, or field dict."
    )


def _is_sqlmodel_table(model_cls: Any) -> bool:
    return (
        isinstance(model_cls, type)
        and issubclass(model_cls, SQLModel)
        and getattr(model_cls, "__tablename__", None) is not None
    )


def _default_table_name(contract_cls: type[Data]) -> str:
    name = contract_cls.__name__
    if name.endswith("Model"):
        name = name[: -len("Model")]
    return _snake_case(name)


def _snake_case(name: str) -> str:
    chars: list[str] = []
    for index, char in enumerate(name):
        if char.isupper() and index > 0:
            chars.append("_")
        chars.append(char.lower())
    return "".join(chars)


def _python_type_from_annotation(annotation: Any) -> type[Any]:
    origin = get_origin(annotation)
    if origin is not None:
        args = get_args(annotation)
        non_none = [arg for arg in args if arg is not type(None)]
        if non_none:
            return _python_type_from_annotation(non_none[0])
    if isinstance(annotation, type):
        return annotation
    logical = logical_type_from_annotation(annotation)
    return _PYTHON_FROM_LOGICAL.get(logical, str)


def _is_nullable(annotation: Any) -> bool:
    origin = get_origin(annotation)
    if origin is None:
        return False
    return any(arg is type(None) for arg in get_args(annotation))


def _review_flags(fields: list[dict[str, Any]]) -> list[str]:
    flags: list[str] = []
    for field in fields:
        logical = str(field.get("logical_type") or "")
        if logical in {"object", "array", "unknown"}:
            flags.append(f"{field['name']}:unsupported_logical_type")
        if field.get("primary_key") and logical not in {
            "integer",
            "int",
            "string",
            "str",
        }:
            flags.append(f"{field['name']}:nonstandard_primary_key")
    return flags
