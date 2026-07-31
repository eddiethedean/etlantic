# Governance

> **Status: Available in ETLantic 0.37.0.**

ETLantic currently uses a maintainer-led governance model. See
[MAINTAINERS.md](https://github.com/eddiethedean/etlantic/blob/main/MAINTAINERS.md)
for the active maintainer list.

## Decision authority

Maintainers accept changes based on user value, correctness, compatibility,
security, architectural ownership, and maintenance cost. The repository's
public code, tests, accepted ADRs, and published standards are authoritative;
roadmap dates and design studies are not commitments.

The **lead maintainer** has final authority on release tags, security
disclosure timing, maintainer appointments/removals, and unresolved conflicts
after discussion.

## Roles

| Role | Authority |
|---|---|
| Lead maintainer | Releases, security, succession, tie-breaking |
| Maintainer | Merge within area; escalate security/API breaks |
| Contributor | PRs and issues under Code of Conduct |
| Plugin author | Own backend packages; follow public protocols |

## Change classes

| Change | Required evidence |
|---|---|
| Documentation correction | Source or executable behavior |
| Compatible implementation | Tests and affected docs |
| Public API addition | Two concrete consumers or one end-to-end workflow |
| Plugin protocol change | Compatibility analysis and conformance tests |
| Persistent format/contract change | Versioning and migration path |
| Difficult-to-reverse architecture | ADR and maintainer approval |
| Security fix | Private report path + tests; coordinated disclosure |

## Conflicts of authority

- [ODCS](../03_DATA_CONTRACTS/ODCS.md), [DTCS](../04_TRANSFORMATIONS/DTCS.md), and [DPCS](../05_PIPELINES/DPCS.md) specifications own contract meaning.
- ETLantic owns logical modeling, validation, and planning behavior.
- Plugins own backend realization.
- Code and tests supersede stale narrative documentation for a shipped release.

Maintainers should document rejected alternatives when a decision materially
constrains third-party plugins or persistent artifacts.

## Succession and inactivity

If the lead maintainer is unavailable for an extended period, active
maintainers should coordinate interim release authority publicly in an issue.
Inactive maintainers may be removed after documented notice. Appointment and
removal decisions are recorded in commit history / `MAINTAINERS.md`.

## Conduct and security conflicts

If a Code of Conduct report concerns the lead maintainer, reporters should use
GitHub private vulnerability reporting or request a trusted third party via
the GitHub organization/owner channels before sharing sensitive details. Do
not open a public issue containing private allegations.

Security process details live in
[SECURITY.md](https://github.com/eddiethedean/etlantic/blob/main/SECURITY.md).
