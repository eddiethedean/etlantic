---
title: Adaptive 0.52 release-blocker remediation
description: Traceability, historical compatibility, unique logical paths, and deterministic resource accounting.
---

# Adaptive 0.52 release-blocker remediation

This change addresses FINAL-052-015 through FINAL-052-018. It does not grant
adaptive execution authority or change the public `/1` or `/2` schema versions.

## FINAL-052-015: executable issue ledger

[The issue ledger](phase_0_52_issue_ledger.json) maps all 36 issues required by
[the approved plan](IMPLEMENTATION_PLAN_0_52.md) to implementation symbols,
acceptance criteria and executable tests. The evidence verifier rejects missing
or duplicate issues, missing symbols, in-scope deferrals and unexecuted proofs.
It binds the ledger digest into every generated evidence artifact. Historical
GitHub issue wording about runtime admission does not authorize execution in
0.52; the ledger explicitly identifies the 0.53/0.54 non-scope.

The audit also found issue #49's generic pushdown lookup still present. Advisory
optimization now treats predicate and projection independently, using canonical
capability tokens from static, source-addressed `connector_capabilities` records
in the existing `EvidenceStore`. Unknown, conflicting, expiring and non-static
evidence cannot authorize a proposal. Engine negotiation and legacy generic
flags are not connector proof. This correction adds neither I/O nor discovery
to optimization, and does not apply optimization to adaptive plans.

## FINAL-052-016: historical reader compatibility

Logical-path completeness is enforced for documents marked with planner version
0.52. Historical 0.51 hand-built `/2` documents retain their wire-foundation
contract, including incomplete topology and short objectives. Structural wire
validation and fingerprint verification remain active. Regression tests cover
both reader verification modes and a serialization round trip.

## FINAL-052-017: unique logical-edge realization

Generated plans require exactly one data path for every logical edge. Counting
stops at intervening compute units, so transitive logical diamonds are not
mistaken for duplicate edge realizations. Counts saturate at two. Control and
lifecycle dependencies do not establish a data path. Cross-target transfers
carry port attribution to distinguish legitimate parallel port edges. Existing
metadata-independent disconnection tests remain intact.

## FINAL-052-018: prospective live ownership

The context-local budget is shared by nested planning and projection operations.
The size pass streams bounded canonical UTF-8 chunks over borrowed fields;
it does not construct the buffer whose allocation it is admitting. Path-redacted
inventory views are borrowed until their exact retained size has been admitted.

Inventory, candidates, regions and physical boundary records receive their
canonical sizes plus record overhead before construction. Solver and independent
oracle frontier/incumbent records receive their canonical sizes plus 128 bytes.
Phase frames release temporary owners, including on exceptions. Incumbent
replacement releases the previous owner. Final plan fields borrow already-owned
records rather than charging them a second time. At return, ownership transfers
to the caller; the request ledger has no live charges.

Explain and serialization admit materialized output and owned buffers separately.
The public JSON writer accounts for its actual indentation and escaping.
Fingerprinting streams directly into SHA-256. Oversized explain detail is never
materialized; it becomes a deterministic summary. Oversized summary identifiers
are omitted in favor of counts and a content omission digest.

Tests exercise admission below/at/above limits, construction sentinels, cleanup,
the 256-node/8-target/2,048-cell maximum, the eight-reference truncation rule,
the millionth/next solver expansion and the exact 4 MiB explain threshold.
The transient gate is deterministic canonical accounting, not a promise about
Python heap size or peak RSS; neither RSS nor wall-clock time affects placement.

## Reproduction

Run `uv run python scripts/check_adaptive_0_52.py` for the non-writing executable
evidence gate. Regeneration requires `--write` and succeeds only after the full
referenced campaign passes. The unchanged review artifacts are supplemented by
`tests/plan/test_adaptive_final_remediation_0_52.py`. CI executes the same evidence
verifier on every supported OS/Python matrix row. A successful remediation run
is not a substitute for the independent production review and final release check.
