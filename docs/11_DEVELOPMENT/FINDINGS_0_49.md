# 0.49 findings ledger

This ledger records the substantive Sol review findings for the qualified
DuckDB subset. It is evidence of implementation work, not an approval or a
substitute for the independent release gate.

| ID | Status | Resolution / remaining boundary |
|---|---|---|
| SOL-049-11 | Verified fixed | Selected SQL engine is preserved through planning boundaries. |
| SOL-049-12 | Verified fixed | Portable staging uses connection-local temporary relations and cleans up on success/failure. |
| SOL-049-13 | Verified fixed | DuckDB configuration paths and metadata are defensively immutable. |
| SOL-049-14 | Fixed in this cycle | Requirement merging and schema preflight now fail closed for operators, types, semantic modes, unresolved columns, and known join collisions. |
| SOL-049-15 | Verified fixed | Concurrent same-run fetches use unique sealed statement identities. |
| SOL-049-16 | Verified fixed | Join key arity mismatches are rejected before lowering. |
| SOL-049-17 | Fixed in this cycle | Evidence includes generator/package/runtime identity, validates its schema, and derives result status from runtime checks. |
| SOL-049-18 | Fixed in this cycle | DuckDB qualification runs across supported OS/Python and DuckDB min/max dependency matrices, including generated file-backed/read-only checks; release wheel smoke includes DuckDB and a generic SQL fixture. |
| SOL-049-19 | Fixed in this cycle | Public capability docs, migration, What's New, changelog, runnable example, and this ledger are aligned with the qualified subset. |
| SOL-049-20 | Pending release operation | Changes must be committed and pushed before Sol’s independent re-review; this work is not an approval. |

The package deliberately remains a qualified subset. Unimplemented actions and
unknown requirements continue to be rejected before execution.
