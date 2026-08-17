"""ETLantic streaming SDK (etlantic.streaming/1).

Core owns logical expansion, stream-time, envelope metadata, DLQ policy, and
schema-registry **protocol**. Kafka I/O and live registry HTTP stay in optional
packages. Artifacts never contain event payloads.
"""

from __future__ import annotations

from etlantic.streaming.control import (
    CONTROL_NODE_KINDS,
    STREAMING_EXTRAS,
    STREAMING_SCHEMA,
    ChildExpansion,
    ExpansionBounds,
    ExpansionSpec,
    child_identity,
    expand_children,
    is_control_kind,
    reject_python_branch,
)
from etlantic.streaming.diagnostics import (
    DLQ_CODES,
    DYN_CODES,
    REG_CODES,
    STR_CODES,
    dlq_diagnostic,
    dyn_diagnostic,
    reg_diagnostic,
    str_diagnostic,
)
from etlantic.streaming.envelope import (
    ChangeEnvelopeMetadata,
    ChangeOp,
    assert_no_payload,
)
from etlantic.streaming.errors import (
    OffsetAdvanceRule,
    RecordErrorOutcome,
    RecordErrorPolicy,
)
from etlantic.streaming.fixtures import (
    InMemoryDeadLetterStore,
    InMemoryRecord,
    InMemoryStreamSink,
    InMemoryStreamSource,
    InMemoryTriggerQueue,
)
from etlantic.streaming.handoff import (
    HandoffResult,
    SnapshotCut,
    evaluate_handoff,
    handoff_failure_diagnostic,
)
from etlantic.streaming.migration import (
    ENVELOPE_SCHEMA_V1,
    STATE_SCHEMA_V1,
    StreamStateRecord,
    migrate_envelope_dict,
    migrate_state_dict,
)
from etlantic.streaming.plan_meta import (
    EXPANSION_METADATA_KEY,
    STREAMING_METADATA_KEY,
    expand_plan_metadata,
    expansion_metadata,
    graph_required_streaming_extras,
)
from etlantic.streaming.registry import (
    REGISTRY_PROTOCOL,
    CompatibilityMode,
    InMemorySchemaRegistry,
    SchemaFormat,
    SchemaIdentity,
    SchemaRegistryProvider,
    schema_fingerprint,
)
from etlantic.streaming.semantics import (
    Boundedness,
    LatenessPolicy,
    StreamSemantics,
    StreamTrigger,
    TimeDomain,
    WatermarkSpec,
)
from etlantic.streaming.trust import registry_adapter_allowed

__all__ = [
    "CONTROL_NODE_KINDS",
    "DLQ_CODES",
    "DYN_CODES",
    "ENVELOPE_SCHEMA_V1",
    "EXPANSION_METADATA_KEY",
    "REGISTRY_PROTOCOL",
    "REG_CODES",
    "STATE_SCHEMA_V1",
    "STREAMING_EXTRAS",
    "STREAMING_METADATA_KEY",
    "STREAMING_SCHEMA",
    "STR_CODES",
    "Boundedness",
    "ChangeEnvelopeMetadata",
    "ChangeOp",
    "ChildExpansion",
    "CompatibilityMode",
    "ExpansionBounds",
    "ExpansionSpec",
    "HandoffResult",
    "InMemoryDeadLetterStore",
    "InMemoryRecord",
    "InMemorySchemaRegistry",
    "InMemoryStreamSink",
    "InMemoryStreamSource",
    "InMemoryTriggerQueue",
    "LatenessPolicy",
    "OffsetAdvanceRule",
    "RecordErrorOutcome",
    "RecordErrorPolicy",
    "SchemaFormat",
    "SchemaIdentity",
    "SchemaRegistryProvider",
    "SnapshotCut",
    "StreamSemantics",
    "StreamStateRecord",
    "StreamTrigger",
    "TimeDomain",
    "WatermarkSpec",
    "assert_no_payload",
    "child_identity",
    "dlq_diagnostic",
    "dyn_diagnostic",
    "evaluate_handoff",
    "expand_children",
    "expand_plan_metadata",
    "expansion_metadata",
    "graph_required_streaming_extras",
    "handoff_failure_diagnostic",
    "is_control_kind",
    "migrate_envelope_dict",
    "migrate_state_dict",
    "reg_diagnostic",
    "registry_adapter_allowed",
    "reject_python_branch",
    "schema_fingerprint",
    "str_diagnostic",
]
