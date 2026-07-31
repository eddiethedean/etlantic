"""Import-boundary: core etlantic must not require FastAPI at import time."""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path


def test_importing_etlantic_does_not_require_fastapi() -> None:
    before = {
        name for name in sys.modules if name == "fastapi" or name.startswith("fastapi.")
    }
    importlib.invalidate_caches()
    import etlantic

    assert etlantic.__name__ == "etlantic"
    cp = etlantic.control_plane
    assert cp.ControlPlaneContext is not None
    after = {
        name for name in sys.modules if name == "fastapi" or name.startswith("fastapi.")
    }
    assert after == before or not (after - before)

    import etlantic.control_plane as cp_mod
    import etlantic.control_plane.authz as authz
    import etlantic.control_plane.errors as errors
    import etlantic.control_plane.memory as memory
    import etlantic.control_plane.models as models
    import etlantic.control_plane.protocols as protocols

    for mod in (cp_mod, models, protocols, authz, errors, memory):
        assert "fastapi" not in mod.__dict__
        path = Path(mod.__file__ or "")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("fastapi")
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("fastapi")
