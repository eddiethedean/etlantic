#!/usr/bin/env python3
"""Example: continuous landing-zone watch as a durable submitter (outside core).

Continuous directory watching is **not** a third Extract kind and must not live
under ``src/etlantic/``. This script polls a directory with the stdlib and
posts workspace-scoped ``local-files`` binding refs to the CP1 durable submit
API — never file contents.

Usage (after starting a control-plane app that accepts ``X-Principal``)::

    python examples/landing_zone_watch_submitter.py \\
        --watch ./inbox --definition landing_pipe --base-url http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path

try:
    import httpx
except ImportError:  # pragma: no cover - example-only dependency
    print("httpx is required for this example: pip install httpx", file=sys.stderr)
    raise SystemExit(1) from None

from etlantic_fastapi.landing_sensor import (
    LandingWatchSubmitter,
    local_files_binding_ref,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", type=Path, required=True)
    parser.add_argument("--definition", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--principal", default="alice")
    parser.add_argument("--tenant", default="tenant-a")
    parser.add_argument("--workspace", default="ws-1")
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()

    binding = local_files_binding_ref(root=args.watch.name, mode="snapshot")

    def submit_run(
        definition_id: str,
        payload: dict,
        idempotency_key: str,
    ) -> dict:
        resp = httpx.post(
            f"{args.base_url.rstrip('/')}/v1/definitions/{definition_id}/runs",
            headers={
                "X-Principal": args.principal,
                "Idempotency-Key": idempotency_key,
            },
            json={"payload": payload},
            timeout=30.0,
        )
        resp.raise_for_status()
        return dict(resp.json())

    stop = threading.Event()
    submitter = LandingWatchSubmitter(
        watch_dir=args.watch,
        definition_id=args.definition,
        submit_run=submit_run,
        binding_ref=binding,
        tenant_id=args.tenant,
        workspace_id=args.workspace,
        poll_interval=args.interval,
    )
    print(
        f"Watching {args.watch} as submitter (not an Extract kind). Ctrl+C to stop.",
        flush=True,
    )
    try:
        while not stop.is_set():
            for receipt in submitter.poll_once():
                print(f"accepted {receipt.get('acceptance_id')}", flush=True)
            stop.wait(args.interval)
    except KeyboardInterrupt:
        stop.set()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
