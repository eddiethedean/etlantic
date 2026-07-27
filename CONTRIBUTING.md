# Contributing

Thank you for your interest in ETLantic.

**Canonical contributor guide (single source of truth):**

**[docs/11_DEVELOPMENT/CONTRIBUTING.md](docs/11_DEVELOPMENT/CONTRIBUTING.md)**

Use that page for setup, the full CI-equivalent checklist (including
`tests/authoring`, FastAPI package tests, and `pipeline_definition_json.py`),
coding standards, and PR expectations. This root file is a short pointer only.

## Quick start

```bash
git clone https://github.com/eddiethedean/etlantic.git
cd etlantic
uv sync --locked
```

### Docs-only / minimal first PR

```bash
uv run ruff check .
uv run ruff format --check .
uv run python scripts/check_docs.py
uv run python scripts/check_agent_guidance.py
```

For core, plugin, or release-impacting changes, run the **CI-equivalent checks**
section in
[docs/11_DEVELOPMENT/CONTRIBUTING.md](docs/11_DEVELOPMENT/CONTRIBUTING.md)
(do not rely on an abbreviated list here).

Fork the repository, branch from `main`, and open a pull request against
`main`. Please report security issues privately per [SECURITY.md](SECURITY.md).
Do not open public issues that include credentials or production data.

Participation is governed by the
[Code of Conduct](docs/11_DEVELOPMENT/CODE_OF_CONDUCT.md), and project decisions
follow the [Governance guide](docs/11_DEVELOPMENT/GOVERNANCE.md). Maintainers
are listed in [MAINTAINERS.md](MAINTAINERS.md).
