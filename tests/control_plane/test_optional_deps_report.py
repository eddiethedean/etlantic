"""Dependency / import report: core stays FastAPI- and SQLModel-free."""

from __future__ import annotations

import ast
import importlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTROL_PLANE = ROOT / "src" / "etlantic" / "control_plane"


def _forbidden_imports(path: Path, roots: tuple[str, ...]) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if any(
                    alias.name == r or alias.name.startswith(r + ".") for r in roots
                ):
                    hits.append(alias.name)
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and any(node.module == r or node.module.startswith(r + ".") for r in roots)
        ):
            hits.append(node.module)
    return hits


def test_control_plane_sources_forbid_fastapi_and_sqlmodel() -> None:
    forbidden = ("fastapi", "sqlmodel", "starlette")
    offenders: list[str] = []
    for path in sorted(CONTROL_PLANE.glob("*.py")):
        hits = _forbidden_imports(path, forbidden)
        if hits:
            offenders.append(f"{path.name}: {hits}")
    assert not offenders, (
        "control_plane must not import optional HTTP/ORM stacks:\n"
        + ("\n".join(offenders))
    )


def test_import_etlantic_without_fastapi_or_sqlmodel() -> None:
    before = {
        name
        for name in sys.modules
        if name == "fastapi"
        or name.startswith("fastapi.")
        or name == "sqlmodel"
        or name.startswith("sqlmodel.")
    }
    importlib.invalidate_caches()
    import etlantic

    assert etlantic.__name__ == "etlantic"
    _ = etlantic.control_plane.ControlPlaneContext
    after = {
        name
        for name in sys.modules
        if name == "fastapi"
        or name.startswith("fastapi.")
        or name == "sqlmodel"
        or name.startswith("sqlmodel.")
    }
    leaked = after - before
    assert not leaked, f"import etlantic pulled optional deps: {sorted(leaked)}"


def test_subprocess_import_etlantic_clean() -> None:
    """Fresh interpreter proves optional packages are not required at import."""
    code = (
        "import sys\n"
        "assert 'fastapi' not in sys.modules\n"
        "assert 'sqlmodel' not in sys.modules\n"
        "import etlantic\n"
        "assert etlantic.__version__\n"
        "import etlantic.control_plane as cp\n"
        "assert cp.ControlPlaneContext is not None\n"
        "assert 'fastapi' not in sys.modules\n"
        "assert 'sqlmodel' not in sys.modules\n"
        "print('ok', etlantic.__version__)\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.strip().startswith("ok ")


def test_fastapi_package_declares_optional_extra() -> None:
    root_pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'fastapi = ["etlantic-fastapi==' in root_pyproject
    pkg = (ROOT / "packages" / "etlantic-fastapi" / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    assert "fastapi" in pkg
    assert "etlantic>=" in pkg
