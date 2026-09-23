# pyright: reportUnknownVariableType=false
"""JSON file storage binding (stdlib)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from etlantic.exceptions import PipelineExecutionError
from etlantic.storage.protocol import as_records, records_to_dicts

_UNSUPPORTED_WRITE_MODES = frozenset({"merge", "upsert"})


class JsonStorage:
    """Read/write JSON arrays or JSON Lines files."""

    name = "json"

    def __init__(self, *, lines: bool = False) -> None:
        self._lines = lines

    def _path(
        self, binding: str, location: str | None, context: dict[str, Any] | None
    ) -> Path:
        if not location:
            raise PipelineExecutionError(
                f"JSON binding {binding!r} requires a location path",
                code="PMEXEC450",
            )
        raw = Path(location)
        policy = (context or {}).get("safe_io")
        if policy is not None:
            from etlantic.io_policy import resolve_under_policy

            resolved, _events = resolve_under_policy(
                raw, policy, run_id=str((context or {}).get("run_id") or "json")
            )
            return Path(resolved)
        return raw

    def _is_lines(self, path: Path) -> bool:
        return self._lines or path.suffix in {".jsonl", ".ndjson"}

    def _decode(self, text: str, path: Path) -> list[Any]:
        if self._is_lines(path):
            return [json.loads(line) for line in text.splitlines() if line.strip()]
        payload = json.loads(text) if text.strip() else []
        return payload if isinstance(payload, list) else [payload]

    def _encode(self, rows: list[Any], path: Path) -> str:
        if self._is_lines(path):
            return "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
        return json.dumps(rows, indent=2, sort_keys=True) + "\n"

    async def read(
        self,
        *,
        binding: str,
        location: str | None,
        contract_type: type[Any] | None,
        context: dict[str, Any],
    ) -> Any:
        path = self._path(binding, location, context)
        if not path.is_file():
            raise PipelineExecutionError(
                f"JSON source not found: {path}",
                code="PMEXEC451",
            )
        policy = (context or {}).get("safe_io")
        if policy is not None:
            from etlantic.io_policy import read_text_safe

            _resolved, text, _events = read_text_safe(
                path,
                policy,
                run_id=str((context or {}).get("run_id") or binding),
            )
        else:
            text = path.read_text(encoding="utf-8")
        rows = self._decode(text, path)
        return as_records(rows, contract_type)

    async def write(
        self,
        *,
        binding: str,
        location: str | None,
        data: Any,
        contract_type: type[Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        mode = str((context or {}).get("write_mode") or "overwrite").lower()
        if mode in _UNSUPPORTED_WRITE_MODES:
            raise PipelineExecutionError(
                f"JSON binding {binding!r} does not support write_mode={mode!r}; "
                "failing closed.",
                code="PMEXEC452",
            )
        path = self._path(binding, location, context)
        rows = records_to_dicts(as_records(data, contract_type))
        if mode in {"skip_if_exists", "skip"} and path.is_file():
            return {
                "binding": binding,
                "location": str(path),
                "records": 0,
                "skipped": True,
            }
        path.parent.mkdir(parents=True, exist_ok=True)
        serialized = self._encode(rows, path)
        policy = (context or {}).get("safe_io")
        if mode == "append":

            def merge(existing_text: str) -> str:
                existing = self._decode(existing_text, path)
                return self._encode([*existing, *rows], path)

            if policy is not None:
                from etlantic.io_policy import read_modify_write_text_safe

                read_modify_write_text_safe(
                    path,
                    policy,
                    merge,
                    run_id=str((context or {}).get("run_id") or binding),
                )
            elif self._is_lines(path) and path.is_file():
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(serialized)
            else:
                existing_text = (
                    path.read_text(encoding="utf-8") if path.is_file() else ""
                )
                path.write_text(merge(existing_text), encoding="utf-8")
        elif policy is not None:
            from etlantic.io_policy import write_text_safe

            write_text_safe(
                path,
                serialized,
                policy,
                run_id=str((context or {}).get("run_id") or binding),
            )
        else:
            path.write_text(serialized, encoding="utf-8")
        return {
            "binding": binding,
            "location": str(path),
            "records": len(rows),
            "skipped": False,
        }
