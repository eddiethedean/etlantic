---
title: Migration from ETLantic 0.54 to 0.55
status: published
current_minor: "0.55"
---

# Migration from 0.54 to 0.55

> **Status: ETLantic 0.55.0 Beta release.**

## Existing pipelines

Class-authored `Data`, `Transformation`, and `Pipeline` definitions remain the
default API. Existing 0.54 pipelines do not need to be rewritten to upgrade.
Install core and any first-party plugins from the published `0.55.0` line.
Plugin requirements now use
`etlantic>=0.55.0,<0.56`.

## Optional data-first authoring

0.55 adds the Experimental inferred-model facade. Start with a bounded source
and review its schema, diagnostics, and provenance before using previews or
exporting a definition. Supply hints when inference reports unknown or
provisional types. Use a stable source binding for durable definitions; a
one-shot iterator is single-use and cannot be durably rebound without an
explicit source factory or key.

Target observations are read-only. Existing target constraints do not rewrite
the observed source schema. A missing target produces a proposal only after an
explicit create intent and qualified provider capability. Recheck a pinned
target revision before publication.

## Qualification limits

The inferred-model feature remains Experimental and is qualified only for the
surfaces and modes in the [0.55 evidence index](evidence/inference_0_55/index.json).
In particular, some providers are metadata-only, Parquet and registry
inspection are read-only, and qualified write modes currently use the
transactional SQLite reference target. See [What's new in 0.55](../01_GETTING_STARTED/WHATS_NEW_0_55.md)
before adopting a provider outside that scope.

The 0.54 adaptive execution qualification is pinned to exact package versions
and does not carry forward to 0.55. The 0.55 package therefore rejects adaptive
execution until a new version-matched candidate passes its qualification gate.
Keep explicit execution profiles for 0.55 deployments in the meantime; the
0.54 adaptive evidence and usage guide remain historical records.

## Package versions

Core and all first-party distributions move together to `0.55.0`. Do not mix
0.54 and 0.55 first-party plugins in one environment. Third-party plugins
should update their tested compatibility bounds and rerun the public
`etlantic.testing` conformance suite before claiming 0.55 support.
