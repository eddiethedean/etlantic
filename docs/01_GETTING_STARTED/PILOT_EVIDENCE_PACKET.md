# Pilot evidence packet (0.38)

> **Status: Available in ETLantic 0.38.0.** Reproducible checklist for a
> controlled single-tenant pilot. This is an in-repo evidence template, not an
> independent third-party case study.

## Exact versions

| Component | Pin |
|---|---|
| Core | `etlantic==0.38.0` |
| Docs | `https://etlantic.readthedocs.io/en/v0.38.0/` |
| Optional engines | Matching `0.38.0` plugins (`etlantic-polars`, `etlantic-sql`, …) |
| Facade | `medallantic==0.38.0` when used |

## Topology (reference)

1. Single-tenant process / workspace
2. Development profile for learning; production profile with explicit
   `plugin_allowlist` for pilots that write
3. Local or one engine plugin (Polars **or** Pandas **or** SQL **or** local PySpark)
4. Optional Airflow compile or Prefect local MVP — not a managed control plane

Companion: [`examples/sample_pilot/`](https://github.com/eddiethedean/etlantic/tree/v0.38.0/examples/sample_pilot).

## Ownership

| Concern | Owner |
|---|---|
| Pipeline contracts and wiring | Adopter |
| Plugin allowlist / trust | Adopter (fail-closed in production) |
| Secrets | Adopter SecretRef providers — never embed values |
| Multi-tenant isolation | Out of scope in 0.37 |
| Incident response / SLA | Community only — see [SUPPORT](https://github.com/eddiethedean/etlantic/blob/main/SUPPORT.md) |

## Recovery

1. Keep secret-free plans and SARIF/JSON validate output
2. Use [Rollback and recovery](../06_EXECUTION/ROLLBACK_RECOVERY.md)
3. Query durable reports when enabled (`etlantic report query`)

## Observed limitations (document honestly)

- Beta maturity; no enterprise SLA
- No managed multi-tenant control plane
- CycloneDX SBOM optional / may be absent — verify SHA-256 digests and
  attestations ([Release artifact verification](RELEASE_ARTIFACT_VERIFICATION.md))
- Engine tutorials may require a clone; PyPI-pasteable pages: Quickstart, SQL hello,
  interchange (embedded scripts)

## Sign-off checklist

- [ ] `etlantic --version` prints `0.38.0`
- [ ] Quickstart succeeds and intentional `PMPIPE210` fails closed
- [ ] Production profile has `plugin_allowlist`
- [ ] Docs consulted from `/en/v0.38.0/` for the pin
- [ ] Limitations reviewed in [Capabilities](CAPABILITIES.md)
