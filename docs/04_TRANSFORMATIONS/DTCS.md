# DTCS

## Overview

ETLantic adopts the **Data Transformation Contract Standard (DTCS)** as the
canonical portable representation of transformation contracts.

DTCS defines **what a transformation means**. ETLantic provides the
Python-first authoring experience and generates DTCS artifacts from typed
transformation classes.

The DTCS specification is the normative definition of transformation semantics.
This document explains how ETLantic integrates with that specification.

---

## Why ETLantic Uses DTCS

Transformation logic should be portable.

Developers should define a transformation once and reuse it across different
execution engines without changing its logical interface.

DTCS provides a vendor-neutral representation of:

- inputs
- outputs
- parameters
- metadata
- transformation identity
- compatibility information

ETLantic treats DTCS as the portable artifact for transformation
definitions.

---

## Architectural Relationship

```text
Python Transformation
        │
        ▼
Transformation
        │
        ▼
ETLantic
        │
        ▼
DTCS Artifact
        │
        ▼
Execution Planning
```

ETLantic owns the Python API.

DTCS owns the portable transformation representation.

---

## Code-First Workflow

Developers author transformations in Python.

```python
class NormalizeCustomers(Transformation):
    customers: Input[RawCustomer]
    minimum_age: Parameter[int] = 18
    result: Output[Customer]
```

ETLantic generates the corresponding DTCS artifact.

In a code-first project, the Python class remains the authoring source of
truth.

---

## Contract-First Workflow

ETLantic may load existing DTCS artifacts and reconstruct transformation
definitions through its public loading APIs.

Whether authored in Python or imported from DTCS, transformations participate
in planning and validation the same way.

---

## Generated DTCS Artifacts

A transformation may generate:

```text
contracts/
└── transformations/
    └── normalize-customers.dtcs.yaml
```

Generated artifacts should be deterministic so they can be reviewed in version
control and reproduced in CI.

---

## Validation

ETLantic validates transformation contracts before execution.

Examples include:

- input compatibility
- output compatibility
- parameter types
- implementation signatures
- required metadata
- DTCS version compatibility

Planning should fail before execution when required DTCS semantics cannot be
satisfied.

## Portable Transformation Plans (0.11+)

DTCS already defines the implementation-independent Transformation Plan,
expressions, functions, semantic actions, and engine capability model.
The proposed `dtcs.transform-plan/1` package model is the concrete, closed
realization of that DTCS model. `etlantic.transform/1` is its ergonomic
authoring profile—not a separate source of transformation meaning.

`@Transformation.portable` provides the PySpark-inspired Python authoring
surface. Generated DTCS may carry the normalized Transformation Plan, while
plugins compile it into backend Execution Plans. If ETLantic-specific syntax
and DTCS semantics disagree, DTCS remains authoritative.

ETLantic and DTCS share a publisher. Portable design requirements may therefore
drive coordinated DTCS specification and package releases. ETLantic waits for
the relevant public `dtcs` models and version before treating the behavior as
normative or compiler-ready.

---

## Identity and Versioning

Every published transformation should expose a stable identity.

Typical metadata includes:

- identifier
- version
- description
- owner
- tags

Compatibility decisions should follow the DTCS specification and ETLantic's
planning rules.

---

## Relationship to Implementations

DTCS describes the logical transformation.

Execution implementations remain separate.

Portable compiler implementations also remain separate: the DTCS artifact
describes semantic intent, while Polars, Pandas, SQL, and PySpark plugins
provide backend lowering.

```python
@NormalizeCustomers.implementation("polars")
def normalize(...):
    ...
```

```python
@NormalizeCustomers.implementation("pandas")
def normalize(...):
    ...
```

Multiple implementations may satisfy the same DTCS contract.

---

## Relationship to ODCS and DPCS

The three standards complement one another.

```text
ODCS
  Data Contracts
      │
      ▼
DTCS
  Transformation Contracts
      │
      ▼
DPCS
  Pipeline Contracts
```

ETLantic unifies these standards through strongly typed Python models.

---

## Design Principles

ETLantic follows these principles when integrating with DTCS:

- Python classes are the preferred authoring interface.
- DTCS is the portable artifact.
- Types define transformation interfaces.
- Implementations are interchangeable.
- Planning precedes execution.
- Generated artifacts are deterministic.

---

## Further Reading

For the normative definition of DTCS, refer to the
[DTCS 1.0 Specification](../specifications/DTCS_SPEC.md).

This document describes **how ETLantic integrates with DTCS**, not the DTCS
specification itself.
