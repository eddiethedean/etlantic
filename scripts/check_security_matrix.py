#!/usr/bin/env python3
"""CI gate: security verification matrix completeness and path existence.

Validates ``docs/02_FOUNDATIONS/security-verification-matrix.json`` and checks
that ``SECURITY_VERIFICATION_MATRIX.md`` mirrors every control id. Fails when
any row (mandatory or partial) lacks owner, verification, or residual_risk, or
when cited verification paths are missing on disk.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MATRIX_JSON = ROOT / "docs" / "02_FOUNDATIONS" / "security-verification-matrix.json"
MATRIX_MD = ROOT / "docs" / "02_FOUNDATIONS" / "SECURITY_VERIFICATION_MATRIX.md"
EXPECTED_SCHEMA = "etlantic.security_verification_matrix/1"
REQUIRED_FIELDS = ("id", "name", "owner", "verification", "residual_risk")
CONTROL_ID_RE = re.compile(r"^SEC-[A-Z0-9-]+$")
# Full matrix rows have five content columns (id, name, owner, verification,
# residual). Shorter summary tables (e.g. Partial rationale) are ignored.
MD_MATRIX_ROW_RE = re.compile(
    r"^\|\s*(SEC-[A-Z0-9-]+)\s*\|(?:[^|\n]*\|){4}\s*$"
)


def _load_matrix() -> dict[str, Any]:
    if not MATRIX_JSON.is_file():
        raise SystemExit(f"missing matrix JSON: {MATRIX_JSON.relative_to(ROOT)}")
    return json.loads(MATRIX_JSON.read_text(encoding="utf-8"))


def _markdown_control_ids() -> list[str]:
    if not MATRIX_MD.is_file():
        raise SystemExit(f"missing matrix markdown: {MATRIX_MD.relative_to(ROOT)}")
    ids: list[str] = []
    for line in MATRIX_MD.read_text(encoding="utf-8").splitlines():
        match = MD_MATRIX_ROW_RE.match(line.strip())
        if match:
            ids.append(match.group(1))
    return ids


def _validate_control(control: dict[str, Any], index: int) -> list[str]:
    errors: list[str] = []
    label = control.get("id") or f"controls[{index}]"

    for field in REQUIRED_FIELDS:
        if field not in control:
            errors.append(f"{label}: missing required field {field!r}")
            continue
        value = control[field]
        if field == "verification":
            if not isinstance(value, list) or not value:
                errors.append(f"{label}: verification must be a non-empty list")
            elif any(not isinstance(item, str) or not item.strip() for item in value):
                errors.append(f"{label}: verification entries must be non-empty strings")
        elif not isinstance(value, str) or not value.strip():
            errors.append(f"{label}: {field} must be a non-empty string")

    control_id = control.get("id")
    if isinstance(control_id, str) and not CONTROL_ID_RE.match(control_id):
        errors.append(f"{label}: id must match SEC-* pattern")

    status = control.get("status")
    if status not in {"mandatory", "partial"}:
        errors.append(f"{label}: status must be 'mandatory' or 'partial' (got {status!r})")

    # Mandatory rows explicitly called out by the exit gate.
    if status == "mandatory":
        for field in ("owner", "verification", "residual_risk"):
            value = control.get(field)
            if field == "verification":
                if not isinstance(value, list) or not value:
                    errors.append(f"{label}: mandatory row lacks verification")
            elif not isinstance(value, str) or not value.strip():
                errors.append(f"{label}: mandatory row lacks {field}")

    return errors


def _verify_paths(control: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    control_id = control.get("id", "?")
    for rel in control.get("verification") or []:
        if not isinstance(rel, str):
            continue
        path = ROOT / rel
        if not path.exists():
            errors.append(
                f"{control_id}: cited verification path does not exist: {rel}"
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-path-check",
        action="store_true",
        help="Do not require cited verification paths to exist on disk",
    )
    args = parser.parse_args(argv)

    payload = _load_matrix()
    errors: list[str] = []

    schema = payload.get("schema")
    if schema != EXPECTED_SCHEMA:
        errors.append(f"schema must be {EXPECTED_SCHEMA!r} (got {schema!r})")

    controls = payload.get("controls")
    if not isinstance(controls, list) or not controls:
        errors.append("controls must be a non-empty list")
        controls = []

    seen_ids: set[str] = set()
    for index, control in enumerate(controls):
        if not isinstance(control, dict):
            errors.append(f"controls[{index}] must be an object")
            continue
        errors.extend(_validate_control(control, index))
        control_id = control.get("id")
        if isinstance(control_id, str):
            if control_id in seen_ids:
                errors.append(f"duplicate control id: {control_id}")
            seen_ids.add(control_id)
        if not args.skip_path_check:
            errors.extend(_verify_paths(control))

    md_ids = _markdown_control_ids()
    md_set = set(md_ids)
    if len(md_ids) != len(md_set):
        errors.append("SECURITY_VERIFICATION_MATRIX.md has duplicate control ids")

    missing_from_md = sorted(seen_ids - md_set)
    extra_in_md = sorted(md_set - seen_ids)
    if missing_from_md:
        errors.append(
            "markdown missing control ids from JSON: " + ", ".join(missing_from_md)
        )
    if extra_in_md:
        errors.append(
            "markdown has control ids not in JSON: " + ", ".join(extra_in_md)
        )

    if errors:
        print("Security verification matrix gate FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1

    mandatory = sum(1 for c in controls if c.get("status") == "mandatory")
    partial = sum(1 for c in controls if c.get("status") == "partial")
    print(
        "Security verification matrix OK: "
        f"{len(controls)} controls "
        f"({mandatory} mandatory, {partial} partial); "
        "JSON and markdown ids match; verification paths exist."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
