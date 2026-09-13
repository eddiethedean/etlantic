# Exit Gate 0.52 — Deterministic Adaptive Planning

> **Status: 0.52.0 planning release published.**

The release claim is limited to deterministic, side-effect-free adaptive plan
generation and inspection. Generated plans contain a complete candidate matrix,
canonical six-term objective plus target vectors, content-bound region and
transfer identities, bounded explain summaries, and validated physical DAG
provenance. Resource limits reject before retained-object construction.

Explicit `/1` planning remains available and unchanged. Adaptive execution,
external compilation, control-plane acceptance, streaming, and runtime-expanded
graphs remain unavailable and reject before external I/O. Native implementation
bodies remain explicit `/1` escape hatches.

Validation commands:

```bash
etlantic validate TARGET --format json
etlantic plan TARGET --format json
python scripts/check_adaptive_0_52.py
python scripts/check_portable_0_50.py
```

Rollback by repinning the complete 0.51.x package set and using explicit
profiles. Never feed `/2` documents to 0.51 readers.
