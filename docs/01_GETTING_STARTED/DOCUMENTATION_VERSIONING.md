# Documentation versioning

> **Status: Available.** How Read the Docs aliases relate to PyPI pins.

ETLantic docs are published on Read the Docs.

## Latest vs stable

| Alias | Meaning |
|---|---|
| **latest** | Tracks the default branch (`main`). May describe unreleased changes. |
| **stable** | Tracks the latest tagged release on PyPI. Prefer this for pilots. |

Pin installs to an exact version (`pip install 'etlantic==0.35.0'`) and open the
matching docs version when available. Do not mix a pinned wheel with `latest`
docs that describe a newer branch tip.

## Internal links

Pages under `docs/` use **relative Markdown links** (`.md` targets) so the same
source works on GitHub, local `mkdocs serve`, and every RTD version alias.
Root and package READMEs may keep absolute `https://etlantic.readthedocs.io/…`
URLs for external readers.

## Release notes

- [What's new in 0.34](WHATS_NEW_0_34.md)
- [Upgrade hub](UPGRADE.md)
- [Changelog](../CHANGELOG.md)
