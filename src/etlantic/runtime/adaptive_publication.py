"""Atomic destination-locked publication for qualified local adaptive sinks."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

from anyio.to_thread import run_sync

from etlantic.connectors.models import CommitReceipt
from etlantic.io_policy import SafeIoPolicy, write_text_safe
from etlantic.storage.protocol import records_to_dicts


async def publish_file(
    *,
    provider: str,
    location: str,
    data: Any,
    contract_type: Any,
    policy: SafeIoPolicy | None,
    publication_id: str,
) -> CommitReceipt:
    rows = records_to_dicts(data)
    if provider == "json":
        if Path(location).suffix in {".jsonl", ".ndjson"}:
            text = "".join(
                json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in rows
            )
        else:
            text = json.dumps(rows, sort_keys=True, indent=2, allow_nan=False) + "\n"
    else:
        buffer = io.StringIO(newline="")
        fields = (
            list(contract_type.model_fields)
            if contract_type is not None
            else list(rows[0])
            if rows
            else ["value"]
        )
        writer = csv.DictWriter(buffer, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        text = buffer.getvalue()
    policy = policy or SafeIoPolicy.for_root(Path(location).absolute().parent)
    if not policy.enable_locking:
        raise ValueError("Adaptive file publication requires destination locking")

    # Drain blocking atomic commit before its input buffers may be reclaimed.
    def commit() -> None:
        write_text_safe(Path(location), text, policy, run_id=publication_id)

    await run_sync(commit)
    return CommitReceipt(
        status="committed",
        provider=provider,
        publication_id=publication_id,
        metadata={
            "digest": "sha256:" + hashlib.sha256(text.encode()).hexdigest(),
            "record_count": len(rows),
        },
    )
