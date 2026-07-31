# Rollback and recovery

> **Status: Available in ETLantic 0.38.0.** Operator checklist for pinned
> package rollback, re-validate / re-plan, workspace backup, and failed deploy
> recovery. Single-tenant Beta envelope only.

## Package pin rollback

1. Keep the previous lockfile / image tag that last passed validate → plan →
   smoke run.
2. Reinstall the last known-good pins (same minor for core and plugins):

   ```bash
   python -m pip install --force-reinstall \
     'etlantic==0.33.0' 'etlantic-polars==0.33.0'
   # Adjust versions to your last good release.
   ```

3. Align `Profile.plugin_allowlist` pins with the reinstalled packages.
4. Do not mix core and plugin minors.

## Re-validate and re-plan

After any pin change or rollback:

```bash
python -m etlantic validate TARGET --profile profiles/prod.json --format json
python -m etlantic plan TARGET --profile profiles/prod.json --format json \
  > pipeline-plan.json
```

Compare the new plan fingerprint to the last reviewed artifact. Recompile
Airflow DAGs only from a valid plan after a successful plan step.

## Backup `.etlantic/` reports and history

Before risky upgrades or redeploys, archive the workspace (secret-free ops
evidence):

```bash
tar -czf etlantic-workspace-backup.tgz .etlantic/
# Typical contents: reports/, history/, artifacts/, schema-history/
```

Restore by extracting beside the project root, then use
`etlantic report list` / `report query` / `report show`. Reports are operational
evidence, not a compliance SoR — see [Reports and history](REPORTS_AND_HISTORY.md).

## Failed deploy recovery

1. Stop or pause orchestrated schedules that still target the failed revision.
2. Roll package pins (and images) back to the last known-good set.
3. Re-validate and re-plan with the production allowlisted profile.
4. Smoke-run one non-critical pipeline; confirm `etlantic report query` shows
   `succeeded`.
5. Only then re-enable schedules / promote the prior DAG artifact.

Engine-side data recovery (tables, files, Delta versions) remains
adopter-owned.

## Plugin downgrade note

Official plugins require a matching core minor (`etlantic>=X.Y.0,<X.Y+1`).
Downgrading a plugin alone against a newer core (or the reverse) fails
closed at allowlist / discovery. Always roll **core + plugins** together, and
update allowlist pins in the same change.

## Related

- [Deployment](DEPLOYMENT.md)
- [Production readiness](PRODUCTION_READINESS.md)
- [Production profiles](PRODUCTION_PROFILES.md)
- [Upgrade hub](../01_GETTING_STARTED/UPGRADE.md)
- [CI integration](CI_INTEGRATION.md)
