# Specifications

This directory contains normative specifications owned by the ETLantic
ecosystem.

- [DTCS 3.0 Specification](https://github.com/eddiethedean/dtcs/blob/main/SPEC.md)
  is the canonical transformation-semantics specification. Version 3.0.0
  supersedes 2.0.0 and adds Rich Portable Analytics with
  `dtcs.transform-plan/2` and independently claimable semantic-family
  profiles.
- [DTCS in this docs site](https://etlantic.readthedocs.io/en/latest/specifications/DTCS/) summarizes the current authority and
  profile inventory for ETLantic readers.
- [Vendored DTCS 1.0 snapshot](https://etlantic.readthedocs.io/en/latest/specifications/DTCS_SPEC/) is retained only for historical
  comparison and must not be treated as current authority.
- [DPCS 1.0 Specification](https://etlantic.readthedocs.io/en/latest/specifications/DPCS_SPEC/) defines pipeline-contract semantics.
- [Portable Transformation IR](https://etlantic.readthedocs.io/en/latest/specifications/PORTABLE_TRANSFORM_IR_SPEC/) records
  ETLantic's authoring and compiler requirements on top of published DTCS
  plan/profile semantics. The canonical models live in `dtcs>=0.13`; the
  ETLantic authoring API has shipped since 0.11, with portable compiler
  capabilities added through 0.14.

[ODCS](https://etlantic.readthedocs.io/en/latest/03_DATA_CONTRACTS/ODCS/) is an external standard and is not copied
into this repository. See the
[ODCS Integration Guide](https://etlantic.readthedocs.io/en/latest/03_DATA_CONTRACTS/ODCS/) for ETLantic's
relationship with the upstream specification.

## Normative Versus Integration Documentation

Normative specifications define contract meaning with requirement language such
as `MUST`, `SHOULD`, and `MAY`.

Integration guides explain how ETLantic authors, loads, validates,
generates, and references those contracts:

- [ODCS Integration](https://etlantic.readthedocs.io/en/latest/03_DATA_CONTRACTS/ODCS/)
- [DTCS Integration](https://etlantic.readthedocs.io/en/latest/04_TRANSFORMATIONS/DTCS/)
- [DPCS Integration](https://etlantic.readthedocs.io/en/latest/05_PIPELINES/DPCS/)

ETLantic implementation details must not silently redefine normative
contract semantics.

The canonical current DTCS publication is
[DTCS `SPEC.md`](https://github.com/eddiethedean/dtcs/blob/main/SPEC.md). The
vendored `DTCS_SPEC.md` supports local documentation navigation and may lag the
publisher's latest revision; when they differ, the published DTCS repository is
authoritative.

Publication history:

- [DTCS 2.0 Portable Relational Publication Record](https://etlantic.readthedocs.io/en/latest/11_DEVELOPMENT/DTCS_PORTABLE_SPEC_PROPOSAL/)
- [DTCS 3.0 Rich Portable Analytics Publication Record](https://etlantic.readthedocs.io/en/latest/11_DEVELOPMENT/DTCS_3_0_SPEC_PROPOSAL/)
