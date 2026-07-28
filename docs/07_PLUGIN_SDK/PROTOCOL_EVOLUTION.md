# Protocol Evolution Policy

> **Status (0.28.0):** Plugin `/1` families are **frozen in 0.28.0** for the
> core 1.0 path (`dataframe`, `sql`, `spark`, `orchestration`,
> `transform-compiler`). `etlantic.scheduler/1` remains provisional (not on the
> freeze path). External feedback evidence:
> [EXTERNAL_PLUGIN_FEEDBACK.md](../11_DEVELOPMENT/EXTERNAL_PLUGIN_FEEDBACK.md).
> Prior freeze-eligible status:
> [EXIT_GATE_0_27](../11_DEVELOPMENT/EXIT_GATE_0_27.md).

## Freeze decision (0.28)

| Criterion | Status | Owner |
|---|---|---|
| First-party plugins exercise public `etlantic.testing` in CI | Met (0.22+) | Maintainers |
| Out-of-monorepo `etlantic-plugin-echo` CI workflow | Met | Maintainers |
| Packaging / manifest gates | Met | Maintainers |
| ≥1 documented external feedback cycle from a non-first-party plugin author | **Met** — see [EXTERNAL_PLUGIN_FEEDBACK.md](../11_DEVELOPMENT/EXTERNAL_PLUGIN_FEEDBACK.md) | Maintainers + community |
| No unresolved provisional core protocol on the 1.0 path | Met (`scheduler/1` excluded from freeze path) | Maintainers |

**Decision:** Declare core Plugin SDK `/1` **frozen in 0.28.0**. Only additive
optional evolution within `/1` is permitted; incompatible changes require a
new protocol major. CI gate: `scripts/check_protocol_freeze.py`.

## Freeze decision (0.27) — historical

0.27 triple-minor burn-in and second-wave removals left freeze owned by 0.28.
The external feedback criterion was not cleared in 0.27; see table above.

## Freeze decision (0.26) — historical

0.26 dual-minor burn-in and first-wave removals left freeze owned by 0.27.
0.27 executed triple-minor burn-in and second-wave removals but did **not** clear
the external feedback criterion; see table above.

## Freeze decision (0.25) — historical

0.25 published the open external feedback blocker and deferred closure to 0.26.
0.26 executed dual-minor burn-in and first-wave removals but did **not** clear
the external feedback criterion.

This document is the normative policy for evolving ETLantic plugin protocols
(`etlantic.dataframe/1`, `etlantic.sql/1`, `etlantic.spark/1`,
`etlantic.orchestration/1`, `etlantic.transform-compiler/1`,
`etlantic.scheduler/1`, and related wire schemas). It complements
[Capability Vocabulary](CAPABILITY_VOCABULARY.md),
[Testing Plugins](TESTING_PLUGINS.md),
[Building a Plugin](BUILDING_A_PLUGIN.md), and
[Distribution](DISTRIBUTION.md).

## Freeze glossary (three different terms)

Do not conflate these:

| Term | What freezes | Status in 0.28 |
|---|---|---|
| **Contract / configuration freeze** | Authoring contracts, Profile trust fields, and related config surfaces stop incompatible churn without migration notes | Shipped since **0.19** (see [Deprecation Policy](../11_DEVELOPMENT/DEPRECATION_POLICY.md)) |
| **Plan immutability** | Plan graphs use fingerprint verify + `deep_freeze` on nested mappings/lists/sets; dataclasses and unknown objects are **not** recursively frozen | Shipped helper; not full object-graph immutability |
| **Protocol `/1` freeze** | Plugin protocol majors lock required methods and incompatible wire meaning | **Frozen in 0.28.0** for core `/1` families |

Wire schemas marked “wire-stable” mean schema ids keep meaning under the additive `/1` rules above; they do **not** imply protocol `/1` freeze.

## Goals

- Let third-party plugins implement against public protocols without depending
  on first-party engine identity.
- Make optional behaviour negotiable and inspectable.
- Separate **protocol compatibility** from **production trust**.
- Freeze `/1` only after external proof, not merely because a core minor ships.

## Protocol identifiers

Protocol ids use the form `etlantic.<family>/<major>` (for example
`etlantic.dataframe/1`). The major component is the compatibility boundary:

| Change | Allowed within `/1`? | Action |
|---|---|---|
| Add optional method / capability | Yes | Advertise; negotiate |
| Tighten required behaviour of an existing method | No | New major (`/2`) |
| Remove or rename a required method | No | New major |
| Expand capability vocabulary with implications | Yes (vocab major) | See vocabulary policy |
| Change wire schema meaning incompatibly | No | New schema id |

