"""In-process FakeKafka (partitions, rebalance, outage, transactions)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


def live_bootstrap() -> str | None:
    """Return live broker address when opt-in env is set (never required in CI)."""
    value = str(os.environ.get("ETLANTIC_KAFKA_BOOTSTRAP") or "").strip()
    return value or None


@dataclass
class FakeKafka:
    """Deterministic in-memory broker. Payloads stay on the broker, not in plans."""

    partitions: int = 3
    outage: bool = False
    generation: int = 0
    log: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    committed: dict[str, dict[int, int]] = field(default_factory=dict)
    txn_open: dict[str, list[tuple[int, dict[str, Any]]]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for index in range(self.partitions):
            self.log.setdefault(index, [])

    def inject_outage(self, value: bool = True) -> None:
        self.outage = value

    def rebalance(self) -> int:
        self.generation += 1
        return self.generation

    def produce(
        self, partition: int, record: dict[str, Any], *, txn: str | None = None
    ) -> None:
        if self.outage:
            raise ConnectionError("fake kafka outage")
        if txn:
            self.txn_open.setdefault(txn, []).append((partition, record))
            return
        self.log[partition].append(record)

    def begin_txn(self, txn: str) -> None:
        self.txn_open[txn] = []

    def commit_txn(self, txn: str) -> None:
        for partition, record in self.txn_open.pop(txn, ()):
            self.log[partition].append(record)

    def abort_txn(self, txn: str) -> None:
        self.txn_open.pop(txn, None)

    def fetch(self, partition: int, offset: int) -> list[dict[str, Any]]:
        if self.outage:
            raise ConnectionError("fake kafka outage")
        return list(self.log.get(partition, [])[offset:])

    def commit_offset(self, group: str, partition: int, offset: int) -> None:
        self.committed.setdefault(group, {})[partition] = offset
