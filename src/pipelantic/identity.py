"""Stable identity helpers for pipelines, nodes, ports, and contracts."""

from __future__ import annotations

import re
from typing import Any


def qualified_type_id(obj: type[Any] | Any) -> str:
    """Return a stable identity for a class or object type.

    Format: ``{module}:{qualname}``. Never uses memory addresses.
    """
    if not isinstance(obj, type):
        obj = type(obj)
    module = getattr(obj, "__module__", None) or "<unknown>"
    qualname = getattr(obj, "__qualname__", None) or getattr(obj, "__name__", "?")
    return f"{module}:{qualname}"


def pipeline_id(pipeline_cls: type[Any]) -> str:
    """Stable identity for a pipeline class."""
    published = getattr(pipeline_cls, "__published_id__", None)
    if isinstance(published, str) and published:
        return published
    return qualified_type_id(pipeline_cls)


def transformation_id(transformation_cls: type[Any]) -> str:
    """Stable identity for a transformation class."""
    published = getattr(transformation_cls, "__published_id__", None)
    if isinstance(published, str) and published:
        return published
    return qualified_type_id(transformation_cls)


def contract_id(contract_type: type[Any]) -> str:
    """Stable authoring identity for a data-contract type.

    Always uses ``{module}:{qualname}``. Published ODCS/CCM identities are
    available via :func:`published_contract_id`.
    """
    return qualified_type_id(contract_type)


def published_contract_id(contract_type: type[Any]) -> str | None:
    """Return the published data-contract id when ContractModel can provide one."""
    explicit = getattr(contract_type, "__published_id__", None)
    if isinstance(explicit, str) and explicit:
        return explicit
    try:
        from contractmodel import DataContract

        return str(DataContract.from_pydantic(contract_type).contract_id)
    except Exception:
        return None


def published_contract_version(contract_type: type[Any]) -> str | None:
    """Return the published data-contract version when available."""
    explicit = getattr(contract_type, "__published_version__", None)
    if isinstance(explicit, str) and explicit:
        return explicit
    try:
        from contractmodel import DataContract

        return str(DataContract.from_pydantic(contract_type).version)
    except Exception:
        return None


def identity_slug(identity: str) -> str:
    """Convert a contract identity into a stable filesystem slug."""
    slug = identity.strip().lower()
    slug = slug.replace(":", "__").replace("/", "__")
    slug = re.sub(r"[^a-z0-9._-]+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-._")
    return slug or "contract"


def node_id(pipeline: str, node_name: str) -> str:
    """Stable identity for a node within a pipeline."""
    return f"{pipeline}/{node_name}"


def port_id(node: str, port_name: str) -> str:
    """Stable identity for a port on a node."""
    return f"{node}:{port_name}"


def implementation_id(transform: str, engine: str) -> str:
    """Stable identity for a registered transformation implementation."""
    return f"{transform}/{engine}"
