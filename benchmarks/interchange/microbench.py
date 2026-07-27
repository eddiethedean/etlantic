"""Cross-engine interchange planning microbenchmark."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etlantic.interchange.tabular import (  # noqa: E402
    SCHEMA,
    CopyEligibility,
    InterchangeDescriptor,
    InterchangeMechanism,
)
from etlantic.interchange.tabular.reconcile import (  # noqa: E402
    build_interchange_evidence,
    interchange_evidence_refs,
    reconcile_interchange_evidence,
)


def _descriptor() -> InterchangeDescriptor:
    fp = "b" * 64
    mechanism = InterchangeMechanism.RECORDS_FALLBACK
    copy = CopyEligibility.COPY_REQUIRED
    return InterchangeDescriptor(
        schema=SCHEMA,
        mechanism=mechanism,
        producer_engine="polars",
        consumer_engine="pandas",
        producer_caps=(mechanism.value,),
        consumer_caps=(mechanism.value,),
        schema_fingerprint=fp,
        ownership="copied",
        batching="collected",
        collection=True,
        copy_eligibility=copy,
        fallback_reason="bench",
        evidence_refs=interchange_evidence_refs(
            schema_fingerprint=fp,
            mechanism=mechanism,
            copy_eligibility=copy,
        ),
    )


def bench_reconcile(*, iterations: int = 20) -> float:
    planned = _descriptor()
    samples = []
    for _ in range(iterations):
        started = time.perf_counter()
        observed = build_interchange_evidence(
            descriptor=planned,
            value_before=[{"id": 1}],
            value_after=[{"id": 1}],
        )
        reconcile_interchange_evidence(planned, observed)
        samples.append(time.perf_counter() - started)
    samples.sort()
    return samples[len(samples) // 2]


def run_all() -> dict[str, float]:
    return {"interchange.reconcile": bench_reconcile()}


if __name__ == "__main__":
    print(json.dumps(run_all(), indent=2, sort_keys=True))
