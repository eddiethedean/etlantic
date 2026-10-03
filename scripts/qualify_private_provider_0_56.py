"""Build and run AC056-037 from clean installed wheels in a temporary venv."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "private_provider_0_56"


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {command!r}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed.stdout.strip()


def _wheel(directory: Path, pattern: str) -> Path:
    matches = sorted(directory.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"expected one wheel matching {pattern!r}, got {matches!r}")
    return matches[0]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def qualify() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="etlantic-ac056037-") as temp_name:
        temp = Path(temp_name)
        wheels = temp / "wheels"
        wheels.mkdir()
        provider_project = temp / "private-provider"
        shutil.copytree(FIXTURE, provider_project)
        _run(
            [
                "uv",
                "build",
                "--package",
                "etlantic",
                "--wheel",
                "--out-dir",
                str(wheels),
            ],
            cwd=ROOT,
        )
        _run(
            ["uv", "build", "--wheel", "--out-dir", str(wheels), str(provider_project)],
            cwd=ROOT,
        )
        core_wheel = _wheel(wheels, "etlantic-*.whl")
        provider_wheel = _wheel(wheels, "etlantic_private_ac056037-*.whl")

        venv = temp / "venv"
        _run(["uv", "venv", "--python", sys.executable, str(venv)], cwd=ROOT)
        python = venv / "bin" / "python"
        _run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                str(core_wheel),
                str(provider_wheel),
            ],
            cwd=temp,
        )

        workdir = temp / "consumer-work"
        workdir.mkdir()
        child_env = os.environ.copy()
        for name in (
            "PYTHONPATH",
            "PYTHONHOME",
            "VIRTUAL_ENV",
            "UV_PROJECT_ENVIRONMENT",
        ):
            child_env.pop(name, None)
        result = _run(
            [
                str(python),
                "-I",
                str(FIXTURE / "consumer.py"),
                str(workdir),
            ],
            cwd=temp,
            env=child_env,
        )
        consumer_result = json.loads(result)
        return {
            "schema": "etlantic.phase_0_56.private_provider_qualification/1",
            "qualification": "pass",
            "python": sys.version.split()[0],
            "core_wheel": {
                "filename": core_wheel.name,
                "sha256": _sha256(core_wheel),
            },
            "independent_provider_wheel": {
                "filename": provider_wheel.name,
                "distribution": "etlantic-private-ac056037",
                "version": "1.0.0",
                "sha256": _sha256(provider_wheel),
            },
            "consumer": consumer_result,
            "installed_without_workspace_path": True,
        }


if __name__ == "__main__":
    print(json.dumps(qualify(), sort_keys=True, indent=2))
