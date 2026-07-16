"""Write-intent helpers for the reference SQL plugin."""

from __future__ import annotations

from pipelantic.sql.protocol import WriteIntentKind

SUPPORTED_WRITE_INTENTS = frozenset(
    {
        WriteIntentKind.APPEND,
        WriteIntentKind.INSERT_SELECT,
        WriteIntentKind.REPLACE,
        WriteIntentKind.SNAPSHOT,
        WriteIntentKind.MERGE,
    }
)


def requires_atomic_publication(intent: WriteIntentKind) -> bool:
    return intent in {WriteIntentKind.REPLACE, WriteIntentKind.SNAPSHOT}
