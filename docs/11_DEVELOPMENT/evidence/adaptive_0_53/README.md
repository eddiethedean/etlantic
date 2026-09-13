---
status: Experimental
---

# Adaptive execution 0.53 qualification

`scripts/check_adaptive_0_53.py` executes the adaptive planner, both protected
Sol review suites and the real-backend physical qualification campaign.
Required tests must execute and pass: skipped tests cannot qualify support.
The campaign covers five-family empty/nullable differential execution, exact
branch and directional dual-port patterns, partial scopes, finite collection,
local checkpoints/reuse, definite publication failure, atomic file overwrite
and qualified executor lifecycle/port ownership.

Run `uv sync --locked --group dataframes`, then install the exact qualified
backends with `uv pip install "polars==1.42.1" "pandas==2.3.3" "pyarrow==25.0.0"`.
Core and first-party plugin distributions are 0.52.1 on this development base.
Installation alone grants no qualification.

Use `--write` to record observed results (including failures); it does not grant
release approval. The default verifier runs the campaign afresh without writing
and requires matching source fingerprints, executed test identities/statuses,
and digests of the committed sanitized JUnit and aggregate process observations.
Evidence excludes captured logs, exception payloads, source rows and credentials.
A failed/conflicted record deliberately fails the verifier until Sol adjudicates
the protected verification contract and the complete campaign passes.

The packaged `etlantic.runtime/adaptive_support.json` is independent of submitted
plan topology and generated run fingerprints. It restricts matching to exact
logical/port shapes, contiguous target assignments and qualified dependency
versions. Compute units are currently unfused; a fused realization requires its
own passing signature and is rejected by these rows.

CI executes qualification on Linux, macOS and Windows with Python 3.11, 3.12 and
3.13, retaining separate environment proof artifacts. Those jobs must actually
pass before any environment qualification claim; local macOS evidence does not
stand in for the remaining CI environments. All functionality remains
Experimental pending the independent 0.54 qualification decision.
