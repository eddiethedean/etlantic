"""Independent public-SDK source connector used to qualify AC056-037."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any, cast

from etlantic.connectors.capabilities import SOURCE_BATCH_SNAPSHOT
from etlantic.connectors.maturity import ConnectorMaturity
from etlantic.connectors.models import (
    SOURCE_PROTOCOL,
    ConnectorInfo,
    CursorProposal,
    LandingReadManifest,
    ReadBatch,
    SourcePlan,
    fingerprint_public_config,
)
from etlantic.connectors.protocol import SourceConnector

PROVIDER = "private-ac056037"
PROVIDER_VERSION = "1.0.0"
_DATASET = "warehouse://tenant-a/private/orders-v3"
_PROJECTION = "orders-settled/2"


class PrivateSource:
    """Small independent provider that carries native options through a run."""

    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name=PROVIDER,
            provider=PROVIDER,
            protocol=SOURCE_PROTOCOL,
            version=PROVIDER_VERSION,
            capabilities=(SOURCE_BATCH_SNAPSHOT,),
            maturity=ConnectorMaturity.EXPERIMENTAL,
            metadata={"qualification": "independently-built-wheel"},
            configuration_schema={
                "type": "object",
                "additionalProperties": False,
                "required": ["native_dataset_ref", "projection"],
                "properties": {
                    "native_dataset_ref": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Opaque provider-native resource reference",
                    },
                    "projection": {
                        "type": "string",
                        "enum": [_PROJECTION],
                        "description": "Provider projection option",
                    },
                },
            },
        )

    async def plan_read(
        self, *, binding: Mapping[str, Any], context: Mapping[str, Any]
    ) -> SourcePlan:
        del context
        config = dict(binding.get("config") or {})
        if config != {
            "native_dataset_ref": _DATASET,
            "projection": _PROJECTION,
        }:
            raise ValueError("qualification source received unexpected options")
        return SourcePlan(
            provider=PROVIDER,
            protocol=SOURCE_PROTOCOL,
            mode="snapshot",
            identity_scheme="private_ac056037/1",
            listing_intent={
                "native_dataset_ref": _DATASET,
                "projection": _PROJECTION,
            },
            required_capabilities=(SOURCE_BATCH_SNAPSHOT,),
            config_fingerprint=fingerprint_public_config(config),
            root_ref=_DATASET,
            metadata={
                "native_dataset_ref": _DATASET,
                "projection": _PROJECTION,
            },
        )

    async def read_batches(
        self,
        *,
        plan: SourcePlan,
        binding: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> AsyncIterator[ReadBatch]:
        config = dict(binding.get("config") or {})
        if (
            plan.metadata.get("native_dataset_ref") != _DATASET
            or plan.metadata.get("projection") != _PROJECTION
            or config.get("native_dataset_ref") != _DATASET
            or config.get("projection") != _PROJECTION
        ):
            raise ValueError(
                "accepted native reference/options did not survive execution"
            )
        runtime_context = cast(dict[str, Any], context)
        runtime_context["landing_read_manifest"] = LandingReadManifest(
            root_ref=_DATASET,
            mode="snapshot",
            file_count=1,
            total_bytes=19,
            metadata={
                "native_dataset_ref": _DATASET,
                "projection": _PROJECTION,
            },
        )
        yield ReadBatch(
            records=({"event_id": "private-order-17", "amount": 42},),
            batch_index=0,
            exhausted=True,
            metadata={"provider_version": PROVIDER_VERSION},
        )

    async def propose_cursor(
        self,
        *,
        plan: SourcePlan,
        manifest: LandingReadManifest,
        context: Mapping[str, Any],
    ) -> CursorProposal | None:
        del plan, manifest, context
        return None


def create_source() -> SourceConnector:
    """Entry-point factory exported by the independent wheel."""
    return PrivateSource()
