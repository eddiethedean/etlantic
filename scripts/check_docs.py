"""Small dependency-free documentation consistency checks."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]


def version_from(path: Path, pattern: str) -> str:
    match = re.search(pattern, path.read_text(encoding="utf-8"))
    if match is None:
        raise SystemExit(f"Could not find version in {path}")
    return match.group(1)


def main() -> None:
    package_version = version_from(
        ROOT / "src/pipelantic/_version.py", r'__version__ = "([^"]+)"'
    )
    project_version = version_from(ROOT / "pyproject.toml", r'(?m)^version = "([^"]+)"')
    if package_version != project_version:
        raise SystemExit(
            f"Version mismatch: package={package_version}, project={project_version}"
        )

    current_markers = [
        ROOT / "README.md",
        ROOT / "docs/README.md",
        ROOT / "docs/01_GETTING_STARTED/CAPABILITIES.md",
        ROOT / "SECURITY.md",
    ]
    for path in current_markers:
        text = path.read_text(encoding="utf-8")
        if package_version not in text:
            raise SystemExit(
                f"{path} does not mention current version {package_version}"
            )

    examples_index = (ROOT / "docs/09_EXAMPLES/README.md").read_text(encoding="utf-8")
    if "complete working examples" in examples_index.lower():
        raise SystemExit("Examples index still claims all design examples are runnable")

    banned_phrases = [
        "does not ship Pandas or Polars",
        "Pandas, Polars, SQL, Spark, and Airflow plugins are not published as part of\nPipelantic 0.4",
        "Future plugins may add Pandas, Polars",
        "Pandas and Polars pipelines | Future plugin design",
        "Pandas, Polars, SQL, Spark, and Airflow plugins | Not yet available",
        "SQL, Spark, and Airflow plugins | Not yet available",
        "SQL compilation or execution | Future design (0.6)",
        "SQL, Spark, and Airflow compilation are not shipped",
        "These examples use only APIs and dependencies shipped in Pipelantic 0.4",
        "These examples use only APIs and dependencies shipped in Pipelantic 0.5",
        "Available in Pipelantic 0.4.0",
        "not a Pipelantic 0.4 API guide",
        "not a Pipelantic 0.5 API guide",
        "Dataframe, SQL, Spark, and external orchestration chapters remain accepted",
        "plan.to_mermaid()",
        "lightweight production workloads",
        "uv run pyright",
        "Commands are provisional until the implementation toolchain is committed",
    ]
    if "| Capability | 0.4 |" in (ROOT / "README.md").read_text(encoding="utf-8"):
        raise SystemExit("README.md capability table still labels the release as 0.4")
    if "| Capability | 0.5 |" in (ROOT / "README.md").read_text(encoding="utf-8"):
        raise SystemExit("README.md capability table still labels the release as 0.5")

    scrub_paths = [
        ROOT / "README.md",
        ROOT / "examples/README.md",
        ROOT / "docs/README.md",
        ROOT / "docs/01_GETTING_STARTED/INSTALLATION.md",
        ROOT / "docs/01_GETTING_STARTED/FAQ.md",
        ROOT / "docs/01_GETTING_STARTED/README.md",
        ROOT / "docs/01_GETTING_STARTED/QUICKSTART.md",
        ROOT / "docs/01_GETTING_STARTED/FIRST_PIPELINE.md",
        ROOT / "docs/01_GETTING_STARTED/CAPABILITIES.md",
        ROOT / "docs/02_FOUNDATIONS/DOCUMENTATION_STATUS.md",
        ROOT / "docs/06_EXECUTION/LOCAL_PYTHON.md",
        ROOT / "docs/06_EXECUTION/SECRETS_MANAGEMENT.md",
        ROOT / "docs/08_VISUALIZATION/MERMAID.md",
        ROOT / "docs/09_EXAMPLES/README.md",
        ROOT / "docs/10_REFERENCE/API_REFERENCE.md",
        ROOT / "docs/10_REFERENCE/CLI.md",
        ROOT / "docs/10_REFERENCE/COMPATIBILITY.md",
        ROOT / "docs/11_DEVELOPMENT/CONTRIBUTING.md",
        ROOT / "docs/theme/javascripts/status-banner.js",
    ]
    for path in scrub_paths:
        text = path.read_text(encoding="utf-8")
        for phrase in banned_phrases:
            if phrase in text:
                raise SystemExit(
                    f"{path} still contains banned stale phrase: {phrase!r}"
                )

    # Design example pages must carry a future-design admonition
    for path in (ROOT / "docs/09_EXAMPLES").glob("*.md"):
        if path.name == "README.md":
            continue
        text = path.read_text(encoding="utf-8")
        if "Future design—not a Pipelantic 0.6 API guide" not in text:
            raise SystemExit(f"{path} missing Future design admonition")

    banner_js = (ROOT / "docs/theme/javascripts/status-banner.js").read_text(
        encoding="utf-8"
    )
    if "Future design—not a Pipelantic 0.6 API guide" not in banner_js:
        raise SystemExit("status-banner.js missing 0.6 future-design banner text")

    start = banner_js.find("futureExecutionPages = [")
    end = banner_js.find("];", start)
    if start < 0 or end < 0:
        raise SystemExit("status-banner.js missing futureExecutionPages array")
    future_block = banner_js[start:end]
    for shipped in (
        "SQL",
        "SQL_EXECUTION",
        "SQL_PUSHDOWN",
        "POLARS",
        "PANDAS",
        "DATAFRAME_PLUGINS",
    ):
        # Exact token match: "SQL" must not match SQL_EXECUTION incorrectly —
        # check quoted entries.
        if f'"{shipped}"' in future_block:
            raise SystemExit(
                f"status-banner.js still lists shipped page {shipped!r} as future"
            )

    # Shipped plugin-protocol pages must be excluded from the future Plugin SDK banner
    for shipped_sdk in ("DATAFRAME_PLUGIN", "SQL_PLUGIN", "SQL_DIALECT"):
        if f"/07_PLUGIN_SDK/{shipped_sdk}/" not in banner_js:
            raise SystemExit(
                f"status-banner.js must exclude {shipped_sdk} from future Plugin SDK banner"
            )

    secrets = (ROOT / "docs/06_EXECUTION/SECRETS_MANAGEMENT.md").read_text(
        encoding="utf-8"
    )
    if "Available in 0.5" not in secrets and "shipped" not in secrets.lower():
        raise SystemExit("SECRETS_MANAGEMENT.md missing shipped-in-0.5 banner")
    if 'provider = "aws-secrets-manager"' in secrets:
        raise SystemExit(
            "SECRETS_MANAGEMENT.md still shows aws-secrets-manager as current config"
        )

    print(f"Documentation consistency checks passed for {package_version}.")


if __name__ == "__main__":
    main()
