"""Small dependency-free documentation consistency checks."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]


def version_from(path: Path, pattern: str) -> str:
    match = re.search(pattern, path.read_text(encoding="utf-8"))
    if match is None:
        raise SystemExit(f"Could not find version in {path}")
    return match.group(1)


def main() -> None:
    package_version = version_from(
        ROOT / "src/etlantic/_version.py", r'__version__ = "([^"]+)"'
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
        "Pandas, Polars, SQL, Spark, and Airflow plugins are not published as part of\nETLantic 0.4",
        "Future plugins may add Pandas, Polars",
        "Pandas and Polars pipelines | Future plugin design",
        "Pandas, Polars, SQL, Spark, and Airflow plugins | Not yet available",
        "SQL, Spark, and Airflow plugins | Not yet available",
        "SQL compilation or execution | Future design (0.6)",
        "SQL, Spark, and Airflow compilation are not shipped",
        "These examples use only APIs and dependencies shipped in ETLantic 0.4",
        "These examples use only APIs and dependencies shipped in ETLantic 0.5",
        "These examples use only APIs and dependencies shipped in ETLantic 0.6",
        "Available in ETLantic 0.4.0",
        "not a ETLantic 0.4 API guide",
        "not a ETLantic 0.5 API guide",
        "not a ETLantic 0.6 API guide",
        "not a ETLantic 0.7 API guide",
        "Dataframe, SQL, Spark, and external orchestration chapters remain accepted",
        "Spark and Airflow plugins are not part of 0.6",
        "Spark / Airflow | No",
        "PySpark and streaming | Future plugin design",
        "Still accepted design until later milestones:** Spark",
        "Spark and Airflow remain design material",
        "Later milestones add Spark",
        "plan.to_mermaid()",
        "lightweight production workloads",
        "uv run pyright",
        "Commands are provisional until the implementation toolchain is committed",
        "Airflow or other orchestrator compilation | Future design (0.8)",
        "External orchestrator compilation is not included in 0.7",
        "Full CLI `compile` / generate tooling | Continues in 0.9",
        "Graphviz and generated HTML pipeline documentation | Future design",
        "Public third-party Plugin SDK polish | Continues in 0.9",
        "SparkForge migration adapter | Future design (0.10)",
        "SparkForge migration adapter | Future design",
        "External orchestration plugins (Airflow and peers) arrive later.",
        "Airflow and other orchestrator compilers are not part of 0.7",
        "Until 0.7.0 is on PyPI",
        "Airflow compilation | Future plugin design",
        "Generated Graphviz/HTML documentation | Future design",
        "Graphviz/HTML are future",
        "Graphviz/HTML exporters and plan-level Mermaid APIs\nare not shipped",
        "keyring, and cloud identity providers are\n**future design**",
        "| 0.7.x | Current alpha line",
        "git tag v0.6.1",
        "full CLI `compile` command (0.9)",
        "not a ETLantic 0.9 API guide",
        "Airflow compilation remains design material",
        "External orchestrators remain future",
        "cloud providers (Databricks/EMR/Connect) and Airflow compilation are not",
        "Examples that require Airflow or other orchestrators describe",
        "Spark / remote (future)",
        "# spark/             # future",
        "Data` remains as a deprecated",
        "These examples use only APIs and dependencies shipped in ETLantic 0.8",
        "Runnable now (0.7)",
        "ETLantic 0.8 can execute",
        "This section separates ETLantic **0.6**",
        "ETLantic 0.6\n    does not load",
        "future Airflow/orchestration plugins",
        "Visualization (beyond Mermaid)",
        "Future Design → Visualization",
        "not shipped in 0.5",
        "Only `Pipeline.to_mermaid()` is available in 0.6",
        "spark (future)",
        "not installable yet",
        "Design studies (not installable)",
        "PyPI may not have 0.10.0 yet",
        "Prefer **from-source** until a matching",
        "prefer from-source until PyPI has 0.10.0",
        "hosted site TBD",
        "pipeline.to_graphviz()",
        "plan.to_graphviz()",
        ".write_odcs(",
        "PluginRegistry.discover()",
        "plan.to_html()",
    ]
    if "| Capability | 0.4 |" in (ROOT / "README.md").read_text(encoding="utf-8"):
        raise SystemExit("README.md capability table still labels the release as 0.4")
    if "| Capability | 0.5 |" in (ROOT / "README.md").read_text(encoding="utf-8"):
        raise SystemExit("README.md capability table still labels the release as 0.5")
    if "| Capability | 0.6 |" in (ROOT / "README.md").read_text(encoding="utf-8"):
        raise SystemExit("README.md capability table still labels the release as 0.6")
    if "| Capability | 0.7 |" in (ROOT / "README.md").read_text(encoding="utf-8"):
        raise SystemExit("README.md capability table still labels the release as 0.7")
    if "| Capability | 0.8 |" in (ROOT / "README.md").read_text(encoding="utf-8"):
        raise SystemExit("README.md capability table still labels the release as 0.8")
    if "| Capability | 0.9 |" in (ROOT / "README.md").read_text(encoding="utf-8"):
        raise SystemExit("README.md capability table still labels the release as 0.9")

    # Shipped capabilities must not be denied on primary getting-started pages.
    capabilities = (ROOT / "docs/01_GETTING_STARTED/CAPABILITIES.md").read_text(
        encoding="utf-8"
    )
    for required in (
        "etlantic-airflow",
        "etlantic-sparkforge",
        "etlantic-keyring",
        "Graphviz",
    ):
        if required not in capabilities:
            raise SystemExit(f"CAPABILITIES.md missing shipped surface {required!r}")
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    if f"| {package_version.rsplit('.', 1)[0]}.x | Current alpha line" not in security:
        # e.g. 0.10.0 → 0.10.x
        major_minor = ".".join(package_version.split(".")[:2])
        if f"| {major_minor}.x | Current alpha line" not in security:
            raise SystemExit(
                f"SECURITY.md support table must list {major_minor}.x as current alpha"
            )

    scrub_paths = [
        ROOT / "README.md",
        ROOT / "examples/README.md",
        ROOT / "examples/quickstart.py",
        ROOT / "docs/README.md",
        ROOT / "docs/01_GETTING_STARTED/INSTALLATION.md",
        ROOT / "docs/01_GETTING_STARTED/TROUBLESHOOTING.md",
        ROOT / "docs/01_GETTING_STARTED/FAQ.md",
        ROOT / "docs/01_GETTING_STARTED/README.md",
        ROOT / "docs/01_GETTING_STARTED/QUICKSTART.md",
        ROOT / "docs/01_GETTING_STARTED/FIRST_PIPELINE.md",
        ROOT / "docs/01_GETTING_STARTED/PROJECT_STRUCTURE.md",
        ROOT / "docs/01_GETTING_STARTED/EVALUATOR.md",
        ROOT / "docs/01_GETTING_STARTED/CAPABILITIES.md",
        ROOT / "docs/02_FOUNDATIONS/DOCUMENTATION_STATUS.md",
        ROOT / "docs/06_EXECUTION/LOCAL_PYTHON.md",
        ROOT / "docs/06_EXECUTION/README.md",
        ROOT / "docs/06_EXECUTION/SECRETS_MANAGEMENT.md",
        ROOT / "docs/05_PIPELINES/PLANNING.md",
        ROOT / "docs/05_PIPELINES/PROFILES.md",
        ROOT / "docs/05_PIPELINES/DPCS.md",
        ROOT / "docs/08_VISUALIZATION/MERMAID.md",
        ROOT / "docs/08_VISUALIZATION/DOCUMENTATION.md",
        ROOT / "docs/08_VISUALIZATION/OPENAPI_FOR_PIPELINES.md",
        ROOT / "docs/08_VISUALIZATION/GRAPHVIZ.md",
        ROOT / "docs/08_VISUALIZATION/HTML.md",
        ROOT / "docs/08_VISUALIZATION/LINEAGE.md",
        ROOT / "docs/09_EXAMPLES/README.md",
        ROOT / "docs/09_EXAMPLES/AIRFLOW_COMPILE.md",
        ROOT / "docs/09_EXAMPLES/SPARKFORGE_ADAPTER.md",
        ROOT / "docs/10_REFERENCE/API_REFERENCE.md",
        ROOT / "docs/10_REFERENCE/README.md",
        ROOT / "docs/10_REFERENCE/KNOWN_ISSUES.md",
        ROOT / "docs/10_REFERENCE/CLI.md",
        ROOT / "docs/10_REFERENCE/COMPATIBILITY.md",
        ROOT / "docs/10_REFERENCE/CONFIGURATION.md",
        ROOT / "docs/10_REFERENCE/ENVIRONMENT_VARIABLES.md",
        ROOT / "docs/11_DEVELOPMENT/CONTRIBUTING.md",
        ROOT / "SECURITY.md",
        ROOT / "packages/etlantic-airflow/README.md",
        ROOT / "docs/theme/javascripts/status-banner.js",
        ROOT / "mkdocs.yml",
    ]
    for path in scrub_paths:
        text = path.read_text(encoding="utf-8")
        for phrase in banned_phrases:
            if phrase in text:
                raise SystemExit(
                    f"{path} still contains banned stale phrase: {phrase!r}"
                )

    # Design study pages need future/design admonitions; runnable guides do not.
    runnable_guides = {
        "AIRFLOW_COMPILE.md",
        "SPARKFORGE_ADAPTER.md",
        "README.md",
    }
    for path in (ROOT / "docs/09_EXAMPLES").glob("*.md"):
        if path.name in runnable_guides:
            if path.name != "README.md":
                text = path.read_text(encoding="utf-8")
                if (
                    "**Status: Available" not in text
                    and "Status: Available" not in text
                ):
                    raise SystemExit(f"{path} runnable guide missing Available status")
            continue
        text = path.read_text(encoding="utf-8")
        if "!!! warning" not in text:
            raise SystemExit(f"{path} missing design/future admonition")
        if (
            "Future design—not a ETLantic 0.10 API guide" not in text
            and "Design study—" not in text
            and "Experimental design study—" not in text
        ):
            raise SystemExit(f"{path} missing Future design / design-study admonition")

    # Honesty gate + nav SSOT
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if "pip install etlantic" not in readme:
        raise SystemExit("README.md missing pip-first install guidance")
    if "etlantic --version" not in readme:
        raise SystemExit("README.md missing etlantic --version verify step")
    if "hosted site TBD" in readme:
        raise SystemExit("README.md still says hosted site TBD")
    if "etlantic.readthedocs.io" not in readme:
        raise SystemExit("README.md missing hosted docs URL")
    if "Green path" not in (ROOT / "docs/README.md").read_text(encoding="utf-8"):
        raise SystemExit("docs/README.md missing Green path rail")
    docs_home = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    green_idx = docs_home.find("Green path")
    if green_idx < 0:
        raise SystemExit("docs/README.md missing Green path rail")
    green_block = docs_home[green_idx : green_idx + 500]
    if "INSTALLATION.md" not in green_block.split("Quickstart")[0]:
        raise SystemExit("docs/README.md Green path must lead with Installation")
    if "prefer from-source until PyPI" in docs_home:
        raise SystemExit("docs/README.md still prefers from-source install")
    known = (ROOT / "docs/10_REFERENCE/KNOWN_ISSUES.md").read_text(encoding="utf-8")
    if "etlantic-airflow" not in known:
        raise SystemExit(
            "KNOWN_ISSUES.md must state Airflow is available via etlantic-airflow"
        )
    mkdocs = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    if "site_url: https://etlantic.readthedocs.io/" not in mkdocs:
        raise SystemExit("mkdocs.yml site_url must be https://etlantic.readthedocs.io/")
    viz_idx = mkdocs.find("  - Visualization:")
    future_viz = mkdocs.find("Visualization (beyond Mermaid)")
    if future_viz >= 0:
        raise SystemExit(
            "mkdocs.yml still nests shipped viz under Visualization (beyond Mermaid)"
        )
    if viz_idx < 0:
        raise SystemExit("mkdocs.yml missing Visualization section")
    viz_block = mkdocs[viz_idx : viz_idx + 500]
    for shipped_viz in ("GRAPHVIZ.md", "HTML.md", "LINEAGE.md"):
        if shipped_viz not in viz_block:
            raise SystemExit(f"mkdocs.yml Visualization section missing {shipped_viz}")
    if "AIRFLOW_COMPILE.md" not in mkdocs or "SPARKFORGE_ADAPTER.md" not in mkdocs:
        raise SystemExit("mkdocs.yml missing runnable example guide pages")
    if "RUNTIME_CONFIGURATION.md" not in mkdocs:
        raise SystemExit("mkdocs.yml missing RUNTIME_CONFIGURATION.md")
    api_ref = (ROOT / "docs/10_REFERENCE/API_REFERENCE.md").read_text(encoding="utf-8")
    major_minor = ".".join(package_version.split(".")[:2])
    if f"Available in ETLantic {major_minor}" not in api_ref:
        raise SystemExit(
            f"API_REFERENCE.md must claim Available in ETLantic {major_minor}"
        )
    for mod in ("etlantic.spark", "etlantic.orchestration", "etlantic.viz"):
        if mod not in api_ref:
            raise SystemExit(f"API_REFERENCE.md missing {mod}")

    banner_js = (ROOT / "docs/theme/javascripts/status-banner.js").read_text(
        encoding="utf-8"
    )
    if "AIRFLOW_COMPILE/" not in banner_js or "SPARKFORGE_ADAPTER/" not in banner_js:
        raise SystemExit(
            "status-banner.js must exclude runnable example guides from design banner"
        )
    if 'banner.dataset.etlanticStatus = "future"' not in banner_js:
        raise SystemExit("status-banner.js missing semantic future-status marker")
    if "Experimental in ETLantic 0.7" not in banner_js:
        raise SystemExit("status-banner.js missing experimental streaming banner text")
    if "/08_VISUALIZATION/GRAPHVIZ/" not in banner_js:
        raise SystemExit(
            "status-banner.js must exclude GRAPHVIZ from future viz banner"
        )
    if "/08_VISUALIZATION/HTML/" not in banner_js:
        raise SystemExit("status-banner.js must exclude HTML from future viz banner")
    if "/08_VISUALIZATION/LINEAGE/" not in banner_js:
        raise SystemExit("status-banner.js must exclude LINEAGE from future viz banner")

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
        "PYSPARK",
        "PYSPARK_EXECUTION",
        "SPARK_OPTIMIZATION",
        "STRUCTURED_STREAMING",
        "ORCHESTRATION_PLUGINS",
        "AIRFLOW",
        "COMPILATION",
    ):
        # Exact token match: "SQL" must not match SQL_EXECUTION incorrectly —
        # check quoted entries.
        if f'"{shipped}"' in future_block:
            raise SystemExit(
                f"status-banner.js still lists shipped page {shipped!r} as future"
            )

    # Shipped plugin-protocol pages must be excluded from the future Plugin SDK banner
    for shipped_sdk in (
        "DATAFRAME_PLUGIN",
        "SQL_PLUGIN",
        "SQL_DIALECT",
        "PYSPARK_PLUGIN",
        "SPARK_PROVIDER",
        "ORCHESTRATOR_PLUGIN",
        "SECRET_PROVIDER",
        "TESTING_PLUGINS",
    ):
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

    # Plugin package versions must match core.
    for plugin_pyproject in (
        ROOT / "packages/etlantic-polars/pyproject.toml",
        ROOT / "packages/etlantic-pandas/pyproject.toml",
        ROOT / "packages/etlantic-sql/pyproject.toml",
        ROOT / "packages/etlantic-pyspark/pyproject.toml",
        ROOT / "packages/etlantic-airflow/pyproject.toml",
        ROOT / "packages/etlantic-keyring/pyproject.toml",
        ROOT / "packages/etlantic-sqlmodel/pyproject.toml",
        ROOT / "packages/etlantic-sparkforge/pyproject.toml",
    ):
        plugin_version = version_from(plugin_pyproject, r'(?m)^version = "([^"]+)"')
        if plugin_version != package_version:
            raise SystemExit(
                f"{plugin_pyproject} version {plugin_version} != core {package_version}"
            )

    subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_runnable_docs.py")],
        check=True,
    )

    print(f"Documentation consistency checks passed for {package_version}.")


if __name__ == "__main__":
    main()
