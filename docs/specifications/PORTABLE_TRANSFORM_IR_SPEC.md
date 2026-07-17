# ETLantic Profile for DTCS Portable Transformation Plans

Status: ETLantic integration profile draft over published DTCS 3.0 semantics
DTCS plan identifier: `dtcs.transform-plan/2` (v1 remains readable)  
ETLantic authoring profile: `etlantic.transform/1`  
Target milestones: 0.11 kernel through 0.15 advanced lowering

## 1. Scope

This specification defines ETLantic's closed, versioned, backend-independent
serialization and authoring profile for a DTCS Transformation Plan. DTCS owns
transformation semantics, expressions, functions, semantic actions, and engine
capability meaning. This specification defines how ETLantic realizes that
model through its authoring profile and the requirements its plugins MUST
preserve. Canonical plan models and semantic registries belong to the public
`dtcs` package.

It does not replace DTCS or define physical execution, storage, scheduling,
backend APIs, or arbitrary Python translation. Where this document and DTCS
conflict, DTCS is authoritative and this profile must be corrected or
versioned.

DTCS 3.0.0 and `dtcs` 0.13.0 are normative for Transformation Plan, Portable
Relational and Rich Portable Analytics profiles, registry, and conformance
semantics. DTCS 2.0.0 identifiers and `dtcs.transform-plan/1` remain readable.
The key words MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY in this document
apply only to ETLantic's authoring and compiler integration. They do not
redefine published DTCS meaning.

## 2. Architectural boundary

```text
Transformation ports and contracts
              +
Portable authoring expression
              ↓
TransformationIR
              ↓
Capability validation
              ↓
Backend compiler and execution plugin
```

The relationship is:

```text
DTCS Transformation Contract
            ↓
DTCS Transformation Plan semantics
            ↓
DTCS `dtcs.transform-plan/2` representation
(v1 remains readable)
            ↓
Backend Execution Plan
```

The IR MUST be immutable, deterministic, bounded, data-only, inspectable, and
free of executable objects and resolved secrets.

## 3. Document model

A serialized definition has this conceptual shape:

```json
{
  "protocol": "dtcs.transform-plan/2",
  "transformation_id": "example.NormalizeCustomers",
  "inputs": {
    "customers": {
      "contract_id": "example.RawCustomer"
    }
  },
  "parameters": {
    "minimum_age": {
      "type": {"kind": "integer"}
    }
  },
  "outputs": {
    "result": {
      "contract_id": "example.Customer",
      "expression": {"kind": "project"}
    }
  },
  "requirements": {
    "profiles": ["dtcs:profile/portable-relational-kernel/1"],
    "actions": ["dtcs:filter", "dtcs:project"],
    "functions": ["dtcs:concat_ws"]
  },
  "fingerprint": "..."
}
```

Canonical serialization MUST sort mapping keys, preserve expression-list
order, omit runtime values, and reject non-data objects. Fingerprints MUST be
computed from canonical semantic content rather than display metadata.
Compilers that claim only plan v1 MUST reject plans that require lambda
nodes or other v2-only constructs.

## 4. Type system

The IR uses the DTCS logical type vocabulary (2.0 retained in 3.0), independent
of backend-specific types:

```text
boolean
integer
decimal
string
binary
date
time
datetime
duration
list(element_type)
map(key_type, value_type)
object(fields)
tuple(element_types)
```

Boolean is the DTCS primitive used for predicates. Each value also carries its
DTCS value-state semantics: present, null, missing, or invalid. Plugins MUST
either preserve a declared type and state or report a capability/type error
before execution. Silent narrowing or state collapse is forbidden.

ETLantic authoring aliases such as `array` and `struct` MUST normalize to DTCS
`list` and `object`. Backend-width aliases such as `int64` MAY be accepted by
the facade only when normalization to the DTCS logical type loses no requested
semantic constraint. An unresolved authoring type MAY exist during partial
analysis but MUST NOT remain in a validated executable plan.

## 5. References

### 5.1 Input references

An `input` node identifies one declared `Input[T]` port. It MUST contain the
port identity and contract identity. It MUST NOT contain data or a live backend
handle.

### 5.2 Column references

A column reference contains a field name and optional relation identity.
Resolution MUST detect missing and ambiguous columns. Qualified names are
authoring conveniences; normalized IR uses stable relation identities.

### 5.3 Parameter references

A parameter reference identifies one declared `Parameter[T]`. Serialized IR
MUST contain its name and type but MUST NOT contain a runtime override or
secret value. Public non-secret defaults MAY appear in the transformation
contract, subject to bounded-literal rules.

