# ruff: noqa: E402
"""Generated-spec consumer qualification through the public HTTP API."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx2")
uvicorn = pytest.importorskip("uvicorn")

from etlantic import Data, Extract, Load, Pipeline
from etlantic.authoring import definition_from_pipeline
from etlantic.authoring.serialize import pipeline_to_dict
from etlantic.control_plane import (
    ControlPlaneContext,
    EnvironmentRef,
    MemoryAuthorizer,
    MemoryDurableWorkStore,
    MemoryEventStore,
    MemoryRegistryProvider,
    MemorySubmissionStore,
    Principal,
    RegistryDefinitionRepository,
    SecurityDomain,
    TenantRef,
    WorkspaceRef,
)
from etlantic_fastapi import (
    ETLanticAPI,
    create_app,
    membership_context_factory,
    principal_from_header,
)


class _ConsumerRow(Data):
    id: int


class _ConsumerPipeline(Pipeline):
    source: Extract[_ConsumerRow] = Extract(asset="source")
    target: Load[_ConsumerRow] = Load(input=source, asset="target")


def test_generated_consumer_runs_review_and_external_webhook_over_public_commands(
    tmp_path: Path,
) -> None:
    ctx = _authorized_context()
    authorizer = MemoryAuthorizer()
    for action in (
        "definition.write",
        "definition.validate",
        "definition.plan",
        "run.submit",
    ):
        authorizer.grant(ctx, action)

    submissions = MemorySubmissionStore()
    durable = MemoryDurableWorkStore()
    api = ETLanticAPI(
        authorizer=authorizer,
        definitions=RegistryDefinitionRepository(MemoryRegistryProvider()),
        submissions=submissions,
        events=MemoryEventStore(),
        durable_work=durable,
        profile="development",
        context_factory=membership_context_factory(
            {
                "alice": (
                    "consumer-tenant",
                    "consumer-workspace",
                    "development",
                    "consumer-tests",
                )
            }
        ),
        principal_dependency=principal_from_header,
    ).enable_managed_execution()
    app = create_app(api)

    received_events: list[dict[str, Any]] = []

    class WebhookHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            size = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(size))
            received_events.append(
                {
                    "path": self.path,
                    "idempotency_key": self.headers.get("Idempotency-Key"),
                    "event": body,
                }
            )
            self.send_response(204)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    webhook = ThreadingHTTPServer(("127.0.0.1", 0), WebhookHandler)
    webhook_thread = threading.Thread(target=webhook.serve_forever, daemon=True)
    webhook_thread.start()

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        api_port = int(listener.getsockname()[1])
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=api_port,
            log_level="critical",
            access_log=False,
        )
    )
    api_thread = threading.Thread(target=server.run, daemon=True)
    api_thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            if not api_thread.is_alive():
                raise RuntimeError("managed API exited before binding")
            if time.monotonic() > deadline:
                raise RuntimeError("managed API did not start")
            time.sleep(0.01)

        document = pipeline_to_dict(definition_from_pipeline(_ConsumerPipeline))
        spec_path = tmp_path / "consumer-spec.json"
        spec = {
            "definition_id": "generated-customer-refresh",
            "document": document,
            "idempotency_key": "generated-customer-refresh:rejected-review",
            "request": {},
            "business_context": {"change_request": "CR-056"},
        }
        spec_path.write_text(json.dumps(spec), encoding="utf-8")
        script = (
            Path(__file__).resolve().parents[2]
            / "examples"
            / "managed_consumer_0_56.py"
        )
        command = [
            sys.executable,
            str(script),
            str(spec_path),
            "--base-url",
            f"http://127.0.0.1:{api_port}",
            "--principal",
            "alice",
            "--require-review",
            "--business-webhook",
            f"http://127.0.0.1:{webhook.server_port}/events/managed",
        ]

        rejected = subprocess.run(
            command,
            input="no\n",
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        assert rejected.returncode == 1
        assert "External review did not approve" in rejected.stderr
        rejected_spec = json.loads(spec_path.read_text(encoding="utf-8"))
        revision_id = rejected_spec["revision_id"]
        assert isinstance(revision_id, str) and revision_id
        assert received_events == []
        assert (
            submissions.lookup_idempotency(
                _authorized_context(),
                "generated-customer-refresh:rejected-review",
                operation="run.submit",
            )
            is None
        )

        # Reuse the checkpointed immutable revision for the approved command.
        rejected_spec["idempotency_key"] = "generated-customer-refresh:approved"
        spec_path.write_text(json.dumps(rejected_spec), encoding="utf-8")
        approved = subprocess.run(
            command,
            input="yes\n",
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        assert approved.returncode == 0, approved.stderr
        assert len(received_events) == 1
        received = received_events[0]
        assert received["path"] == "/events/managed"
        assert received["idempotency_key"] == received["event"]["event_id"]
        assert received["event"]["business_event"] == "etlantic.run.accepted"
        assert received["event"]["business_context"] == {"change_request": "CR-056"}
        accepted = submissions.lookup_idempotency(
            _authorized_context(),
            "generated-customer-refresh:approved",
            operation="run.submit",
        )
        assert accepted is not None
        assert accepted.submission_id == received["event"]["receipt"]["submission_id"]
        assert len(durable.pending_outbox(_authorized_context())) == 1
        assert "import etlantic" not in script.read_text(encoding="utf-8")
    finally:
        server.should_exit = True
        api_thread.join(timeout=5)
        webhook.shutdown()
        webhook.server_close()
        webhook_thread.join(timeout=5)


def _authorized_context() -> ControlPlaneContext:
    """Return the app's stable fixture scope for direct store assertions."""
    return ControlPlaneContext(
        principal=Principal("alice"),
        tenant=TenantRef("consumer-tenant"),
        workspace=WorkspaceRef("consumer-tenant", "consumer-workspace"),
        environment=EnvironmentRef("development"),
        security_domain=SecurityDomain("consumer-tests"),
    )
