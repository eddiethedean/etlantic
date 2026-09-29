"""Read-only registry adapter evidence over a local HTTP protocol fixture."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import etlantic as etl


def test_registry_subject_fetch_is_bounded_and_row_free() -> None:
    registry_package = pytest.importorskip("etlantic_schemaregistry")
    document = (
        '{"type":"object","properties":{"id":{"type":"integer"}},"required":["id"]}'
    )
    payload = json.dumps(
        {"subject": "orders", "version": 1, "schemaType": "JSON", "schema": document}
    ).encode()
    methods: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            methods.append("GET")
            if self.path != "/subjects/orders/versions/1":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.schemaregistry.v1+json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(ValueError, match="allowlisted"):
            registry_package.ConfluentHttpRegistry("https://registry.example")
        client = registry_package.ConfluentHttpRegistry(
            f"http://127.0.0.1:{server.server_port}"
        )
        result = etl.infer_registry_subject(client, "orders", version=1)
        assert result.valid
        assert [(field.name, field.logical_type) for field in result.schema.fields] == [
            ("id", "integer")
        ]
        assert result.provenance["version"] == 1
        wire = result.to_observation().to_dict()
        assert document not in json.dumps(wire)
        assert methods == ["GET"]

        limited = registry_package.ConfluentHttpRegistry(
            f"http://127.0.0.1:{server.server_port}", max_bytes=8
        )
        blocked = etl.infer_registry_subject(limited, "orders", version=1)
        assert "INFER_SOURCE_UNSUPPORTED" in {item.code for item in blocked.diagnostics}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
