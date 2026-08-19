# Security Verification Matrix (0.37)

> **Status: Available in ETLantic 0.48.0.** Single-tenant pilot envelope only.

Machine-readable companion:
[`security-verification-matrix.json`](security-verification-matrix.json)
(`etlantic.security_verification_matrix/1`). CI gate:
`scripts/check_security_matrix.py`.

This matrix maps every **mandatory** control from
[Security Model](SECURITY.md) § *Implemented through 0.37*, plus explicit
**Partial** controls called out in the evaluation table (CLI write roots,
outbound SSRF edges, DoS budgets, SecurityEvent audit residual, CycloneDX
optional/SBOM warning). It does **not** expand into multi-tenant isolation;
those controls remain adopter-owned until the
[Multi-Tenant Control Plane Plan](../11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN.md).

| Control ID | Control name | Owner | Automated verification | Residual risk |
|---|---|---|---|---|
| SEC-SECRETS-PLAN | Secret-free plans and reports | core maintainers | `tests/plan/test_planner.py`; `tests/plan/test_serialize.py`; `tests/secrets/test_secrets.py`; `tests/unit/test_hardening_top20_0_34.py` | None for single-tenant pilot envelope |
| SEC-PROFILE-MODE | Profile.security_mode production fail-closed trust | core maintainers | `tests/profile/test_profile_0_19.py`; `tests/unit/test_tooling_0_9.py`; `tests/cli/test_production_allowlist_cli.py` | None for single-tenant pilot envelope |
| SEC-PLUGIN-ALLOWLIST | Production plugin_allowlist fail-closed selection | plugin maintainers | `tests/unit/test_trust_isolation_0_20.py`; `tests/unit/test_tooling_0_9.py`; `tests/cli/test_production_allowlist_cli.py`; `tests/runtime/test_plugin_discovery_profile.py` | Allowlist is selection policy, not an import-time sandbox; install boundary remains adopter-owned |
| SEC-PROFILE-NAMED | Strict named profile resolution (PMCFG100) | core maintainers | `tests/profile/test_profile_0_19.py` | None for single-tenant pilot envelope |
| SEC-PLAN-FINGERPRINT | Plan fingerprint verification at trust boundaries | core maintainers | `tests/plan/test_freeze_0_19.py`; `tests/unit/test_trust_isolation_0_20.py` | None for single-tenant pilot envelope |
| SEC-VALIDATION-PHASES | Multi-phase validation before planning/execution | core maintainers | `tests/validation/test_phases.py` | None for single-tenant pilot envelope |
| SEC-SCHEMA-HISTORY | Schema history fingerprints without source rows | core maintainers | `tests/schema_drift/test_schema_history_hardening_0_34.py`; `tests/unit/test_hardening_top20_0_34.py` | None for single-tenant pilot envelope |
| SEC-SQL-PARAMS | Parameterized SQL and trusted-SQL gates | plugin maintainers | `tests/sql/test_sql_security.py`; `tests/sql/test_sql_portable_security.py` | Untrusted raw SQL fragments remain out of scope |
| SEC-DIAG-SARIF | SARIF/JSON diagnostics for CI | core maintainers | `tests/cli/test_cli.py`; `tests/unit/test_tooling_0_9.py`; `tests/testing/test_application_pipeline_burn_in_0_36.py` | None for single-tenant pilot envelope |
| SEC-REDACTION | Central redaction for logs and reports | core maintainers | `tests/runtime/test_bugfixes.py`; `tests/unit/test_hardening_next20_0_34.py`; `tests/compatibility/test_security_compatibility_0_36.py`; `tests/testing/test_testing_foundation_0_37.py` | None for single-tenant pilot envelope |
| SEC-SAFE-IO | SafeIoPolicy approved roots and atomic writes | core maintainers | `tests/unit/test_trust_isolation_0_20.py` | Kernel/FS race windows and host mounts outside SafeIoPolicy remain adopter-owned |
| SEC-OUTBOUND-DENY | Outbound default-deny (SSRF edges) | core maintainers | `tests/unit/test_trust_isolation_0_20.py` | Default-deny and host allowlists are tested; residual SSRF edges include DNS rebinding races, redirect chains, and adopter webhook topology outside the unit envelope |
| SEC-UNSAFE-SERIAL | Unsafe serialization prohibition | core maintainers | `tests/unit/test_trust_isolation_0_20.py`; `tests/secrets/test_secrets.py` | None for single-tenant pilot envelope |
| SEC-ARTIFACT-ISOLATION | Artifact and cache isolation keys | core maintainers | `tests/unit/test_trust_isolation_0_20.py` | Single-tenant reference keys only; cross-tenant isolation is adopter-owned until the control-plane program |
| SEC-SECURITY-EVENT | Versioned SecurityEvent audit events | core maintainers | `tests/unit/test_trust_isolation_0_20.py` | Versioned SecurityEvent is operational evidence only; not an immutable compliance audit system of record |
| SEC-RELEASE-PROVENANCE | Release SHA-256 digests and GitHub attestations | release maintainers | `.github/workflows/release.yml`; `tests/compatibility/test_security_compatibility_0_36.py`; `docs/01_GETTING_STARTED/RELEASE_ARTIFACT_VERIFICATION.md` | None for single-tenant pilot envelope when adopters verify published digests and attestations |
| SEC-SBOM-OPTIONAL | CycloneDX SBOM optional with sbom-warning.txt | release maintainers | `.github/workflows/release.yml`; `docs/01_GETTING_STARTED/RELEASE_ARTIFACT_VERIFICATION.md` | CycloneDX generation is optional; a release may ship sbom-warning.txt instead of an SBOM—confirm the published asset before assuming SBOM coverage |
| SEC-PROTOCOL-FREEZE | Plugin SDK /1 protocol freeze | plugin maintainers | `scripts/check_protocol_freeze.py`; `src/etlantic/schemas/surface-inventory.json` | None for single-tenant pilot envelope |
| SEC-WIRE-CODEC | Wire codec burn-in across consecutive minors | core maintainers | `scripts/check_pipeline_codec_burn_in.py`; `scripts/check_codec_burn_in_matrix.py`; `scripts/check_isolated_codec_burn_in.py`; `tests/compatibility/test_codec_burn_in_matrix.py` | None for single-tenant pilot envelope |
| SEC-CLI-WRITE-ROOTS | CLI write-root restriction | core maintainers | `tests/unit/test_trust_isolation_0_20.py`; `tests/cli/test_cli.py` | SafeIoPolicy covers approved roots for policy-backed writes; residual CLI generate/compile output-path restriction remains partial—operators must constrain working directories |
| SEC-DOS-BUDGETS | Denial-of-service / I/O budgets | core maintainers | `tests/unit/test_extensions_0_19.py`; `tests/unit/transform/test_portable_corpus.py`; `tests/compatibility/test_security_compatibility_0_36.py`; `tests/unit/test_trust_isolation_0_20.py` | Partial I/O, metadata, probe, and outbound budgets only; formal capacity SLA is residual |

