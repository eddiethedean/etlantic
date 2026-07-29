# Top-10 diagnostics playbook

> **Status: Available in ETLantic 0.34.0.** Fix recipes for the codes adopters
> hit first. Full catalog: [Diagnostics catalog](DIAGNOSTICS_CATALOG.md).

| Code | Usually means | Fix |
|---|---|---|
| `PMPIPE210` | Load/Extract type does not match upstream port | Align annotations (Quickstart aha: `Load[Row]` vs `Load[Other]`) |
| `PMPLUG401` | Production profile missing allowlist | Set `security_mode="production"` **and** non-empty `plugin_allowlist` |
| `PMPLUG402` | Plugin not on allowlist / not trusted | Add package to allowlist or switch profile to development |
| `PMCFG111` | Legacy profile `bindings` shape | Migrate to `assets` / modern profile JSON ([Profiles hub](../05_PIPELINES/PROFILES_HUB.md)) |
| `PMPLAN*` capability miss | Engine/plugin cannot satisfy plan | Install matching plugin minor; set engine fields on Profile |
| `PMXFORM*` portable fail | Portable IR cannot lower | Use `portable_transform_policy` or provide a native `@implementation` |
| `PMSEC*` / IO policy | Path or outbound blocked | Adjust `SafeIoPolicy` / workspace roots; never embed secrets |
| `PMEXEC*` run failure | Storage/runtime error after a valid plan | Check asset URIs, memory seeding, and same `--profile` as plan |
| Fingerprint mismatch | Plan mutated or wrong plan reused | Re-`plan` before `run` / `compile`; do not edit plan JSON by hand |
| Empty `data/out.json` / no rows | Bindings or seed missing | Confirm `data/` files exist; memory demos need Python seeding |

## Operator commands

```bash
python -m etlantic validate TARGET --profile development --format json
python -m etlantic validate TARGET --profile production --format sarif
python -m etlantic doctor
python -m etlantic report query --format json --limit 20
```

## Related

- [Troubleshooting](../01_GETTING_STARTED/TROUBLESHOOTING.md)
- [FAQ](../01_GETTING_STARTED/FAQ.md)
- [Reports and history](../06_EXECUTION/REPORTS_AND_HISTORY.md)
- [Diagnostics model](DIAGNOSTICS.md)
