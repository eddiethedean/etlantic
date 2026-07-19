# Portable Failure Cookbook

> **Status: Available in ETLantic 0.18.0.** Practical failure modes for
> `@Transformation.portable` and compiler selection.

## Policy first

`Profile.portable_transform_policy` controls planning when a portable
definition exists:

| Policy | Behavior |
|---|---|
| `prefer` (common default) | Use a matching portable compiler when available; otherwise native |
| `require` | Fail closed if no capable portable compiler matches |
| `native` | Prefer registered native implementations |

If validate/plan fails with a portable capability diagnostic, check policy
before assuming the transform is wrong.

## Engine coverage cliff

| Family | Polars | PySpark | Pandas | SQL |
|---|---|---|---|---|
| Kernel + relational `/1` | Yes | Yes | Yes (eager) | Yes |
| Advanced (window, reshape, …) | Yes | Yes | Baseline only | Baseline only |

Seeing a plan succeed on Polars and fail on Pandas/SQL for the same portable
definition is expected for advanced profiles. See
[Portable compiler matrix](../10_REFERENCE/PORTABLE_COMPILER_MATRIX.md).

## Common failures

1. **No compiler discovered** — install the engine package
   (`etlantic-polars==0.18.0`, …) and match core minor.
2. **`require` with incomplete coverage** — switch to `prefer` for pilots, or
   narrow the portable definition to supported profiles.
3. **Native-only implementation present, policy `require`** — portable path is
   mandatory; register a portable definition or change policy.
4. **Version skew** — core 0.18 + plugin 0.17 fails discovery; pin together.
5. **Production empty allowlist** — portable compilers must appear on
   `plugin_allowlist`.

## Debugging steps

```bash
etlantic plugin list --kind transform_compiler --format json
etlantic validate path.py:MyPipeline --profile development --format json
etlantic plan path.py:MyPipeline --profile development --format json
```

Inspect capability decisions in the plan explain output
(`etlantic plan explain …`).

## Related

- [Portable vs native](PORTABLE_VS_NATIVE.md)
- [Portable transformations](../04_TRANSFORMATIONS/PORTABLE_TRANSFORMATIONS.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [Interchange Gate A FAQ](INTERCHANGE_GATE_A_FAQ.md)
