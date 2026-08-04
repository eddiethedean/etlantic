# CP-GA Operator Drills (0.43)

Record of qualification drills executed for CP-GA. Re-run from a clean
environment after any P0/P1 remediation.

| Drill ID | Workstream | Procedure | Evidence |
|---|---|---|---|
| D-COMPAT | 043-C | `uv run python scripts/check_cp_ga_compat.py --fake` | cp_ga_compat_matrix_0_43.json |
| D-ISO | 043-I | `uv run python scripts/check_cp_ga_isolation.py --fake` | cp_ga_isolation_matrix_0_43.json |
| D-RES | 043-R | `uv run python scripts/check_cp_ga_resilience.py --fake` | cp_ga_resilience_matrix_0_43.json |
| D-REC | 043-B | `uv run python scripts/check_cp_ga_recovery.py --fake` | cp_ga_recovery_matrix_0_43.json |
| D-CAP | 043-P | `uv run python scripts/check_cp_ga_capacity.py --fake` | cp_ga_capacity_envelope_0_43.json |
| D-SEC | 043-S | `uv run python scripts/check_cp_ga_security.py --fake` | cp_ga_security_matrix_0_43.json |
| D-OPS | 043-O | `uv run python scripts/check_cp_ga_ops.py --fake` | cp_ga_ops_matrix_0_43.json |
| D-GITOPS | 043-M | `uv run python scripts/check_cp_ga_gitops.py --fake` | cp_ga_gitops_matrix_0_43.json |

## Key / secret rotation

1. Rotate attestation `signing_secret` on a new store instance.
2. Re-sign required plan/plugin attestations.
3. Confirm prior signatures fail closed under the new secret.
4. Record result in security matrix `attestation_key_rotation` case.
