"""In-repo fake third-party source connector (public imports only).

Simulates an independently governed connector that would register via
``etlantic.source_connectors`` without depending on private core modules.
Used for Wave 7 soft-continue evidence for ``038-X-01`` until
``etlantic-plugin-echo`` hosts a real entry point.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

from etlantic.connectors.capabilities import (
    FORMAT_CSV,
    IDEMPOTENCY,
    SOURCE_BATCH_SNAPSHOT,
    SOURCE_FILE_GLOB,
)
from etlantic.connectors.maturity import ConnectorMaturity
from etlantic.connectors.models import (
    SOURCE_PROTOCOL,
    ConnectorInfo,
    CursorProposal,
    LandingReadManifest,
    ReadBatch,
    SchemaInspection,
    SourcePlan,
    fingerprint_public_config,
)
from etlantic.connectors.protocol import SourceConnector

PROVIDER = "echo-third-party"
_CAPS = frozenset(
    {
        SOURCE_BATCH_SNAPSHOT,
        SOURCE_FILE_GLOB,
        FORMAT_CSV,
        IDEMPOTENCY,
    }
)


class EchoThirdPartySource:
    """Minimal protocol-valid source used only in tests."""

    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name=PROVIDER,
            protocol=SOURCE_PROTOCOL,
            version="0.38.0",
            provider=PROVIDER,
            capabilities=tuple(sorted(_CAPS)),
            maturity=ConnectorMaturity.EXPERIMENTAL,
            metadata={"governance": "in-repo-fake-third-party", "public_imports": True},
        )

    async def plan_read(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> SourcePlan:
        cfg = dict(binding.get("config") or {})
        mode = str(cfg.get("mode") or binding.get("mode") or "snapshot")
        return SourcePlan(
            provider=PROVIDER,
            protocol=SOURCE_PROTOCOL,
            mode=mode if mode in {"snapshot", "incremental"} else "snapshot",  # type: ignore[arg-type]
            identity_scheme="echo_row_id/1",
            listing_intent={
                "root_ref": str(
                    cfg.get("root_ref") or binding.get("root_ref") or "echo"
                ),
                "glob": str(cfg.get("glob") or binding.get("glob") or "*.csv"),
            },
            required_capabilities=tuple(sorted(_CAPS)),
            config_fingerprint=fingerprint_public_config(cfg),
            root_ref=str(cfg.get("root_ref") or binding.get("root_ref") or "echo"),
            metadata={"live_files": False},
        )

    async def read_batches(
        self,
        *,
        plan: SourcePlan,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> AsyncIterator[ReadBatch]:
        del plan, binding
        rows = [{"event_id": "echo-1", "payload": "hello"}]
        context["landing_read_manifest"] = LandingReadManifest(
            root_ref="echo",
            mode="snapshot",
            identities=(),
            file_count=1,
            total_bytes=0,
            metadata={"synthetic": True, "provider": PROVIDER},
        )
        yield ReadBatch(records=rows, batch_index=0)

    async def propose_cursor(
        self,
        *,
        plan: SourcePlan,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> CursorProposal | None:
        del plan, binding, context
        return None

    async def inspect_schema(
        self,
        *,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> SchemaInspection:
        del binding, context
        return SchemaInspection(
            provider=PROVIDER,
            fields=(
                {"name": "event_id", "type": "string"},
                {"name": "payload", "type": "string"},
            ),
            row_estimate=None,
            metadata={"bounded": True},
        )


def create_echo_third_party_source() -> SourceConnector:
    """Factory matching ``etlantic.source_connectors`` entry-point shape."""
    return EchoThirdPartySource()


__all__ = [
    "PROVIDER",
    "EchoThirdPartySource",
    "create_echo_third_party_source",
]
