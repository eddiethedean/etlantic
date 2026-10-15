"""Execute the release workflow's version and publishing shell locally."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from scripts.check_rsconnect_release import TAG_PREFIX, inspect_source

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
    _write(checkout / "pyproject.toml", '[project]\nversion = "0.60.0"\n')
    for source in (_ROOT / "packages").glob("*/pyproject.toml"):
        version = "0.60.0"
        _write(
            checkout / source.relative_to(_ROOT),
            f'[project]\nversion = "{version}"\n',
        )
    _write(checkout / "src/etlantic/_version.py", '__version__ = "0.60.0"\n')
    _write(
        checkout / "packages/etlantic-rsconnect/src/etlantic_rsconnect/__init__.py",
        f'__version__ = "{module_version}"\n',
    )
    exports = tmp_path / "github-env"
    result = subprocess.run(
        [
            "bash",
            "-euc",
            'uv() { printf "0.60.0\\n"; }\n'
            + _step("Verify tag matches package version"),
        ],
        cwd=checkout,
        env={**os.environ, "RELEASE_TAG": "v0.60.0", "GITHUB_ENV": str(exports)},
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
            "RELEASE_TAG": "v0.60.0",
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


def _release_source(destination: Path) -> Path:
    for name in (
        "pyproject.toml",
        "uv.lock",
        "packages/etlantic-rsconnect/pyproject.toml",
        "packages/etlantic-rsconnect/src/etlantic_rsconnect/__init__.py",
        "packages/etlantic-rsconnect/CHANGELOG.md",
        "packages/etlantic-rsconnect/LICENSE",
    ):
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_ROOT / name, target)
    return destination


def test_preview_has_a_release_tag_independent_of_the_published_core(
    tmp_path: Path,
) -> None:
    source = _release_source(tmp_path)
    result = inspect_source(source, tag=f"{TAG_PREFIX}0.60.0")

    assert result["version"] == "0.60.0"
    assert result["core_version"] == "0.60.0"
    assert result["external_services_required"] is False
    for wrong_tag in ("v0.60.0", "etlantic-rsconnect-v0.60.1"):
        with pytest.raises(ValueError, match="preview tag must be"):
            inspect_source(source, tag=wrong_tag)
    workflow = _WORKFLOW.read_text()
    assert '- "etlantic-rsconnect-v*.*.*"' in workflow
    assert "  publish-rsconnect:\n" in workflow
    assert "!startsWith(" in workflow


def test_preview_dispatch_requires_a_real_tag_at_the_checked_out_commit(
    tmp_path: Path,
) -> None:
    def git(*arguments: str) -> None:
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Release test",
                "-c",
                "user.email=release-test@example.invalid",
                "-c",
                "commit.gpgsign=false",
                "-c",
                "tag.gpgsign=false",
                *arguments,
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
        )

    tag = f"{TAG_PREFIX}0.60.0"
    git("init")
    git("commit", "--allow-empty", "-m", "synthetic preview source")
    git("branch", tag)

    def verify() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", "-euc", _step("Verify rsconnect release tag ref")],
            cwd=tmp_path,
            env={**os.environ, "RELEASE_TAG": tag},
            capture_output=True,
            text=True,
            check=False,
        )

    assert verify().returncode != 0  # A similarly named branch is insufficient.
    git("tag", tag)
    assert verify().returncode == 0
    git("commit", "--allow-empty", "-m", "different source")
    assert verify().returncode != 0


@pytest.mark.parametrize(
    ("relative_path", "old", "new", "error"),
    [
        (
            "packages/etlantic-rsconnect/src/etlantic_rsconnect/__init__.py",
            '__version__ = "0.60.0"',
            '__version__ = "0.60.1"',
            "metadata and module versions differ",
        ),
        (
            "pyproject.toml",
            "etlantic-rsconnect[connect]>=0.60.0",
            "etlantic-rsconnect[connect]>=0.61.0",
            "root rsconnect extra",
        ),
        (
            "packages/etlantic-rsconnect/pyproject.toml",
            "posit-sdk==0.17.0",
            "posit-sdk>=0.17.0",
            "one exact SDK version",
        ),
        (
            "uv.lock",
            'name = "etlantic-rsconnect"\nversion = "0.60.0"',
            'name = "etlantic-rsconnect"\nversion = "0.60.1"',
            "lockfile does not match",
        ),
    ],
)
def test_preview_readiness_rejects_inconsistent_release_metadata(
    relative_path: str, old: str, new: str, error: str, tmp_path: Path
) -> None:
    source = _release_source(tmp_path)
    path = source / relative_path
    original = path.read_text()
    assert old in original
    path.write_text(original.replace(old, new))

    with pytest.raises(ValueError, match=error):
        inspect_source(source)


@pytest.mark.parametrize("fallback", [False, True])
def test_independent_preview_publisher_only_uploads_its_own_artifacts(
    fallback: bool, tmp_path: Path
) -> None:
    for filename in (
        "etlantic_rsconnect-0.60.0-py3-none-any.whl",
        "etlantic_rsconnect-0.60.0.tar.gz",
    ):
        _write(tmp_path / "dist" / filename, "synthetic release artifact\n")
    trace = tmp_path / "publish-trace"
    publisher = """
    uv() {
      printf '%s\\n' "$*" >> "$PUBLISH_TRACE"
      for argument in "$@"; do
        case "$argument" in
          *.whl|*.tar.gz) [ -f "$argument" ] || return 2 ;;
        esac
      done
      if [ "$USE_FALLBACK" = true ] && [ "$2" = --trusted-publishing ]; then
        return 1
      fi
    }
    """
    result = subprocess.run(
        [
            "bash",
            "-euc",
            textwrap.dedent(publisher) + _step("Publish rsconnect preview"),
        ],
        cwd=tmp_path,
        env={
            **os.environ,
            "RSCONNECT_VERSION": "0.60.0",
            "PUBLISH_TRACE": str(trace),
            "USE_FALLBACK": "true" if fallback else "false",
            "UV_PUBLISH_TOKEN": "synthetic-token" if fallback else "",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    invocations = trace.read_text().splitlines()
    assert len(invocations) == (2 if fallback else 1)
    assert all("dist/etlantic_rsconnect-0.60.0" in item for item in invocations)
    assert all("dist/etlantic-" not in item for item in invocations)
    assert "synthetic-token" not in result.stdout + result.stderr
