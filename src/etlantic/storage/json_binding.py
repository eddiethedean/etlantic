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
        text = path.read_text(encoding="utf-8")
        if self._lines or path.suffix in {".jsonl", ".ndjson"}:
            rows = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            payload = json.loads(text) if text.strip() else []
            rows = payload if isinstance(payload, list) else [payload]
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
        if mode == "append" and path.is_file():
            if self._lines or path.suffix in {".jsonl", ".ndjson"}:
                with path.open("a", encoding="utf-8") as handle:
                    for row in rows:
                        handle.write(json.dumps(row, sort_keys=True) + "\n")
            else:
                existing_text = path.read_text(encoding="utf-8")
                existing = json.loads(existing_text) if existing_text.strip() else []
                if not isinstance(existing, list):
                    existing = [existing]
                existing.extend(rows)
                path.write_text(
                    json.dumps(existing, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
        elif self._lines or path.suffix in {".jsonl", ".ndjson"}:
            path.write_text(
                "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
                encoding="utf-8",
            )
        else:
            path.write_text(
                json.dumps(rows, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        return {
            "binding": binding,
            "location": str(path),
            "records": len(rows),
            "skipped": False,
        }
