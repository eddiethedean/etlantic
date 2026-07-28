#!/usr/bin/env python3
"""Add test for 0.26 root alias removals."""

from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "name",
    [
        "ETLanticError",
        "MemoryStorage",
        "RunIntent",
        "DATAFRAME_PROTOCOL_VERSION",
        "diff_pipelines",
        "PLUGIN_MANIFEST_SCHEMA",
    ],
)
def test_removed_root_alias_raises(name: str) -> None:
    import etlantic

    with pytest.raises(AttributeError, match="removed from the etlantic root in 0.26.0"):
        getattr(etlantic, name)
