# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false
"""Contract ↔ Spark schema mapping helpers (lossy/unknown never guessed)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, get_args, get_origin

from etlantic.spark.protocol import SchemaCompatibility


@dataclass(frozen=True, slots=True)
class FieldMapping:
    """One field mapping outcome."""

    name: str
    logical_type: str
    spark_type: str | None
    compatibility: SchemaCompatibility
    nullable: bool = True
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "logical_type": self.logical_type,
            "spark_type": self.spark_type,
            "compatibility": self.compatibility.value,
            "nullable": self.nullable,
            "message": self.message,
        }


@dataclass
class SchemaMappingResult:
    """Aggregate contract ↔ Spark schema mapping."""

    fields: list[FieldMapping] = field(default_factory=list)
    overall: SchemaCompatibility = SchemaCompatibility.EXACT
    nested_supported: bool = True
    partition_columns: list[str] = field(default_factory=list)
    evolution_evidence: dict[str, Any] = field(default_factory=dict)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fields": [f.to_dict() for f in self.fields],
            "overall": self.overall.value,
            "nested_supported": self.nested_supported,
            "partition_columns": list(self.partition_columns),
            "evolution_evidence": dict(self.evolution_evidence),
            "diagnostics": list(self.diagnostics),
        }


_PYTHON_TO_LOGICAL: dict[type, str] = {
    int: "integer",
    float: "float",
    bool: "boolean",
    str: "string",
    bytes: "binary",
}

_LOGICAL_TO_SPARK: dict[str, str] = {
    "integer": "LongType",
    "int": "LongType",
    "long": "LongType",
    "float": "DoubleType",
    "double": "DoubleType",
    "boolean": "BooleanType",
    "bool": "BooleanType",
    "string": "StringType",
    "str": "StringType",
    "binary": "BinaryType",
    "bytes": "BinaryType",
    "date": "DateType",
    "timestamp": "TimestampType",
    "decimal": "DecimalType",
    "array": "ArrayType",
    "map": "MapType",
    "struct": "StructType",
}

_SPARK_TO_LOGICAL: dict[str, str] = {
    "LongType": "integer",
    "IntegerType": "integer",
    "ShortType": "integer",
    "ByteType": "integer",
    "DoubleType": "float",
    "FloatType": "float",
    "BooleanType": "boolean",
    "StringType": "string",
    "BinaryType": "binary",
    "DateType": "date",
    "TimestampType": "timestamp",
    "TimestampNTZType": "timestamp",
    "DecimalType": "decimal",
    "ArrayType": "array",
    "MapType": "map",
    "StructType": "struct",
}


def logical_type_from_annotation(annotation: Any) -> str:
    """Best-effort logical type name from a Python annotation."""
    origin = get_origin(annotation)
    if origin is list:
        return "array"
    if origin is dict:
        return "map"
    if annotation in _PYTHON_TO_LOGICAL:
        return _PYTHON_TO_LOGICAL[annotation]
    name = getattr(annotation, "__name__", None) or str(annotation)
    lower = name.lower()
    if "decimal" in lower:
        return "decimal"
    if "date" in lower and "time" not in lower:
        return "date"
    if "time" in lower:
        return "timestamp"
    return "unknown"


def spark_type_name(logical: str) -> str | None:
    """Map a logical type to a Spark type class name, or None if unknown."""
    return _LOGICAL_TO_SPARK.get(logical.lower())


def logical_from_spark_type(spark_type: str) -> str:
    """Normalize a Spark type name to a logical type (unknown if unmapped)."""
    base = spark_type.split("(")[0].strip()
    return _SPARK_TO_LOGICAL.get(base, "unknown")


def compare_types(logical: str, spark_type: str | None) -> SchemaCompatibility:
    """Compare logical vs observed Spark type without guessing."""
    if spark_type is None:
        return SchemaCompatibility.UNKNOWN
    expected = spark_type_name(logical)
    observed_logical = logical_from_spark_type(spark_type)
    if expected is None or observed_logical == "unknown":
        return SchemaCompatibility.UNKNOWN
    if expected.split("(")[0] == spark_type.split("(")[0]:
        return SchemaCompatibility.EXACT
    if logical == observed_logical:
        return SchemaCompatibility.COMPATIBLE
    if logical in {"integer", "int"} and observed_logical == "integer":
        return SchemaCompatibility.COMPATIBLE
    if logical == "float" and observed_logical == "float":
        return SchemaCompatibility.COMPATIBLE
    if observed_logical == "string" and logical != "string":
        return SchemaCompatibility.LOSSY
    if logical != observed_logical:
        return SchemaCompatibility.UNSUPPORTED
    return SchemaCompatibility.COMPATIBLE


def map_contract_schema(
    contract_type: type[Any],
    *,
    observed: Mapping[str, str] | None = None,
) -> SchemaMappingResult:
    """Map a ContractModel / Pydantic model to Spark types with explicit outcomes."""
    fields: list[FieldMapping] = []
    worst = SchemaCompatibility.EXACT
    rank = {
        SchemaCompatibility.EXACT: 0,
        SchemaCompatibility.COMPATIBLE: 1,
        SchemaCompatibility.LOSSY: 2,
        SchemaCompatibility.UNKNOWN: 3,
        SchemaCompatibility.UNSUPPORTED: 4,
    }
    model_fields = getattr(contract_type, "model_fields", None) or {}
    for name, finfo in model_fields.items():
        annotation = getattr(finfo, "annotation", Any)
        origin = get_origin(annotation)
        args = get_args(annotation)
        nullable = True
        inner = annotation
        if origin is not None and type(None) in args:
            non_none = [a for a in args if a is not type(None)]
            inner = non_none[0] if non_none else Any
            nullable = True
        logical = logical_type_from_annotation(inner)
        spark = spark_type_name(logical)
        obs = (observed or {}).get(name)
        if obs is not None:
            compat = compare_types(logical, obs)
            spark = obs
        elif spark is None:
            compat = SchemaCompatibility.UNKNOWN
        else:
            compat = SchemaCompatibility.EXACT
        message = None
        if compat is SchemaCompatibility.LOSSY:
            message = f"Field {name!r}: logical {logical} → Spark {spark} is lossy"
        elif compat is SchemaCompatibility.UNKNOWN:
            message = f"Field {name!r}: unknown Spark mapping for {logical}"
        elif compat is SchemaCompatibility.UNSUPPORTED:
            message = f"Field {name!r}: unsupported mapping {logical} ↔ {spark}"
        fields.append(
            FieldMapping(
                name=name,
                logical_type=logical,
                spark_type=spark,
                compatibility=compat,
                nullable=nullable,
                message=message,
            )
        )
        if rank[compat] > rank[worst]:
            worst = compat

    diagnostics = [
        {
            "code": "PMSPARK220",
            "severity": (
                "warning" if f.compatibility is SchemaCompatibility.LOSSY else "error"
            ),
            "message": f.message,
            "field": f.name,
            "compatibility": f.compatibility.value,
        }
        for f in fields
        if f.message
        and f.compatibility
        in {
            SchemaCompatibility.LOSSY,
            SchemaCompatibility.UNKNOWN,
            SchemaCompatibility.UNSUPPORTED,
        }
    ]
    return SchemaMappingResult(fields=fields, overall=worst, diagnostics=diagnostics)


def observation_from_spark_schema(
    spark_schema: Any,
    *,
    source: str = "spark",
    partition_columns: list[str] | None = None,
) -> dict[str, Any]:
    """Build a normalized schema observation from a Spark StructType-like object."""
    fields_out: list[dict[str, Any]] = []
    type_map: dict[str, str] = {}
    try:
        for field in spark_schema.fields:
            spark_type = field.dataType.simpleString()
            type_name = type(field.dataType).__name__
            logical = logical_from_spark_type(type_name)
            type_map[field.name] = type_name
            fields_out.append(
                {
                    "name": field.name,
                    "logical_type": logical,
                    "spark_type": spark_type,
                    "nullable": bool(field.nullable),
                    "compatibility": (
                        SchemaCompatibility.UNKNOWN.value
                        if logical == "unknown"
                        else SchemaCompatibility.EXACT.value
                    ),
                }
            )
    except Exception as exc:
        return {
            "source": source,
            "fields": [],
            "partition_columns": list(partition_columns or []),
            "diagnostics": [
                {
                    "code": "PMSPARK221",
                    "severity": "warning",
                    "message": f"Spark schema inspection failed: {exc}",
                }
            ],
        }
    return {
        "source": source,
        "fields": fields_out,
        "types": type_map,
        "partition_columns": list(partition_columns or []),
        "nested_supported": True,
    }