## Partial controls (residual rationale)

| Control ID | Why Partial |
|---|---|
| SEC-OUTBOUND-DENY | Unit coverage proves default-deny and private/metadata blocking; DNS rebinding, full redirect graphs, and deployment webhook topology remain residual SSRF edges. |
| SEC-SECURITY-EVENT | Shipped versioned events support operational audit; they are not a compliance-grade immutable SoR. |
| SEC-SBOM-OPTIONAL | Release workflow may emit CycloneDX **or** `sbom-warning.txt`; SBOM presence is not guaranteed per tag. |
| SEC-CLI-WRITE-ROOTS | SafeIoPolicy roots are enforced for policy-backed I/O; broad CLI write-path authorization remains Partial. |
| SEC-DOS-BUDGETS | Configurable I/O/metadata/probe budgets exist; formal DoS capacity SLA does not. |

## Out of scope for this matrix

- Cross-tenant / multi-tenant isolation guarantees
- Formal denial-of-service capacity SLAs
- Compliance attestations and immutable audit systems of record beyond operational reports
- Broader supply-chain programs beyond allowlists, pins, digests, and release attestations

See [Security Model](SECURITY.md),
[Evaluator → Security posture](../01_GETTING_STARTED/EVALUATOR.md#security-posture),
and [Exit Gate 0.37](../11_DEVELOPMENT/EXIT_GATE_0_37.md).
