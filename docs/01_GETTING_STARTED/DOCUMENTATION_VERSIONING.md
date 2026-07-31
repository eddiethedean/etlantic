# Documentation versioning

> **Status: Available.** How Read the Docs aliases relate to PyPI pins.
> Release facts live in [`docs/release-facts.json`](../release-facts.json).

ETLantic docs are published on Read the Docs.

## Latest vs stable vs versioned

| Alias / slug | Meaning |
|---|---|
| **`/en/v0.39.0/`** | Immutable docs for the tagged release. Prefer this with `etlantic==0.39.0`. |
| **stable** | Moves to the newest published release. Fine for pilots tracking the tip of PyPI. |
| **latest** | Tracks the default branch (`main`) and may document unreleased behavior. |

For `etlantic==0.39.0`, use the immutable `/en/v0.39.0/` documentation.
`stable` moves to the newest published release; `latest` follows `main` and
may document unreleased behavior. Do not mix a pinned wheel with `latest`
docs that describe a newer branch tip.

### Maintainer: activate a tag on Read the Docs

1. Open the ETLantic project on Read the Docs → **Versions**.
2. Activate the git tag `v0.39.0` (build if inactive).
3. Keep **latest** = `main` and **stable** = newest published tag.
4. Confirm `https://etlantic.readthedocs.io/en/v0.39.0/` returns 200.

## Internal links

Pages under `docs/` use **relative Markdown links** (`.md` targets) so the same
source works on GitHub, local `mkdocs serve`, and every RTD version alias.
Root and package READMEs should use absolute
`https://etlantic.readthedocs.io/en/v0.39.0/…` URLs for release-facing readers.

## Release notes

- [What's new in 0.39](WHATS_NEW_0_39.md)
- [What's new in 0.37](WHATS_NEW_0_37.md)
- [Upgrade hub](UPGRADE.md)
- [Changelog](../CHANGELOG.md)
