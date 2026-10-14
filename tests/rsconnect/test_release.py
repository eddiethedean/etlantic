"""Execute the release workflow's version and publishing shell locally."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW = _ROOT / ".github/workflows/release.yml"
pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="the release shell runs on Ubuntu"
)


def _step(name: str) -> str:
    block = _WORKFLOW.read_text().split(f"      - name: {name}\n", 1)[1]
    block = block.split("\n      - ", 1)[0]
    return textwrap.dedent(block.split("        run: |\n", 1)[1])


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.mark.parametrize("module_version", ["0.60.0", "0.60.1"])
def test_release_validates_independent_preview_version(
    module_version: str, tmp_path: Path
) -> None:
    checkout = tmp_path / "checkout"
    _write(checkout / "pyproject.toml", '[project]\nversion = "0.59.0"\n')
    for source in (_ROOT / "packages").glob("*/pyproject.toml"):
        version = "0.60.0" if source.parent.name == "etlantic-rsconnect" else "0.59.0"
        _write(
            checkout / source.relative_to(_ROOT),
            f'[project]\nversion = "{version}"\n',
        )
    _write(checkout / "src/etlantic/_version.py", '__version__ = "0.59.0"\n')
    _write(
        checkout / "packages/etlantic-rsconnect/src/etlantic_rsconnect/__init__.py",
        f'__version__ = "{module_version}"\n',
    )
    exports = tmp_path / "github-env"
    result = subprocess.run(
        [
            "bash",
            "-euc",
            'uv() { printf "0.59.0\\n"; }\n'
            + _step("Verify tag matches package version"),
        ],
        cwd=checkout,
        env={**os.environ, "RELEASE_TAG": "v0.59.0", "GITHUB_ENV": str(exports)},
        capture_output=True,
        text=True,
        check=False,
    )
    if module_version == "0.60.0":
        assert result.returncode == 0, result.stdout + result.stderr
        assert exports.read_text() == "RSCONNECT_VERSION=0.60.0\n"
    else:
        assert result.returncode != 0
        assert "Rsconnect preview version mismatch" in result.stdout


def test_preview_publish_uses_its_artifacts_and_checks_its_own_version(
    tmp_path: Path,
) -> None:
    script = _step("Publish packages to PyPI (OIDC preferred, token fallback)")
    helpers = script.split("\npublish_pair etlantic \\\n", 1)[0]
    invocation = script.split("publish_pair etlantic-rsconnect \\\n", 1)[1]
    invocation = (
        "publish_pair etlantic-rsconnect \\\n"
        + invocation.split("\npublish_pair etlantic-lsp ", 1)[0]
    )
    for filename in (
        "etlantic_rsconnect-0.60.0-py3-none-any.whl",
        "etlantic_rsconnect-0.60.0.tar.gz",
    ):
        _write(tmp_path / "dist" / filename, "synthetic release artifact\n")
    trace = tmp_path / "publish-trace"
    simulated_publisher = """
    pypi_project_exists() { return 0; }
    pypi_version_exists() {
      printf '%s==%s\\n' "$1" "$2" >> "$PUBLISH_TRACE"
      [ "$1" = etlantic-rsconnect ] && [ "$2" = 0.60.0 ]
    }
    uv() {
      for argument in "$@"; do
        case "$argument" in
          *.whl|*.tar.gz) [ -f "$argument" ] || return 2 ;;
        esac
      done
      printf 'file already exists\\n'
      return 1
    }
    """
    result = subprocess.run(
        ["bash", "-euc", helpers + textwrap.dedent(simulated_publisher) + invocation],
        cwd=tmp_path,
        env={
            **os.environ,
            "RELEASE_TAG": "v0.59.0",
            "RSCONNECT_VERSION": "0.60.0",
            "PUBLISH_TRACE": str(trace),
            "UV_PUBLISH_TOKEN": "",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert trace.read_text() == "etlantic-rsconnect==0.60.0\n"
