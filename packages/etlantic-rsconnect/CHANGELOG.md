# etlantic-rsconnect changelog

## [0.60.1] - 2026-10-15

Compatible with `etlantic>=0.60.0,<0.61.0`.

- Upgrade legacy deployed trigger bundles while paused before resuming a
  canonical schedule with a new timer-owner generation.
- Reserve `ETLANTIC_TIMER_OWNER_GENERATION` from runtime credential use.

## [0.60.0] - 2026-10-14

Initial preview release, compatible with `etlantic>=0.59.0,<0.61.0`.

- Generate deterministic, verified Quarto trigger bundles with no runtime
  dependency outside the Python standard library.
- Publish to an explicit Connect URL with separate deployment and receiver
  credential references and a caller-owned durable deployment journal.
- Inspect and manage the experimentally supported UTC minute/hour/day interval
  subset through the pinned optional `posit-sdk==0.17.0` integration.
- Fence schedule lifecycle operations through caller-owned atomic binding
  storage and the public ETLantic schedule service.
- Deliver and reconcile public trigger receipts with bounded HTTPS, verified
  TLS, destination controls, stable occurrence identities, and redacted errors.
- Cover SDK serialization, ownership races, response loss, HTTP framing, TLS
  deadlines, and generated-content safety with local simulations.

The generated Connect content remains inactive: the documented scheduled-render
surface provides no trusted nominal-slot and retry identity. Arming content or
setting static occurrence environment variables cannot enable delivery. Hosts
must provide durable `BindingStore` and `DeploymentJournal` implementations;
the package includes their integration protocols, not a qualified store backend.
Live Connect lifecycle and production support remain unqualified. These support
limits do not prevent publishing or installing this preview.

Python 3.11–3.13 are covered by the repository checks. Quarto and
`rsconnect-python>=1.31.1` are optional external deployment tools. FastAPI,
Data Mover, receiver services, and worker services are not package requirements.
