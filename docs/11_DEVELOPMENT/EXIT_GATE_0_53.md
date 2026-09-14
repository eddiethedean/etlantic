# Exit Gate 0.53 — Local Adaptive Physical-DAG Execution

Status: **0.53.0 release candidate; adaptive execution remains Experimental.**

The release boundary is the 24 acceptance criteria in the
[approved implementation contract](IMPLEMENTATION_PLAN_0_53.md). Local static
batch execution is limited to the packaged exact topology/port, policy, I/O,
contract and dependency-version rows. The five required families are Local,
Polars, Pandas, Polars→Pandas and Pandas→Polars, with one directional cut.

Whole-DAG admission precedes resources and I/O. Stored physical dependencies
and pinned descriptors remain execution authority. Only publication commits;
failure, cancellation, deadlines, cleanup and reconciliation preserve the
documented logical outcomes and ownership barriers. Explicit `/1` compatibility
and valid historical `/2` reader compatibility remain required.

Before tagging `v0.53.0`, require:

1. All in-scope ACs and previous blockers pass independent Sol review.
2. Core and every first-party package declare 0.53.0, synchronized manifests,
   compatible minor ranges and a current lockfile.
3. Default non-writing historical and physical evidence verifiers pass, and
   qualification scenarios execute without skips.
4. Existing CI checks pass on the exact candidate commit, including
   Linux/macOS/Windows × Python 3.11/3.12/3.13 qualification, optional backend
   checks, docs, typing/lint, security/static gates and package builds.
5. Built candidate wheels import with optional dependencies absent or present
   as documented. Release notes and migration guidance match the candidate.

Evidence and exact backend versions:
[adaptive 0.53 qualification](evidence/adaptive_0_53/README.md).

No tag, GitHub release or PyPI upload is created by preparing this candidate.
The existing tag-triggered Release workflow publishes only after its checks.
Native adaptive bodies, additional engines, durable/remote/dynamic execution,
arbitrary topologies and phase 0.54 availability graduation remain excluded.
