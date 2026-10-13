"""Public data-contract and SQLModel conversion namespace.

Root-level exports remain available for existing callers. This module provides
an owning import path for new modeling integrations.
"""

from __future__ import annotations

from etlantic_sqlmodel import (
    compare_metadata,
    contract_to_sqlmodel,
    contract_to_sqlmodel_source,
    primary_key_fields,
    sqlmodel_to_contract,
    validate_model_primary_keys,
)

__all__ = [
    "compare_metadata",
    "contract_to_sqlmodel",
    "contract_to_sqlmodel_source",
    "primary_key_fields",
    "sqlmodel_to_contract",
    "validate_model_primary_keys",
]
