# Migration: 0.20 → 0.21

## Version pins

Update installs and plugin allowlists:

```bash
pip install 'etlantic==0.21.0'
pip install 'etlantic-polars==0.21.0'  # optional engines
```

Plugin packages require `etlantic>=0.21.0,<0.22`.

## Profile JSON: `bindings` → `assets`

0.21 rejects legacy-only `bindings` keys by default (`PMCFG111`).

**Before (0.20):**

```json
{
  "name": "development",
  "bindings": { "rows": "json://data/rows.json" }
}
```

**After (0.21):**

```json
{
  "name": "development",
  "security_mode": "development",
  "assets": { "rows": "json://data/rows.json" }
}
```

Migrate automatically:

```bash
etlantic profile migrate profiles/development.json --write
```

Or load once with `--accept-legacy-bindings` while updating files.

## Structured assets

Assets may use URI or object form:

```json
"assets": {
  "customer_source": "json://data/customers.json",
  "customer_sink": { "provider": "json", "location": "data/out.json" }
}
```

## CLI durable reports

Reports from `etlantic run` are written to `.etlantic/reports/` by default.
Later invocations of `etlantic report show` discover them without stdout
redirection. Use `--ephemeral` to restore process-local behavior.

## Deprecated commands

- `etlantic reliability plan-diff` → `etlantic plan diff`

## Recommended workflow

Use `etlantic init` for new projects and follow the documented
`init → doctor → validate → plan → run → report` path in the quickstart.
