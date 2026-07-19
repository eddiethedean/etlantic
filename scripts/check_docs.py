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
        # Adopter-facing 0.17→0.18 drift (docs adoption audit)
        "Status in 0.17",
        "Implemented in 0.17",
        "0.17 reference envelope",
        "0.17 status",
        "0.17 support envelope",
        "implemented 0.17 controls",
        "Is ETLantic 0.17 production-supported?",
        "ETLantic 0.18.0 shipped portable coverage expansion",
        "not a ETLantic 0.11 API guide",
        "etlantic==0.13.0",
        "etlantic-polars==0.13.0",
        "etlantic-pyspark==0.13.0",
        "etlantic==0.14.0",
        "etlantic-polars==0.14.0",
        "etlantic-pandas==0.14.0",
        "etlantic-sql==0.14.0",
        "etlantic-pyspark==0.14.0",
        "Pandas / SQL compilers remain 0.14\u20130.15",
        "Pandas and SQL portable compilers remain",
        "Safe SQL portable lowering planned for the **0.15** exit gate",
        "Safe SQL portable lowering remains planned for 0.15",
        "Optional Arrow interchange | Available when PyArrow is installed",
        "ETLantic 0.14 user guide",
        "into a 0.12 application",
        "0.18+ — Standards-Based Interchange and Local Analytics",
        "claim set is the **0.15** exit gate",
        "complete CLI-runnable example",
        "CLI-runnable continuation",
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
        # Stale "current = 0.10" claims after 0.11 ship
        "| Capability | 0.10 |",
        "Current 0.10 User Guide",
        "Current 0.10 guide",
        "Available in ETLantic 0.10",
        "does not ship `@Transformation.portable`",
        "etlantic==0.10.0",
        "etlantic>=0.10.0",
        # Stale "current = 0.11" claims after 0.12 ship
        "Current 0.11 guide",
        "Current 0.11 User Guide",
        "Available in 0.11\n",
        "## Available in 0.11",
        "ETLantic 0.11 is alpha",
        "not an ETLantic 0.10 API guide",
        "once compilers ship",
        "eventual runnable example",
        "Profile selection (planned 0.12+)",
        "compilers remain 0.12+",
        "from etlantic.plugins import register_sql_plugin",
        "from etlantic.plugins import register_pyspark_plugin",
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
    major_minor = ".".join(package_version.split(".")[:2])
    if f"| Capability | {major_minor} |" not in (ROOT / "README.md").read_text(
        encoding="utf-8"
    ):
        raise SystemExit(
            f"README.md capability table must label the release as {major_minor}"
        )
    # Ban prior minor capability headers once we have advanced past them.
    prior_minors = []
    try:
        major_s, minor_s = major_minor.split(".")
        prior_minors = [f"{major_s}.{i}" for i in range(int(minor_s))]
    except ValueError:
        prior_minors = []
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    for prior in prior_minors:
        if f"| Capability | {prior} |" in readme_text:
            raise SystemExit(
                f"README.md capability table still labels the release as {prior}"
            )

    mkdocs = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    if "Current 0.10 Guide:" in mkdocs or (
        major_minor != "0.10" and "Current 0.10 Guide:" in mkdocs
    ):
        raise SystemExit("mkdocs.yml still labels Learn nav as Current 0.10 Guide")
    if f"Current {major_minor} Guide:" not in mkdocs:
        raise SystemExit(
            f"mkdocs.yml must label Learn nav as Current {major_minor} Guide"
        )

    evaluator = (ROOT / "docs/01_GETTING_STARTED/EVALUATOR.md").read_text(
        encoding="utf-8"
    )
    if (
        "What not to bet on yet" in evaluator
        and "@Transformation.portable` / `etlantic.transform` (the DTCS" in evaluator
    ):
        raise SystemExit(
            "EVALUATOR.md must not tell readers not to bet on portable authoring "
            "while Capabilities marks authoring Available"
        )
    if (
        "Portable Polars compiler (kernel + relational `/1`) | Yes (0.13"
        not in evaluator
        and "Portable Polars kernel compiler | Yes (0.12)" not in evaluator
    ):
        raise SystemExit(
            "EVALUATOR.md must list Portable Polars compiler as ready (0.12+)"
        )
    if "Portable PySpark compiler (kernel + relational `/1`) | Yes (0.13" not in (
        evaluator
    ):
        raise SystemExit(
            "EVALUATOR.md must list Portable PySpark relational compiler as ready"
        )
    if (
        "Portable Pandas compiler (kernel + relational `/1`, eager) | Yes (0.14)"
        not in (evaluator)
    ):
        raise SystemExit(
            "EVALUATOR.md must list Portable Pandas relational compiler as ready"
        )
    if "Portable SQL compiler (kernel + relational `/1`) | Yes (0.15)" not in (
        evaluator
    ):
        raise SystemExit(
            "EVALUATOR.md must list Portable SQL relational compiler as ready"
        )
    if "Portable SQL compiler (kernel + relational `/1`) | No" in evaluator:
        raise SystemExit(
            "EVALUATOR.md must not deny Portable SQL after the 0.15 exit gate"
        )
    if "end-to-end portable execution on Polars, PySpark" in evaluator:
        raise SystemExit(
            "EVALUATOR.md must not deny Polars portable execution after 0.12"
        )
    if "MIGRATION_0_11_TO_0_12.md" not in (
        ROOT / "docs/11_DEVELOPMENT/README.md"
    ).read_text(encoding="utf-8"):
        raise SystemExit("Development README missing Migration 0.11 → 0.12")
    if not (ROOT / "docs/11_DEVELOPMENT/MIGRATION_0_11_TO_0_12.md").exists():
        raise SystemExit("Missing docs/11_DEVELOPMENT/MIGRATION_0_11_TO_0_12.md")
    if not (ROOT / "docs/11_DEVELOPMENT/MIGRATION_0_12_TO_0_13.md").exists():
        raise SystemExit("Missing docs/11_DEVELOPMENT/MIGRATION_0_12_TO_0_13.md")
    if not (ROOT / "docs/11_DEVELOPMENT/MIGRATION_0_13_TO_0_14.md").exists():
        raise SystemExit("Missing docs/11_DEVELOPMENT/MIGRATION_0_13_TO_0_14.md")
    if not (ROOT / "docs/11_DEVELOPMENT/MIGRATION_0_14_TO_0_15.md").exists():
        raise SystemExit("Missing docs/11_DEVELOPMENT/MIGRATION_0_14_TO_0_15.md")
    if not (ROOT / "docs/05_PIPELINES/EXTRACTS.md").exists():
        raise SystemExit("Missing docs/05_PIPELINES/EXTRACTS.md")
    if not (ROOT / "docs/05_PIPELINES/LOADS.md").exists():
        raise SystemExit("Missing docs/05_PIPELINES/LOADS.md")
    if not (ROOT / "docs/01_GETTING_STARTED/WHATS_NEW_0_14.md").exists():
        raise SystemExit("Missing docs/01_GETTING_STARTED/WHATS_NEW_0_14.md")
    if not (ROOT / "docs/01_GETTING_STARTED/WHATS_NEW_0_15.md").exists():
        raise SystemExit("Missing docs/01_GETTING_STARTED/WHATS_NEW_0_15.md")
    if not (ROOT / "docs/01_GETTING_STARTED/WHATS_NEW_0_16.md").exists():
        raise SystemExit("Missing docs/01_GETTING_STARTED/WHATS_NEW_0_16.md")
    # e.g. 0.17.0 → WHATS_NEW_0_17.md (drop patch)
    major_minor_for_notes = ".".join(package_version.split(".")[:2])
    whats_new_minor = (
        ROOT
        / "docs/01_GETTING_STARTED"
        / f"WHATS_NEW_{major_minor_for_notes.replace('.', '_')}.md"
    )
    if not whats_new_minor.exists():
        raise SystemExit(f"Missing {whats_new_minor.relative_to(ROOT)}")
    if not (ROOT / "docs/11_DEVELOPMENT/MIGRATION_0_15_TO_0_16.md").exists():
        raise SystemExit("Missing docs/11_DEVELOPMENT/MIGRATION_0_15_TO_0_16.md")
    try:
        major, minor = major_minor_for_notes.split(".")
        previous_minor = f"{major}.{int(minor) - 1}"
    except (ValueError, TypeError):
        previous_minor = None
    if previous_minor is not None:
        current_migration = (
            ROOT
            / "docs/11_DEVELOPMENT"
            / (
                f"MIGRATION_{previous_minor.replace('.', '_')}"
                f"_TO_{major_minor_for_notes.replace('.', '_')}.md"
            )
        )
        if not current_migration.exists():
            raise SystemExit(f"Missing {current_migration.relative_to(ROOT)}")
    if not (ROOT / "examples/portable_polars_kernel.py").exists():
        raise SystemExit("Missing examples/portable_polars_kernel.py")
    if not (ROOT / "examples/portable_pandas_kernel.py").exists():
        raise SystemExit("Missing examples/portable_pandas_kernel.py")
    if not (ROOT / "src/etlantic/__main__.py").exists():
        raise SystemExit("Missing src/etlantic/__main__.py for python -m etlantic")
    if not (ROOT / "src/etlantic/py.typed").exists():
        raise SystemExit("Missing src/etlantic/py.typed")
    mkdocs_text = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    for migration in (
        "MIGRATION_0_11_TO_0_12.md",
        "MIGRATION_0_12_TO_0_13.md",
        "MIGRATION_0_13_TO_0_14.md",
        "MIGRATION_0_14_TO_0_15.md",
        "MIGRATION_0_15_TO_0_16.md",
        "MIGRATION_0_16_TO_0_17.md",
        "MIGRATION_0_17_TO_0_18.md",
    ):
        if migration not in mkdocs_text:
            raise SystemExit(f"mkdocs.yml missing {migration} nav entry")
    whats_new_nav = f"WHATS_NEW_{major_minor_for_notes.replace('.', '_')}.md"
    if whats_new_nav not in mkdocs_text:
        raise SystemExit(f"mkdocs.yml missing {whats_new_nav} nav entry")
    if f"Configuration in {major_minor_for_notes}" not in mkdocs_text and (
        f"Configuration in {package_version}" not in mkdocs_text
    ):
        raise SystemExit(
            "mkdocs.yml must label configuration for the current release "
            f"({major_minor_for_notes} or {package_version})"
        )
    if "Configuration in 0.16.0" in mkdocs_text:
        raise SystemExit("mkdocs.yml still labels configuration as 0.16.0")
    for required_nav in (
        "06_EXECUTION/DEPLOYMENT.md",
        "11_DEVELOPMENT/PERFORMANCE.md",
        "11_DEVELOPMENT/DOCUMENTATION_AUDIT_0_17.md",
        "09_EXAMPLES/PREFECT_RUN.md",
        "  - Plugin SDK:",
        "  - Release notes:",
    ):
        if required_nav not in mkdocs_text:
            raise SystemExit(f"mkdocs.yml missing required nav entry {required_nav!r}")
    if "05_PIPELINES/EXTRACTS.md" not in mkdocs_text:
        raise SystemExit("mkdocs.yml missing EXTRACTS.md nav entry")
    if "05_PIPELINES/LOADS.md" not in mkdocs_text:
        raise SystemExit("mkdocs.yml missing LOADS.md nav entry")
    if "Design Proposals:" in mkdocs_text and mkdocs_text.find(
        "Design Proposals:"
    ) < mkdocs_text.find("  - Reference:"):
        raise SystemExit(
            "mkdocs.yml must place Design Proposals after current Reference/Project sections"
        )
    mkdocs_text = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    plugin_sdk_idx = mkdocs_text.find("  - Plugin SDK:")
    design_idx = mkdocs_text.find("  - Design Proposals:")
    compiler_idx = mkdocs_text.find(
        "Portable Transform Compiler: 07_PLUGIN_SDK/PORTABLE_TRANSFORM_COMPILER.md"
    )
    if (
        plugin_sdk_idx < 0
        or compiler_idx < plugin_sdk_idx
        or (design_idx >= 0 and compiler_idx > design_idx)
    ):
        raise SystemExit(
            "mkdocs.yml must promote Portable Transform Compiler under Plugin SDK"
        )
    design_proposals = (ROOT / "docs/11_DEVELOPMENT/DESIGN_PROPOSALS.md").read_text(
        encoding="utf-8"
    )
    if (
        "contains unshipped APIs" in design_proposals
        and "Exception" not in design_proposals
        and "authoring" not in design_proposals.lower()
    ):
        raise SystemExit(
            "DESIGN_PROPOSALS.md must not claim all linked pages are unshipped "
            "without carving out shipped portable authoring"
        )

    # Shipped capabilities must not be denied on primary getting-started pages.
    capabilities = (ROOT / "docs/01_GETTING_STARTED/CAPABILITIES.md").read_text(
        encoding="utf-8"
    )
    for required in (
        "etlantic-airflow",
        "etlantic-prefect",
        "etlantic-sparkforge",
        "etlantic-keyring",
        "Graphviz",
    ):
        if required not in capabilities:
            raise SystemExit(f"CAPABILITIES.md missing shipped surface {required!r}")
    if "Best-effort Arrow-assisted conversion" not in capabilities:
        raise SystemExit(
            "CAPABILITIES.md must label today's Arrow helper as best-effort conversion"
        )
    if (
        "Optional Arrow interchange | Available when PyArrow is installed"
        in capabilities
    ):
        raise SystemExit(
            "CAPABILITIES.md must not advertise formal Optional Arrow interchange as shipped"
        )
    if (
        "Versioned tabular interchange (`etlantic.interchange/1`)" not in capabilities
        or "**0.18.0 Gate A — Available**" not in capabilities
    ):
        raise SystemExit(
            "CAPABILITIES.md must mark 0.18.0 Gate A interchange Available"
        )
    roadmap_summary = (ROOT / "docs/11_DEVELOPMENT/ROADMAP_SUMMARY.md").read_text(
        encoding="utf-8"
    )
    if "Gate A = **0.18.0**" not in roadmap_summary and "0.18.0" not in roadmap_summary:
        raise SystemExit("ROADMAP_SUMMARY.md must state 0.18.0 Gate A scope")
    if "non-blocking" not in roadmap_summary.lower():
        raise SystemExit(
            "ROADMAP_SUMMARY.md must label DataFusion as non-blocking for 0.18.0"
        )
    interop = (
        ROOT / "docs/11_DEVELOPMENT/INTEROPERABILITY_FOUNDATION_PLAN.md"
    ).read_text(encoding="utf-8")
    for required in (
        "etlantic.interchange/1",
        "A0",
        "A4",
        "parquet_artifact",
        "records_fallback",
        "Decision locks",
    ):
        if required not in interop:
            raise SystemExit(
                f"INTEROPERABILITY_FOUNDATION_PLAN.md missing required Gate A content {required!r}"
            )
    if "0.18+ — Standards-Based Interchange" in (ROOT / "ROADMAP.md").read_text(
        encoding="utf-8"
    ):
        raise SystemExit(
            "ROADMAP.md must use Gate A-first 0.18 title, not the old 0.18+ program title"
        )
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    # e.g. 0.14.0 → 0.14.x
    major_minor = ".".join(package_version.split(".")[:2])
    if f"| {major_minor}.x |" not in security:
        raise SystemExit(
            f"SECURITY.md support table must list {major_minor}.x as current"
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
        ROOT / "packages/etlantic-polars/README.md",
        ROOT / "packages/etlantic-pandas/README.md",
        ROOT / "packages/etlantic-pyspark/README.md",
        ROOT / "packages/etlantic-sql/README.md",
        ROOT / "packages/etlantic-sparkforge/README.md",
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
        "PORTABLE_TRANSFORMS.md",
        "INTERCHANGE_POLARS_PANDAS.md",
        "CONTRACT_FIRST_TUTORIAL.md",
        "PREFECT_RUN.md",
        "SAMPLE_PROJECT.md",
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
            re.search(
                r"Future design—not a[n]? ETLantic \d+\.\d+ API guide",
                text,
            )
            is None
            and "Design study—" not in text
            and "Experimental design study—" not in text
            and "Available in ETLantic" not in text
        ):
            raise SystemExit(f"{path} missing Future design / design-study admonition")

    future_plugin_pages = [
        ROOT / "docs/07_PLUGIN_SDK/STORAGE_PLUGIN.md",
        ROOT / "docs/07_PLUGIN_SDK/RESOURCE_PROVIDER.md",
        ROOT / "docs/07_PLUGIN_SDK/OBSERVABILITY_PROVIDER.md",
    ]
    for path in future_plugin_pages:
        text = path.read_text(encoding="utf-8")
        if "Future design" not in text and "!!! warning" not in text:
            raise SystemExit(f"{path} missing Future design admonition")

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
    green_block = docs_home[green_idx : green_idx + 700]
    if "INSTALLATION.md" not in green_block.split("Quickstart")[0]:
        raise SystemExit("docs/README.md Green path must lead with Installation")
    if green_block.find("INSTALLATION.md") > green_block.find("WHATS_NEW_"):
        # Installation should precede release notes for first-time visitors.
        install_pos = green_block.find("INSTALLATION.md")
        whats_pos = green_block.find(f"WHATS_NEW_{major_minor.replace('.', '_')}")
        if whats_pos >= 0 and install_pos > whats_pos:
            raise SystemExit(
                "docs/README.md Green path must place Installation before What's new"
            )
    if "prefer from-source until PyPI" in docs_home:
        raise SystemExit("docs/README.md still prefers from-source install")
    # Current What's New must not point at the prior release notes file.
    whats_new_current_link = f"WHATS_NEW_{major_minor.replace('.', '_')}.md"
    prior_whats_new = None
    try:
        maj_s, min_s = major_minor.split(".")
        if int(min_s) > 0:
            prior_whats_new = f"WHATS_NEW_{maj_s}_{int(min_s) - 1}.md"
    except ValueError:
        prior_whats_new = None
    for label in (
        f"What's new in {major_minor}",
        f"What's new in {package_version}",
    ):
        if label in docs_home and prior_whats_new is not None:
            # Find the markdown link target after the label.
            idx = docs_home.find(label)
            snippet = docs_home[idx : idx + 120]
            if prior_whats_new in snippet and whats_new_current_link not in snippet:
                raise SystemExit(
                    "docs/README.md What's new link targets the prior release notes"
                )
    if (
        f"What's new in {major_minor}" in docs_home
        and whats_new_current_link not in docs_home
    ):
        raise SystemExit(
            f"docs/README.md must link What's new in {major_minor} to {whats_new_current_link}"
        )
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
    api_corpus = "\n".join(
        [
            api_ref,
            (ROOT / "docs/10_REFERENCE/API_AUTHORING.md").read_text(encoding="utf-8"),
            (ROOT / "docs/10_REFERENCE/API_PLAN_RUNTIME.md").read_text(
                encoding="utf-8"
            ),
            (ROOT / "docs/10_REFERENCE/API_PROTOCOLS.md").read_text(encoding="utf-8"),
        ]
    )
    major_minor = ".".join(package_version.split(".")[:2])
    if f"Available in ETLantic {major_minor}" not in api_ref:
        raise SystemExit(
            f"API_REFERENCE.md must claim Available in ETLantic {major_minor}"
        )
    for mod in ("etlantic.spark", "etlantic.orchestration", "etlantic.viz"):
        if mod not in api_corpus:
            raise SystemExit(f"API reference pages missing {mod}")

    banner_js = (ROOT / "docs/theme/javascripts/status-banner.js").read_text(
        encoding="utf-8"
    )
    if "AIRFLOW_COMPILE/" not in banner_js or "SPARKFORGE_ADAPTER/" not in banner_js:
        raise SystemExit(
            "status-banner.js must exclude runnable example guides from design banner"
        )
    if "PREFECT_RUN/" not in banner_js:
        raise SystemExit(
            "status-banner.js must exclude PREFECT_RUN from design-example banner"
        )
    if "CONTRACT_FIRST_TUTORIAL/" not in banner_js:
        raise SystemExit(
            "status-banner.js must exclude CONTRACT_FIRST_TUTORIAL from design banner"
        )
    if 'banner.dataset.etlanticStatus = "future"' not in banner_js:
        raise SystemExit("status-banner.js missing semantic future-status marker")
    if "Experimental in ETLantic 0.7" not in banner_js:
        raise SystemExit("status-banner.js missing experimental streaming banner text")
    if f"not an ETLantic {major_minor} API guide" not in banner_js:
        raise SystemExit(
            f"status-banner.js future banner must reference ETLantic {major_minor}"
        )
    if "PORTABLE_TRANSFORMS/" not in banner_js:
        raise SystemExit(
            "status-banner.js must exclude PORTABLE_TRANSFORMS from design-example banner"
        )
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

    # Only unshipped provider protocols belong in the future Plugin SDK banner.
    start = banner_js.find("futurePluginSdkPages = [")
    end = banner_js.find("];", start)
    if start < 0 or end < 0:
        raise SystemExit("status-banner.js missing futurePluginSdkPages array")
    future_sdk_block = banner_js[start:end]
    for future_sdk in (
        "STORAGE_PLUGIN",
        "RESOURCE_PROVIDER",
        "OBSERVABILITY_PROVIDER",
    ):
        if f'"{future_sdk}"' not in future_sdk_block:
            raise SystemExit(f"status-banner.js must mark {future_sdk} as future")

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
        ROOT / "packages/etlantic-prefect/pyproject.toml",
        ROOT / "packages/etlantic-keyring/pyproject.toml",
        ROOT / "packages/etlantic-sqlmodel/pyproject.toml",
        ROOT / "packages/etlantic-sparkforge/pyproject.toml",
    ):
        plugin_version = version_from(plugin_pyproject, r'(?m)^version = "([^"]+)"')
        if plugin_version != package_version:
            raise SystemExit(
                f"{plugin_pyproject} version {plugin_version} != core {package_version}"
            )

    # Embedded plugin component versions must also match.
    for component in (
        ROOT / "packages/etlantic-airflow/src/etlantic_airflow/plugin.py",
        ROOT / "packages/etlantic-prefect/src/etlantic_prefect/plugin.py",
        ROOT / "packages/etlantic-pyspark/src/etlantic_pyspark/plugin.py",
        ROOT / "packages/etlantic-pyspark/src/etlantic_pyspark/provider.py",
        ROOT / "packages/etlantic-sql/src/etlantic_sql/plugin.py",
        ROOT / "packages/etlantic-sql/src/etlantic_sql/transform_compiler.py",
        ROOT / "packages/etlantic-polars/src/etlantic_polars/__init__.py",
        ROOT / "packages/etlantic-polars/src/etlantic_polars/compiler.py",
        ROOT / "packages/etlantic-pyspark/src/etlantic_pyspark/compiler.py",
        ROOT / "packages/etlantic-pandas/src/etlantic_pandas/compiler.py",
    ):
        text = component.read_text(encoding="utf-8")
        match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
        if match is None:
            raise SystemExit(f"{component} missing __version__")
        if match.group(1) != package_version:
            raise SystemExit(
                f"{component} __version__ {match.group(1)} != core {package_version}"
            )

    # Getting-started / support pages must not present the prior minor as current.
    prior_minor = None
    try:
        maj_s, min_s = major_minor.split(".")
        if int(min_s) > 0:
            prior_minor = f"{maj_s}.{int(min_s) - 1}"
    except ValueError:
        prior_minor = None
    if prior_minor is not None:
        for path in (
            ROOT / "docs/01_GETTING_STARTED/README.md",
            ROOT / "docs/01_GETTING_STARTED/CAPABILITIES.md",
            ROOT / "docs/01_GETTING_STARTED/EVALUATOR.md",
            ROOT / "docs/02_FOUNDATIONS/DOCUMENTATION_STATUS.md",
            ROOT / "docs/10_REFERENCE/README.md",
            ROOT / "SUPPORT.md",
        ):
            text = path.read_text(encoding="utf-8")
            for phrase in (
                f"Current {prior_minor} guide",
                f"## Available in {prior_minor}",
                f"ETLantic {prior_minor} is alpha",
                f"separates ETLantic **{prior_minor}**",
            ):
                if phrase in text:
                    raise SystemExit(
                        f"{path} still presents {prior_minor} as current: {phrase!r}"
                    )
            if (
                f"`{prior_minor}.x`" in text
                and "current published minor" in text.lower()
            ):
                raise SystemExit(
                    f"{path} support line still names {prior_minor}.x as current"
                )

    # Active install/tutorial pins must not target the prior minor release.
    prior_pin_paths = [
        ROOT / "docs/01_GETTING_STARTED/INSTALLATION.md",
        ROOT / "docs/01_GETTING_STARTED/QUICKSTART.md",
        ROOT / "docs/01_GETTING_STARTED/TROUBLESHOOTING.md",
        ROOT / "docs/02_FOUNDATIONS/SECURITY.md",
        ROOT / "docs/06_EXECUTION/POLARS_TUTORIAL.md",
        ROOT / "docs/06_EXECUTION/PANDAS_TUTORIAL.md",
        ROOT / "docs/06_EXECUTION/SQL_TUTORIAL.md",
        ROOT / "docs/06_EXECUTION/PYSPARK_TUTORIAL.md",
        ROOT / "docs/06_EXECUTION/AIRFLOW_TUTORIAL.md",
        ROOT / "docs/06_EXECUTION/FILE_STORAGE_TUTORIAL.md",
        ROOT / "docs/06_EXECUTION/DATAFRAME_PLUGINS.md",
        ROOT / "docs/06_EXECUTION/PILOT_WALKTHROUGH.md",
        ROOT / "docs/06_EXECUTION/OPS_PILOT.md",
        ROOT / "docs/06_EXECUTION/PRODUCTION_READINESS.md",
        ROOT / "docs/06_EXECUTION/PRODUCTION_PROFILES.md",
        ROOT / "docs/07_PLUGIN_SDK/THIRD_PARTY_COMPILER_TUTORIAL.md",
        ROOT / "docs/07_PLUGIN_SDK/BUILDING_A_PLUGIN.md",
        ROOT / "docs/09_EXAMPLES/PORTABLE_TRANSFORMS.md",
        ROOT / "docs/09_EXAMPLES/PREFECT_RUN.md",
        ROOT / "docs/10_REFERENCE/OPTIONAL_PACKAGES.md",
        ROOT / "docs/10_REFERENCE/PORTABLE_COMPILER_MATRIX.md",
        ROOT / "docs/10_REFERENCE/CLI.md",
        ROOT / "packages/etlantic-airflow/README.md",
        ROOT / "packages/etlantic-keyring/README.md",
        ROOT / "packages/etlantic-sqlmodel/README.md",
        ROOT / "packages/etlantic-sparkforge/README.md",
        ROOT / "packages/etlantic-prefect/README.md",
        ROOT / "examples/portable_polars_kernel.py",
        ROOT / "examples/portable_pandas_kernel.py",
    ]
    if prior_minor is not None:
        prior_pin = f"etlantic=={prior_minor}.0"
        prior_range = f">={prior_minor}.0,<{major_minor}"
        prior_range_short = f">={prior_minor},<{major_minor}"
        prior_tag = f"v{prior_minor}.0"
        for path in prior_pin_paths:
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            if prior_pin in text:
                raise SystemExit(f"{path} still pins {prior_pin}")
            if prior_range in text or prior_range_short in text:
                raise SystemExit(f"{path} still uses prior-minor range {prior_range}")
            if f"etlantic-polars=={prior_minor}.0" in text:
                raise SystemExit(f"{path} still pins etlantic-polars=={prior_minor}.0")
            if prior_tag in text and f"v{package_version}" not in text:
                raise SystemExit(f"{path} still references checkout {prior_tag}")
            if "planned for 0.16" in text.lower() or "planned for **0.16" in text:
                raise SystemExit(f"{path} still says Prefect/features planned for 0.16")

    # Current authoring guides must not teach removed Extract/Load binding=.
    binding_scan_roots = [
        ROOT / "docs/03_DATA_CONTRACTS",
        ROOT / "docs/05_PIPELINES",
        ROOT / "docs/06_EXECUTION",
        ROOT / "docs/07_PLUGIN_SDK",
        ROOT / "docs/09_EXAMPLES",
    ]
    binding_pattern = re.compile(
        r"(Extract|Load|Source|Sink)\[[^\]]*\]\([^\)]*\bbinding\s*="
    )
    for root in binding_scan_roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.md")):
            name_u = path.name.upper()
            if "MIGRATION" in name_u or name_u.startswith("WHATS_NEW"):
                continue
            text = path.read_text(encoding="utf-8")
            if binding_pattern.search(text):
                raise SystemExit(
                    f"{path} still shows Extract/Load binding= constructor usage"
                )
    # Classifiers and plugin dependency ranges must match the stable posture.
    stable_classifier = "Development Status :: 5 - Production/Stable"
    alpha_classifier = "Development Status :: 3 - Alpha"
    next_minor = None
    try:
        maj_s, min_s = major_minor.split(".")
        next_minor = f"{maj_s}.{int(min_s) + 1}"
    except ValueError:
        next_minor = None
    for path in (
        ROOT / "pyproject.toml",
        *(ROOT / "packages").glob("etlantic-*/pyproject.toml"),
    ):
        text = path.read_text(encoding="utf-8")
        if alpha_classifier in text:
            raise SystemExit(f"{path} still uses Alpha classifier")
        if stable_classifier not in text:
            raise SystemExit(f"{path} missing Production/Stable classifier")
        if path.parent.name.startswith("etlantic-") and next_minor is not None:
            expected = f"etlantic>={package_version},<{next_minor}"
            # Also accept major.minor.0 style already used.
            expected_alt = f"etlantic>={major_minor}.0,<{next_minor}"
            if expected not in text and expected_alt not in text:
                raise SystemExit(
                    f"{path} must depend on {expected_alt} (found mismatched core range)"
                )

    # Primary status pages must not call the current line alpha.
    for path in (
        ROOT / "README.md",
        ROOT / "docs/README.md",
        ROOT / "SUPPORT.md",
        ROOT / "SECURITY.md",
        ROOT / "docs/01_GETTING_STARTED/CAPABILITIES.md",
        ROOT / "docs/01_GETTING_STARTED/README.md",
    ):
        text = path.read_text(encoding="utf-8")
        for banned in (
            f"Alpha **{package_version}**",
            f"Alpha {package_version}",
            f"alpha **{package_version}**",
            "Project status:** Alpha",
            "Package stability | Alpha",
        ):
            if banned in text:
                raise SystemExit(
                    f"{path} still presents current release as alpha: {banned!r}"
                )

    subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_runnable_docs.py")],
        check=True,
    )

    print(f"Documentation consistency checks passed for {package_version}.")


if __name__ == "__main__":
    main()
