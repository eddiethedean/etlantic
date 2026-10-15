---
title: ETLantic 0.60 Candidate Gate and Connect Preview Exit Record
description: Core 0.60 candidate status and repository-local publication record for etlantic-rsconnect 0.60.0.
---

# ETLantic 0.60 Candidate Gate and Connect Preview Exit Record

## Core 0.60 candidate

Core 0.60.0 is an unpublished Beta candidate. It carries public durable
dispatch contracts used by the phase 0.61 AWS adapter. The latest published
and supported core line remains 0.59.x; no core 0.60.0 tag or PyPI artifact has
been created. Local implementation and checks are tracked on the phase 0.61
branch. Live AWS qualification and a production support decision remain open.
See [Migration 0.59 → 0.60](MIGRATION_0_59_TO_0_60.md), [What's new in
0.60](../01_GETTING_STARTED/WHATS_NEW_0_60.md), and the
[0.61 implementation plan](IMPLEMENTATION_PLAN_0_61.md).

## Independent Connect preview publication record

The locally qualified `etlantic-rsconnect==0.60.0` preview was published at
2026-10-15T00:02:34Z from commit
[`def8a940`](https://github.com/eddiethedean/etlantic/commit/def8a9402a983524e0134f43dbf9fea0fd1fc89c),
under tag `etlantic-rsconnect-v0.60.0`. The package is available on
[PyPI](https://pypi.org/project/etlantic-rsconnect/0.60.0/) and as a
[GitHub prerelease](https://github.com/eddiethedean/etlantic/releases/tag/etlantic-rsconnect-v0.60.0).
The release workflow completed successfully, including its full checks and
preview publishing job ([run 38656000427](https://github.com/eddiethedean/etlantic/actions/runs/38656000427)).
Core remains at 0.59.0 and its existing tag stays immutable. Publication records
distribution only; it does not qualify live Connect activation or production
support.

| Deliverable | Implemented surface and verification |
|---|---|
| Platform boundary | Explicit HTTPS Connect target, pinned optional Posit SDK 0.17.0, experimental mutation opt-in, and exact UTC minute/hour/day interval subset. Unsupported recurrences fail before writes. |
| Trigger bundle | Deterministic archive and verified file manifest; minimal standard-library runner; credential references only; disarmed deploy renders and refusal of spoofed unbound context. |
| Deployment | `RsconnectPythonDeployer` resolves separate credentials at the publishing boundary, journals intent before remote work, redacts vendor output, and retains uncertain outcomes. |
| Lifecycle | Public `BindingStore` and `ConnectScheduleGateway` integration protocols, atomic operation claims, readback, drift checks, pause/delete admission cutoff, resume, and amendment/rollback fencing. |
| Delivery | Public trigger/receipt contract parity, occurrence-preserving retries and receipt lookup, verified and pinned HTTPS, bounded DNS/credentials/read time/bytes, and strict HTTP framing. |
| Simulations | Real pinned SDK over strict synthetic HTTP, controlled lifecycle races, request/response loss, actual loopback TLS, and generated-runner subprocess tests. The larger stateful simulator campaign remains documented future work. |
| Distribution | Independent tag validation, package release notes, wheel/sdist builds, isolated base installation, installed contract tests with workspace imports disabled, and package-only PyPI/GitHub prerelease publishing. |

The pre-publication source gate and focused suite were run from the locked
workspace at the release commit:

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

Publication used the [independent Connect preview release process](RELEASE_PROCESS.md#independently-versioned-connect-preview)
and package [release notes](https://github.com/eddiethedean/etlantic/blob/main/packages/etlantic-rsconnect/CHANGELOG.md).
No external platform campaign was a distribution gate.

The generated Connect content remains inactive because its documented scheduled
invocation has no trusted nominal-slot/retry provider. The package does not
manufacture occurrence authority from clock time or static environment values.
Durable binding/journal implementations, a live Connect topology, and independent
receiver/worker execution remain unqualified for production support. AC060-001–006
and the production-only decision register remain open as stated in the
[implementation plan](IMPLEMENTATION_PLAN_0_60.md). The preview release does not
convert those deferrals into passed evidence.
