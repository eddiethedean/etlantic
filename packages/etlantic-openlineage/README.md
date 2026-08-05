# etlantic-openlineage (Experimental / CP2)

Outbound OpenLineage-compatible event export for
[ETLantic](https://github.com/eddiethedean/etlantic) **0.43** CP2. Maps plan
identity and run events to OL-like JSON. **Outbound only** — export failures
must never mutate registry authority.

**Maturity:** Experimental (Alpha classifier). **Not production multi-tenant**
(that claim remains **0.43**). CP2 builds mechanisms and evidence only.

## Install

```bash
pip install 'etlantic-openlineage==0.45.0'
# Optional vendor client (not required for fake/CI):
# pip install 'etlantic-openlineage[openlineage]==0.45.0'
# pip install 'etlantic==0.45.0'
```

Core dependency: `etlantic>=0.45.0,<0.46`.

## Behavior

- Builds OpenLineage-compatible event shapes from plan identity + run metadata
  without requiring `openlineage-python`.
- Transport failures raise; callers must not treat remote ACKs as registry
  authority.
- Never writes tenants, workspaces, revisions, aliases, or promotions.

## Links

[Source](https://github.com/eddiethedean/etlantic/tree/main/packages/etlantic-openlineage) ·
[Issues](https://github.com/eddiethedean/etlantic/issues)
