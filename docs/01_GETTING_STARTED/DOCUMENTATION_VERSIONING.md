# Documentation versioning

> **Status: ETLantic 0.55.0 Beta release candidate; publication pending.** How Read the Docs aliases relate to PyPI pins.
> Release facts live in [`docs/release-facts.json`](../release-facts.json).

ETLantic docs are published on Read the Docs.

## Latest vs stable vs versioned

| Alias / slug | Meaning |
|---|---|
| **`/en/v0.55.0/`** | Immutable docs for the `v0.55.0` release tag, available after publication. Pair with `etlantic==0.55.0`. |
| **stable** | Moves to the newest published release. Fine for pilots tracking the tip of PyPI. |
| **latest** | Tracks the default branch (`main`) and may document unreleased behavior. |

After publication, use the immutable `/en/v0.55.0/` documentation with `etlantic==0.55.0`.
`stable` moves to the newest published release; `latest` follows `main` and
may document unreleased behavior. Do not mix a pinned wheel with `latest`
docs that describe a newer branch tip.

### Maintainer: activate a tag on Read the Docs

1. After the release tag exists, open the ETLantic project on Read the Docs → **Versions**.
2. Activate the git tag `v0.55.0` (build if inactive).
3. Keep **latest** = `main` and **stable** = newest published tag.
4. Confirm `https://etlantic.readthedocs.io/en/v0.55.0/` returns 200.

## Internal links

Pages under `docs/` use **relative Markdown links** (`.md` targets) so the same
source works on GitHub, local `mkdocs serve`, and every RTD version alias.
Root and package READMEs should use absolute
`https://etlantic.readthedocs.io/en/v0.55.0/…` URLs for release-facing readers.

## Release notes

- [What's new in 0.49](WHATS_NEW_0_49.md)
- [What's new in 0.46](WHATS_NEW_0_46.md)
- [Upgrade hub](UPGRADE.md)
- [Changelog](../CHANGELOG.md)
