---
title: ETLantic 0.60 Preview Exit Record
description: Repository-local completion and publication of etlantic-rsconnect 0.60.0.
---

# ETLantic 0.60 Preview Exit Record

The phase implementation is complete for the locally qualified
`etlantic-rsconnect==0.60.0` preview. Core remains at 0.59.0; its existing tag
stays immutable. The package is ready for the independent
`etlantic-rsconnect-v0.60.0` release path after the checks below pass on the
intended commit. This record does not publish an artifact or qualify live
Connect activation.

| Deliverable | Implemented surface and verification |
|---|---|
| Platform boundary | Explicit HTTPS Connect target, pinned optional Posit SDK 0.17.0, experimental mutation opt-in, and exact UTC minute/hour/day interval subset. Unsupported recurrences fail before writes. |
| Trigger bundle | Deterministic archive and verified file manifest; minimal standard-library runner; credential references only; disarmed deploy renders and refusal of spoofed unbound context. |
| Deployment | `RsconnectPythonDeployer` resolves separate credentials at the publishing boundary, journals intent before remote work, redacts vendor output, and retains uncertain outcomes. |
| Lifecycle | Public `BindingStore` and `ConnectScheduleGateway` integration protocols, atomic operation claims, readback, drift checks, pause/delete admission cutoff, resume, and amendment/rollback fencing. |
| Delivery | Public trigger/receipt contract parity, occurrence-preserving retries and receipt lookup, verified and pinned HTTPS, bounded DNS/credentials/read time/bytes, and strict HTTP framing. |
| Simulations | Real pinned SDK over strict synthetic HTTP, controlled lifecycle races, request/response loss, actual loopback TLS, and generated-runner subprocess tests. The larger stateful simulator campaign remains documented future work. |
| Distribution | Independent tag validation, package release notes, wheel/sdist builds, isolated base installation, installed contract tests with workspace imports disabled, and package-only PyPI/GitHub prerelease publishing. |

Run the source gate and focused suite from the locked workspace:

```bash
uv sync --locked --extra rsconnect
uv run python scripts/check_rsconnect_release.py --tag etlantic-rsconnect-v0.60.0
uv run pytest -q tests/rsconnect tests/control_plane/test_trigger_0_59.py \
  tests/service/test_schedule_application_0_57.py
```

The standard checks also run Ruff, strict Pyright, release/documentation checks,
and the documentation build. The package CI job builds the core and preview
wheels and qualifies the base preview with
`python -I scripts/check_rsconnect_release.py --installed --expected-version
0.60.0`. The checker rejects workspace imports, verifies the optional SDK and
engines are absent, checks reproducibility and manifests, and executes generated
content with `python -I -S`. The installed focused suite uses
`python -I -m pytest -q -o pythonpath=` to override the repository's source paths.
The independent publishing job repeats these checks against released core
0.59.0. Release artifacts include a JSON check report and build provenance.

Publication uses the [release process](RELEASE_PROCESS.md#independently-versioned-connect-preview)
and package [release notes](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-rsconnect/CHANGELOG.md).
No external platform campaign is a distribution gate.

The generated Connect content remains inactive because its documented scheduled
invocation has no trusted nominal-slot/retry provider. The package does not
manufacture occurrence authority from clock time or static environment values.
Durable binding/journal implementations, a live Connect topology, and independent
receiver/worker execution remain unqualified for production support. AC060-001–006
and the production-only decision register remain open as stated in the
[implementation plan](IMPLEMENTATION_PLAN_0_60.md). The preview release does not
convert those deferrals into passed evidence.
