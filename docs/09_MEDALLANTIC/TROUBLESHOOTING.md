# Troubleshooting

## Package versions do not match

Install matching ETLantic and Medallantic minors:

```bash
python -m pip install --upgrade \
  'etlantic==0.44.0' \
  'medallantic==0.44.0'
```

## Unknown source or cycle

Check `source=` against declared step names and inspect `MDL102`, `MDL103`, or
`MDL104`. Medallantic fails closed and never removes dependencies.

## Rule is rejected

`MDL110` means the shorthand is malformed or cannot be enforced by the selected
capability set. Fix the rule or select a conforming implementation; do not
silence the finding for production.

## Transformation reference cannot run

Use `module:attribute`, ensure the module is installed in the runtime
environment, and make the attribute callable. Keep imports side-effect free.

## Merge, upsert, or Delta fails planning

The selected storage/backend must advertise the exact capability. A profile
name or installed distribution is not proof of authorization or semantic
support.

## Production plugin is rejected

Add the trusted distribution to `Profile.plugin_allowlist` and verify its
manifest, version, protocol range, and capabilities. Do not weaken production
security mode to bypass authorization.

## Report fails accept-rate enforcement

Inspect `MDL120`, the layer threshold metadata, and accepted/rejected counts.
Keep rejected rows in bounded runtime artifacts rather than reports.

## Run the focused suite

```bash
uv sync --locked --group medallantic
uv run pytest -q tests/medallantic -m medallantic
```