### 5.4 Literals

Literals MUST be bounded, typed scalar or recursively bounded collection
values. Callables, modules, classes, backend objects, open resources, arbitrary
Python instances, and `SecretValue` objects are forbidden.

Implementations MUST provide configurable size, depth, and collection limits.
Secret-marked values MUST be represented by references and MUST NOT be encoded
as literals.

## 6. Structured expressions

DTCS 2.0 defines five structured expression node kinds:

- `literal`
- `fieldRef`
- `unary`
- `binary`
- `call`

DTCS 3.0 adds `lambda` for bounded higher-order expression bodies. Plan v2 MAY
contain lambda nodes; plan v1 MUST NOT. Lambda parameters bind with
`fieldRef` `scope: "lambda"` and MUST NOT capture undeclared outer names.

Aliases, sort direction, aggregate context, and window placement are expressed
by their containing action rather than by inventing additional expression node
kinds. The published operators are comparison (`eq`, `not_eq`, `lt`, `lte`,
`gt`, `gte`, `null_safe_eq`), boolean (`and`, `or`, `not`), arithmetic (`add`,
`subtract`, `multiply`, `divide`, `modulo`, `negate`), membership (`in`,
`between`), and access (`field`, `index`, `element_at`).

Every expression MUST have a stable operation or function identifier. Opaque
expressions and `repr()`-based serialization are forbidden.

## 7. Relational expressions

The DTCS dataset Semantic Actions (2.0 retained; 3.0 adds reshape/set families
via profiles) include `project`, `select`, `filter`,
`with_fields`, `rename_fields`, `drop_fields`, `aggregate`, `group`, `join`,
`sort`, `union`, `distinct`, `deduplicate`, `limit`, `partition`, `window`, and
`derive`. Field Semantic Actions are `lowercase`, `uppercase`, `capitalize`,
`trim`, `normalize_whitespace`, and `hash_sha256`.

PySpark-inspired ETLantic names are facade syntax only. For example,
`withColumn` and `withColumns` normalize to `with_fields`; `orderBy` and
`sort` normalize to `sort`; `dropDuplicates` normalizes to `deduplicate`; and
`unionByName` normalizes to `union` with mode `byName`. The serialized plan
MUST contain the DTCS action and its registered modes, not the facade spelling.

Nodes MUST reference child expressions structurally. Cycles are invalid.
Implementations MUST impose node-count and depth limits during loading and
validation.

Actions, writes, collection, display, and resource acquisition are not
relational expressions and MUST NOT appear in this IR.

## 8. Output binding

Each declared `Output[T]` MUST map to exactly one relational expression.
Undeclared output keys and missing declared outputs are invalid. Output role
(`valid`, `invalid`, or `side`) comes from the transformation contract and MUST
remain associated with the output through compilation and reporting.

## 9. Core semantics

### 9.1 Nulls

Portable evaluation distinguishes DTCS null, missing, and invalid value states.
Boolean expressions additionally have true and false values. Filtering retains
only rows whose predicate evaluates to true. The DTCS registry entry for the
filter action defines the treatment of false, null, missing, and invalid
predicates; compilers MUST NOT collapse those states.

Equality with null produces null. Authors use `isNull()` and `isNotNull()` for
null predicates. Plugins MUST NOT rewrite `value == null` into `is null`.

Missing and invalid are not null and MUST NOT be coerced to null unless a
standard registry entry explicitly defines that behavior. NaN is also not
null. Floating-point NaN behavior MUST be declared separately by
each operation whose backend behavior differs.

### 9.2 Boolean operators

`and`, `or`, and `not` operate according to DTCS-registered truth tables that
cover null, missing, and invalid. Plugins MUST NOT use host-language truthiness.

### 9.3 Numeric operations

Numeric promotion follows the least widening type capable of representing both
operands within the portable type lattice. Decimal precision and scale changes
MUST be deterministic and inspectable.

Integer overflow MUST fail unless an operation explicitly declares widening.
Silent wraparound is forbidden. Division by zero MUST produce a declared
portable error unless a future semantic mode explicitly selects another
behavior.

`round` uses half-even rounding unless the function explicitly selects another
mode.

### 9.4 Casts

Casts are explicit. A cast is either strict or tolerant:

- strict cast: invalid input fails the operation
- tolerant cast: invalid input produces null and requires explicit syntax

Plugins MUST NOT substitute tolerant behavior for strict behavior.

### 9.5 Strings

String length and substring offsets are defined in Unicode code points, not
encoded bytes. Index origins MUST be explicit in the function definition;
portable substring APIs use zero-based indexing even if a backend lowering uses
another convention.

