# Specifications

This directory contains normative specifications owned by the ETLantic
ecosystem.

- [DTCS 1.0 Specification](DTCS_SPEC.md) defines transformation-contract
  semantics.
- [DPCS 1.0 Specification](DPCS_SPEC.md) defines pipeline-contract semantics.
- [Portable Transformation IR](PORTABLE_TRANSFORM_IR_SPEC.md) proposes
  ETLantic's DTCS Transformation Plan profile. DTCS remains the normative
  authority and the public `dtcs` package will own canonical plan models. It is
  not implemented in ETLantic 0.10.

ODCS is an external standard and is not copied into this repository. See the
[ODCS Integration Guide](../03_DATA_CONTRACTS/ODCS.md) for ETLantic's
relationship with the upstream specification.

## Normative Versus Integration Documentation

Normative specifications define contract meaning with requirement language such
as `MUST`, `SHOULD`, and `MAY`.

Integration guides explain how ETLantic authors, loads, validates,
generates, and references those contracts:

- [ODCS Integration](../03_DATA_CONTRACTS/ODCS.md)
- [DTCS Integration](../04_TRANSFORMATIONS/DTCS.md)
- [DPCS Integration](../05_PIPELINES/DPCS.md)

ETLantic implementation details must not silently redefine normative
contract semantics.

The canonical current DTCS publication is
[DTCS `SPEC.md`](https://github.com/eddiethedean/dtcs/blob/main/SPEC.md). The
vendored `DTCS_SPEC.md` supports local documentation navigation and may lag the
publisher's latest revision; when they differ, the published DTCS repository is
authoritative.

The proposed standards delta required for rich PySpark-inspired portable
authoring is tracked in the
[DTCS Portable Relational Change Proposal](../11_DEVELOPMENT/DTCS_PORTABLE_SPEC_PROPOSAL.md).
