# DTCS 3.0 (canonical)

The current Data Transformation Contract Standard is published upstream:

**[DTCS SPEC.md](https://github.com/eddiethedean/dtcs/blob/main/SPEC.md)**

**Version 3.0.0** supersedes 2.0.0. It retains DTCS 2.0 identifier meanings
and adds Rich Portable Analytics: bounded lambda Expressions, advanced
string/regex Functions, strict conversions, statistical aggregates, complex
value transforms, reshape/set actions, IANA temporal semantics, controlled
nondeterminism, structural nested-field evolution, expanded capability
profiles, and canonical Transformation Plan serialization
`dtcs.transform-plan/2`.

Installable packages use `dtcs>=0.13`. Valid `dtcs.transform-plan/1`
artifacts remain readable; migration to plan v2 MUST NOT change 2.0
semantics.

## Profiles (summary)

Published DTCS 2.0 families remain available:

- `dtcs:profile/portable-relational-kernel/1`
- `dtcs:profile/portable-relational/1`
- `dtcs:profile/portable-window/1`
- `dtcs:profile/portable-complex-types/1`

DTCS 3.0 adds independently claimable families (see SPEC Chapter 27 /
Appendix A.9), including:

- `dtcs:profile/portable-relational-kernel/2` (Candidate)
- `dtcs:profile/portable-relational/2` (Candidate)
- `dtcs:profile/portable-string-advanced/1` (Experimental)
- `dtcs:profile/portable-conversion/1` (Experimental)
- `dtcs:profile/portable-statistics/1` (Experimental)
- `dtcs:profile/portable-complex-values/1` (Experimental)
- `dtcs:profile/portable-reshape/1` (Experimental)
- `dtcs:profile/portable-relational-extended/1` (Experimental)
- `dtcs:profile/portable-temporal-iana/1` (Experimental)
- `dtcs:profile/portable-nondeterministic/1` (Experimental)
- `dtcs:profile/portable-window/2` (Candidate)

ETLantic 0.10 consumes the `dtcs` toolkit models only. Portable authoring
(`etlantic.transform`, `@Transformation.portable`) and backend compilers
remain planned for 0.11–0.15.

## Local archives

- [DTCS 1.0 snapshot](DTCS_SPEC.md) — historical comparison only
- DTCS 2.0 publication history:
  [Portable Relational Publication Record](../11_DEVELOPMENT/DTCS_PORTABLE_SPEC_PROPOSAL.md)

## Related

- [Specifications overview](README.md)
- [DTCS integration in ETLantic](../04_TRANSFORMATIONS/DTCS.md)
- [Portable Transformation IR (ETLantic requirements)](PORTABLE_TRANSFORM_IR_SPEC.md)
- [DTCS 3.0 Rich Portable Analytics publication record](../11_DEVELOPMENT/DTCS_3_0_SPEC_PROPOSAL.md)