Capability vocabulary versions (`etlantic.capabilities/1`) evolve
**independently** of protocol majors. See
[Capability Vocabulary](CAPABILITY_VOCABULARY.md).

## Optional-method negotiation

Protocols may expose optional methods or capability-gated behaviours.

Rules:

1. **Advertise before relying.** Plugins must declare the matching capability
   (or protocol method) in `PluginCapabilities` / manifest entries before the
   planner or runtime may select that path.
2. **Fail closed on missing optionals.** Callers must not assume an optional
   method exists. Use capability checks or `getattr`/`hasattr` negotiation;
   never call an undeclared optional and swallow `AttributeError` as success.
3. **Overstated claims fail conformance.** Public suites in `etlantic.testing`
   assert claim consistency and, where probed, behaviour truthfulness. See
   [Testing Plugins](TESTING_PLUGINS.md).
4. **Required methods stay required.** Making a required method optional, or
   optional required, is a new protocol major.

## Support windows vs package pins

While ETLantic is pre-1.0:

- **Core minor pin:** plugin packages should declare
  `etlantic>=X.Y,<X.(Y+1)` (for 0.28: `etlantic>=0.29.0,<0.30`).
- **Protocol major:** a plugin that implements `etlantic.dataframe/1` remains
  protocol-compatible across core minors that still speak `/1`, subject to the
  package pin above.
- **Support window:** first-party plugins match the core minor. Third-party
  plugins own their support window; ETLantic documents which protocol majors
  the current core speaks, not a multi-year LTS for every third-party wheel.
- **Deprecation:** demotions and renames ship with migration notes and
  warn-once compatibility aliases before removal.

Use `etlantic plugin compatibility` to evaluate an installed plugin's
manifest and packaging metadata against the running core (protocol ranges,
capability vocabulary, plan schema, Requires-Python, core pin, allowlist).

## Compatibility ≠ production trust

Passing protocol negotiation or `etlantic plugin compatibility` means the
plugin **speaks the right dialects**. It does **not** grant production trust.

Production trust still requires:

- Non-empty `Profile.plugin_allowlist` (fail closed) for production profiles
- Authorize-before-load plugin lifecycle / manifests
- `SafeIoPolicy` and related IO / outbound controls
- Secret-free plans, reports, and diagnostics
- Conformance suites for advertised capabilities

A compatible but non-allowlisted plugin must not load in production. An
allowlisted plugin that overstates capabilities must still fail conformance.

## Manifests and discovery

Plugins ship `etlantic-plugin-manifest.json` (schema
`etlantic.plugin_manifest/1`) with:

- `protocol_range` — opaque ids and/or version-like ranges the package supports
- `entries[].protocol` — per entry-point protocol id
- `capabilities` — coarse package-level capability tags

Discovery authorizes manifests before importing entry points. See
[Distribution](DISTRIBUTION.md) and [Building a Plugin](BUILDING_A_PLUGIN.md).

## Pre-freeze eligibility criteria for `/1` (historical)

Protocol `/1` families are **frozen in 0.28.0** (see freeze decision table
above). Before freeze, `/1` became freeze-eligible when all of the following
held:

1. First-party plugins exercise **only** public `etlantic.testing` suites in CI
2. At least one out-of-monorepo reference plugin
   (`etlantic-plugin-echo` or equivalent) is green against published/workspace
   core via public suites + `etlantic plugin compatibility`
3. External feedback cycles documented in
   [EXTERNAL_PLUGIN_FEEDBACK](../11_DEVELOPMENT/EXTERNAL_PLUGIN_FEEDBACK.md)
   and [EXIT_GATE_0_22](../11_DEVELOPMENT/EXIT_GATE_0_22.md) are complete
   (default: freeze after **N ≥ 1** external feedback cycles post-RC)
4. No unresolved architectural dependency on first-party engine identity sets

After freeze, only additive optional methods and vocabulary clarifications may
land in core minors that still speak `/1`. Incompatible changes require `/2`.
Historical note: 0.22 marked the Plugin SDK as release-candidate quality; that
did **not** freeze `/1` — freeze closed in **0.29.0**.

## Related commands and docs

```bash
etlantic plugin list --format json
etlantic plugin compatibility etlantic-polars --format json
```

- [Capability Vocabulary](CAPABILITY_VOCABULARY.md)
- [Testing Plugins](TESTING_PLUGINS.md)
- [Building a Plugin](BUILDING_A_PLUGIN.md)
- [Distribution](DISTRIBUTION.md)
- [External plugin feedback](../11_DEVELOPMENT/EXTERNAL_PLUGIN_FEEDBACK.md)
- [CLI reference](../10_REFERENCE/CLI.md)
- [Surface inventory](../10_REFERENCE/SURFACE_INVENTORY.md)
