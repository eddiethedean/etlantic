"""Data-contract integration boundary for ContractModel.

Pipelantic docs refer to ``DataContractModel``. The published ContractModel
package exposes ``ContractModel`` as the Pydantic authoring base. This module
aliases that type and provides helpers for identity, compatibility checks, and
ODCS load/save facades.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypeAlias

from contractmodel import ContractModel

# Docs-aligned alias for the ContractModel Pydantic authoring base.
DataContractModel: TypeAlias = ContractModel

__all__ = [
    "ContractModel",
    "DataContractModel",
    "is_data_contract_type",
    "load_data_contract",
    "resolve_contract_type",
    "write_odcs",
]


def is_data_contract_type(obj: Any) -> bool:
    """Return True when ``obj`` is a ContractModel-compatible data-contract class."""
    return isinstance(obj, type) and issubclass(obj, ContractModel)


def resolve_contract_type(annotation: Any) -> type[Any] | None:
    """Extract a data-contract class from a type annotation when possible.

    Returns ``None`` when the annotation is not a concrete ContractModel subclass.
    """
    if is_data_contract_type(annotation):
        return annotation
    origin = getattr(annotation, "__origin__", None)
    if origin is not None:
        args = getattr(annotation, "__args__", ())
        if len(args) == 1 and is_data_contract_type(args[0]):
            return args[0]
    return None


def load_data_contract(
    path: str | Path,
    *,
    root: str | Path | None = None,
    class_name: str | None = None,
) -> type[DataContractModel]:
    """Load an ODCS artifact into a ``DataContractModel`` subclass."""
    from pipelantic.interchange.odcs import load_data_contract as _load

    return _load(path, root=root, class_name=class_name)


def write_odcs(
    model: type[DataContractModel],
    path: str | Path,
    *,
    root: str | Path | None = None,
) -> Path:
    """Write a ``DataContractModel`` class to an ODCS YAML file."""
    from pipelantic.interchange.odcs import write_odcs as _write

    return _write(model, path, root=root)