Case conversion uses Unicode default case conversion. Locale-sensitive
behavior requires an explicit future function and capability.

### 9.6 Timestamps

Timestamp values are either timezone-aware or naive. Plugins MUST NOT silently
attach, remove, or change a timezone. Runtime profiles declare the timezone
used by functions such as `current_timestamp()` and timestamp parsing.

`current_timestamp()` is stable within one logical run. All occurrences in a
run resolve to the same logical instant.

### 9.7 Ordering

Relational outputs are unordered unless an explicit sort node exists. Sort
expressions specify direction and null placement. A plugin incapable of
preserving requested null placement MUST reject the plan.

Stable ordering among equal keys is not guaranteed unless an explicit total
ordering is declared.

### 9.8 Joins

Join kinds are `inner`, `left`, `right`, `full`, `semi`, `anti`, and `cross`.
Cross joins require explicit syntax. Null join keys do not match under ordinary
equality. Null-safe equality requires a distinct operator.

Column collisions MUST be resolved or diagnosed before execution. Plugins MUST
NOT invent backend-specific suffixes as portable output names.

### 9.9 Aggregation

Grouping treats null grouping keys as one group. Aggregate null behavior is
defined per function. `count(*)` counts rows; `count(column)` counts non-null
values. Aggregations over empty input MUST follow the registered function
semantics and output nullability.

### 9.10 Determinism

Operations and functions are classified as deterministic, run-stable, or
nondeterministic. Nondeterminism contributes requirements to the plan and MUST
affect cache, retry, and idempotency decisions.

## 10. Validation

Before compilation, ETLantic MUST validate:

1. protocol version and bounded structure
2. port and reference integrity
3. column resolution
4. expression typing and nullability
5. output contract compatibility
6. operation and function registration
7. plugin capability coverage
8. semantic-mode compatibility
9. secret and executable-object exclusion

Expected failures produce structured diagnostics with an expression path and
stable code. Plugins MUST NOT defer discoverable unsupported-operation errors
until execution.

## 11. Plugin capability contract

A plugin support declaration includes:

- supported protocol versions
- DTCS profile identifiers
- Semantic Action identifiers and versions
- function identifiers and versions
- operator identifiers and versions
- supported portable types
- semantic modes and limits
- determinism support
- lazy/eager and ownership behavior

Support is exact. A plugin MUST reject an operation it approximates differently.
A compiler MAY optimize or fuse expressions only when observable semantics,
security domains, validation boundaries, and logical identity mappings remain
unchanged.

The published profile identifiers are:

| Profile | Required semantic family |
|---|---|
| `dtcs:profile/portable-relational-kernel/1` | kernel relational actions and scalar expressions |
| `dtcs:profile/portable-relational/1` | full relational actions, joins, unions, aggregation, ordering, and deduplication |
| `dtcs:profile/portable-window/1` | experimental windows and frames |
| `dtcs:profile/portable-complex-types/1` | experimental composite types and access operations |

A plugin MAY advertise individual capabilities without claiming an entire
profile. It MUST claim a profile only after passing every required DTCS fixture
for that profile. Window and complex-types claims remain experimental until
DTCS's two-independent-compiler graduation requirement is met.

## 12. Security

Definition building and planning MUST NOT:

- read source data
- resolve secrets
- contact execution systems
- execute native transformation implementations
- deserialize executable objects
- evaluate arbitrary user-provided code from serialized artifacts

Python decorator authoring imports and invokes trusted definition code with
symbolic objects. Static artifact loading reconstructs IR from data only and
MUST NOT import or invoke the original definition.

Compilers treat names and literal values as untrusted. SQL lowerings MUST use
safe identifier handling and bound parameters. Plans, diagnostics, cache keys,
and reports MUST remain secret-free.

## 13. Compatibility

Readers MUST reject unknown major protocol versions. They MAY accept newer
minor additions only when every used node and semantic mode is understood.

Adding an optional operation is backward compatible. Changing existing
operation meaning, canonicalization, type promotion, or null behavior requires
a new major protocol version.

The DTCS plan schema, ETLantic authoring profile, and ETLantic compiler protocol
are independently versioned. The shared ETLantic/DTCS publisher MAY coordinate
their releases, but implementations MUST still declare and test compatibility
for each boundary.

## 14. Conformance

A conformant compiler must pass the shared `etlantic.testing` portable
transformation suite for every capability it advertises. Conformance covers IR
loading, compilation, execution results, null and error behavior, type
preservation, diagnostics, determinism, security, and bounded failure.
