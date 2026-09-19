---
status: experimental
since: "0.54.0"
current_minor: "0.54"
audience: developer
---

# Adaptive 0.54 evidence

The frozen case catalogue is coverage metadata, not passing execution evidence.
Observations are generated from actual runs with UTC times, Git commit/tree,
source-before/after digests, full pytest IDs, package/environment pins, actual
command/CI identity and sanitized outcome hashes. Source changes invalidate a run.

The local observation describes only the environment that actually generated it.
Remote cells remain absent until CI runs. Synthetic test envelopes live only in
temporary test directories and are never committed as CI proof. Historical
0.53 evidence is preserved with its provenance caveat (#147), not rewritten.

The packaged graduation record remains pending. Conformance and index integrity
do not grant approval. See the [local gate](../../EXIT_GATE_0_54.md).
