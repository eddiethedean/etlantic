"""Small dependency-free documentation consistency checks."""

from __future__ import annotations

import json
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
        ROOT / "docs/01_GETTING_STARTED/README.md",
        ROOT / "docs/01_GETTING_STARTED/FIRST_PIPELINE.md",
        ROOT / "docs/01_GETTING_STARTED/EVALUATOR.md",
        ROOT / "docs/01_GETTING_STARTED/FAQ.md",
        ROOT / "docs/01_GETTING_STARTED/CAPABILITIES.md",
        ROOT / "docs/09_EXAMPLES/README.md",
        ROOT / "SECURITY.md",
        ROOT / "SUPPORT.md",
    ]
    for path in current_markers:
        text = path.read_text(encoding="utf-8")
        if package_version not in text:
            raise SystemExit(
                f"{path} does not mention current version {package_version}"
            )

    support = (ROOT / "SUPPORT.md").read_text(encoding="utf-8")
    support_opening = "\n".join(support.splitlines()[:8]).lower()
    if (
        f"**{package_version}**" not in "\n".join(support.splitlines()[:8])
        or "beta" not in support_opening
    ):
        raise SystemExit(
            f"SUPPORT.md opening must claim {package_version} is Beta (PyPI)"
        )

    known_issues = (ROOT / "docs/10_REFERENCE/KNOWN_ISSUES.md").read_text(
        encoding="utf-8"
    )
    known_opening = "\n".join(known_issues.splitlines()[:12])
    major_minor = ".".join(package_version.split(".")[:2])
    if f"**{major_minor}.x**" not in known_opening or "Beta" not in known_opening:
        raise SystemExit(
            "KNOWN_ISSUES.md opening must claim the current minor "
            f"({major_minor}.x) is Beta"
        )
    try:
        major_s, minor_s = major_minor.split(".")
        prior_minor = f"{major_s}.{int(minor_s) - 1}" if int(minor_s) > 0 else None
    except ValueError:
        prior_minor = None
    if prior_minor is not None and f"**{prior_minor}.x**" in known_opening:
        raise SystemExit(
            f"KNOWN_ISSUES.md opening still claims prior minor {prior_minor}.x "
            "as the current Beta line"
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
        "Is ETLantic 0.19 production-supported?",
        "0.19 reference envelope",
        "Prefer pages marked **Available in 0.18**",
        "Treat **Available in 0.18**",
        "| Available in 0.18 | Tested against the current package |",
        "match the core minor** (`0.19.0`",
        "pin both to `0.19.0`",
        "reproducible 0.19.0 environment",
        "Gate A shipped in 0.19.0",
        "Available in 0.19.0** for Polars",
        "Public Surface Inventory (0.19)",
        "docs target 0.19.0",
        "0.19.x patches",
        "Core 0.19.x",
        "0.19.0 wheel",
        "Public imports (0.19)",
        "protocols in 0.19.0",
        "In 0.19.0, a relational claim",
        "shipped in ETLantic 0.19.0",
        "0.19 plugins",
        "requires plugins from the **0.20** minor",
        "The CLI defaults to `local`",
        "copy, run, see Ada Lovelace",
        "Quickstart](QUICKSTART.md) (paste)",
        'python -m pip install -e ".[dev]"',
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
        # Stale "current = 0.21" claims after 0.22 ship
        "ETLantic 0.21.0 is production/stable",
        "ETLantic 0.21.0 treats",
        "ETLantic 0.21.0 discovers",
        "Production/stable in ETLantic 0.21.0",
        "docs target 0.21.0",
        "current docs target **0.21.0**",
        "Documented 0.21 public imports",
        "Supported for the 0.21.x line",
        "ETLantic 0.21.0 does not auto-read",
        "Install the wheel into an isolated environment with ETLantic 0.21.0",
        "for 0.21.x pilots, pin all to",
        "`0.21.0` core)",
        "shipped in ETLantic\n0.21.0",
    ]
    major_minor = ".".join(package_version.split(".")[:2])
    try:
        major_s, minor_s = major_minor.split(".")
        prior_minor = f"{major_s}.{int(minor_s) - 1}" if int(minor_s) > 0 else None
    except ValueError:
        prior_minor = None
    if prior_minor is not None:
        prior_patch = f"{prior_minor}.0"
        banned_phrases.extend(
            [
                f"pip install etlantic=={prior_patch}",
                f"ETLantic **{prior_patch}** is **stable**",
                f"Available in ETLantic {prior_patch}",
                f"What is stable in bounded {prior_patch}",
                f"Current stable line is {prior_minor}.x",
                f"{prior_minor}.x is production/stable",
                f"docs target {prior_patch}",
                f"current docs target **{prior_patch}**",
                f"Documented {prior_minor} public imports",
                f"Supported for the {prior_minor}.x line",
                f"pin the published **{prior_patch}**",
                f"Core **{prior_minor}.x** requires",
                f"{prior_patch} wheel",
                f"Public imports ({prior_minor})",
                f"stable in bounded {prior_patch}",
                f"Is ETLantic {prior_minor} production-supported?",
                f"**Available** APIs and behaviors are supported within the documented {prior_minor}",
                f"**{prior_minor}.x** is a **Beta**",
                f"currently {prior_minor}.x",
                f"etlantic=={prior_patch}",
                f"etlantic-polars=={prior_patch}",
                f"etlantic-pandas=={prior_patch}",
                f"etlantic-sql=={prior_patch}",
                f"etlantic-pyspark=={prior_patch}",
            ]
        )
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
        ROOT / "docs/11_DEVELOPMENT/ARCHIVE_INDEX.md"
    ).read_text(encoding="utf-8"):
        raise SystemExit("Archive index missing Migration 0.11 → 0.12")
    if "ARCHIVE_INDEX.md" not in (ROOT / "docs/11_DEVELOPMENT/README.md").read_text(
        encoding="utf-8"
    ):
        raise SystemExit("Development README must link Archive index")
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
    archive_index = (ROOT / "docs/11_DEVELOPMENT/ARCHIVE_INDEX.md").read_text(
        encoding="utf-8"
    )
    if "ARCHIVE_INDEX.md" not in mkdocs_text:
        raise SystemExit("mkdocs.yml missing Archive index nav entry")
    for migration in (
        "MIGRATION_0_11_TO_0_12.md",
        "MIGRATION_0_12_TO_0_13.md",
        "MIGRATION_0_13_TO_0_14.md",
        "MIGRATION_0_14_TO_0_15.md",
        "MIGRATION_0_15_TO_0_16.md",
        "MIGRATION_0_16_TO_0_17.md",
        "MIGRATION_0_17_TO_0_18.md",
        "MIGRATION_0_18_TO_0_19.md",
        "MIGRATION_0_19_TO_0_20.md",
    ):
        if migration not in mkdocs_text and migration not in archive_index:
            raise SystemExit(
                f"mkdocs.yml / Archive index missing {migration} "
                "(nav entry or archive index link required)"
            )
        if migration not in archive_index:
            raise SystemExit(f"Archive index missing {migration}")
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
        "11_DEVELOPMENT/DOCUMENTATION_AUDIT_0_20.md",
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
        or "0.18.0 Gate A — Available" not in capabilities
    ):
        raise SystemExit(
            "CAPABILITIES.md must mark 0.18.0 Gate A interchange Available"
        )
    if "Contract and configuration freeze" not in capabilities:
        raise SystemExit("CAPABILITIES.md must list 0.19 contract/configuration freeze")
    if "Pre-import plugin authorization" not in capabilities:
        raise SystemExit(
            "CAPABILITIES.md must list 0.20 pre-import plugin authorization"
        )
    roadmap_summary = (ROOT / "docs/11_DEVELOPMENT/ROADMAP_SUMMARY.md").read_text(
        encoding="utf-8"
    )
    if "Gate A = **0.18.0**" not in roadmap_summary and "0.18.0" not in roadmap_summary:
        raise SystemExit("ROADMAP_SUMMARY.md must state 0.18.0 Gate A scope")
    if "0.19.0" not in roadmap_summary:
        raise SystemExit("ROADMAP_SUMMARY.md must mention 0.19.0 freeze")
    if "0.20.0" not in roadmap_summary:
        raise SystemExit("ROADMAP_SUMMARY.md must mention 0.20.0 trust/isolation")
    if "0.21.0" not in roadmap_summary and "0.21" not in roadmap_summary:
        raise SystemExit("ROADMAP_SUMMARY.md must mention 0.21")
    if "0.22.0" not in roadmap_summary and "0.22" not in roadmap_summary:
        raise SystemExit("ROADMAP_SUMMARY.md must mention 0.22")
    if "0.23.0" not in roadmap_summary and "0.23" not in roadmap_summary:
        raise SystemExit("ROADMAP_SUMMARY.md must mention 0.23")
    quickstart = (ROOT / "docs/01_GETTING_STARTED/QUICKSTART.md").read_text(
        encoding="utf-8"
    )
    if "etlantic init" not in quickstart:
        raise SystemExit("QUICKSTART.md must document etlantic init")
    if "data/out.json" not in quickstart:
        raise SystemExit(
            "QUICKSTART.md must include success criteria for data/out.json"
        )
    if "examples/quickstart.py" in quickstart:
        raise SystemExit(
            "QUICKSTART.md must not link examples/quickstart.py "
            "(use memory_customers.py or omit)"
        )
    if "non-blocking" not in roadmap_summary.lower():
        raise SystemExit("ROADMAP_SUMMARY.md must label DataFusion as non-blocking")
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
    current_support_rows = [
        line for line in security.splitlines() if f"| {major_minor}.x |" in line
    ]
    if len(current_support_rows) != 1:
        raise SystemExit(
            "SECURITY.md support table must have exactly one "
            f"{major_minor}.x row (found {len(current_support_rows)})"
        )
    if "Not actively maintained" in current_support_rows[0]:
        raise SystemExit(
            f"SECURITY.md {major_minor}.x row must be the current supported line"
        )

    scrub_paths = [
        ROOT / "README.md",
        ROOT / "examples/README.md",
        ROOT / "examples/memory_customers.py",
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
        ROOT / "docs/06_EXECUTION/PRODUCTION_READINESS.md",
        ROOT / "docs/06_EXECUTION/PRODUCTION_PROFILES.md",
        ROOT / "docs/06_EXECUTION/PILOT_WALKTHROUGH.md",
        ROOT / "docs/06_EXECUTION/OPS_PILOT.md",
        ROOT / "docs/05_PIPELINES/PROFILE_PRIMER.md",
        ROOT / "docs/04_TRANSFORMATIONS/PORTABLE_TRANSFORMATIONS.md",
        ROOT / "docs/07_PLUGIN_SDK/PORTABLE_TRANSFORM_COMPILER.md",
        ROOT / "docs/07_PLUGIN_SDK/THIRD_PARTY_COMPILER_TUTORIAL.md",
        ROOT / "docs/10_REFERENCE/PORTABLE_COMPILER_MATRIX.md",
        ROOT / "docs/10_REFERENCE/OPTIONAL_PACKAGES.md",
        ROOT / "docs/10_REFERENCE/CONFIGURATION_TODAY.md",
        ROOT / "docs/11_DEVELOPMENT/DEPRECATION_POLICY.md",
        ROOT / "docs/11_DEVELOPMENT/RELEASE_PROCESS.md",
        ROOT / "docs/02_FOUNDATIONS/SECURITY.md",
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
    if "pip install etlantic" not in readme and "pip install 'etlantic" not in readme:
        raise SystemExit("README.md missing pip-first install guidance")
    if (
        "etlantic --version" not in readme
        and "python -m etlantic --version" not in readme
    ):
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
    if "/08_VISUALIZATION/APPLICATION_INTEGRATION/" not in banner_js:
        raise SystemExit(
            "status-banner.js must exclude APPLICATION_INTEGRATION from future viz banner"
        )

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
        ROOT / "packages/etlantic-datafusion/pyproject.toml",
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
        ROOT / "packages/etlantic-fastapi/src/etlantic_fastapi/__init__.py",
        ROOT / "packages/etlantic-sparkforge/src/etlantic_sparkforge/__init__.py",
        ROOT / "packages/etlantic-keyring/src/etlantic_keyring/__init__.py",
        ROOT / "packages/etlantic-sqlmodel/src/etlantic_sqlmodel/__init__.py",
        ROOT / "packages/etlantic-datafusion/src/etlantic_datafusion/__init__.py",
        ROOT / "packages/etlantic-datafusion/src/etlantic_datafusion/plugin.py",
        ROOT / "packages/etlantic-datafusion/src/etlantic_datafusion/compiler.py",
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

    # Impossible version ranges: >=X.Y…,<X.Y (empty set).
    # Skip historical audit/migration pages that may quote past mistakes.
    impossible_pin = re.compile(
        r">=\s*(\d+\.\d+(?:\.\d+)?)\s*,\s*<\s*(\d+\.\d+(?:\.\d+)?)"
    )
    impossible_skip = re.compile(
        r"(WHATS_NEW_|MIGRATION_|EXIT_GATE_|DOCUMENTATION_AUDIT_|CHANGELOG|ROADMAP)"
    )

    def _major_minor(ver: str) -> str:
        parts = ver.split(".")
        return f"{parts[0]}.{parts[1]}"

    for path in ROOT.rglob("*"):
        if path.suffix not in {".md", ".py", ".toml", ".yml", ".yaml", ".json"}:
            continue
        if any(
            part in {"node_modules", ".venv", "site", ".git"} for part in path.parts
        ):
            continue
        if impossible_skip.search(str(path)):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for match in impossible_pin.finditer(text):
            lower, upper = match.group(1), match.group(2)
            if _major_minor(lower) == _major_minor(upper):
                raise SystemExit(f"{path}: impossible version range {match.group(0)!r}")

    if prior_minor is not None:
        for path in (
            ROOT / "docs/01_GETTING_STARTED/README.md",
            ROOT / "docs/01_GETTING_STARTED/CAPABILITIES.md",
            ROOT / "docs/01_GETTING_STARTED/EVALUATOR.md",
            ROOT / "docs/02_FOUNDATIONS/DOCUMENTATION_STATUS.md",
            ROOT / "docs/10_REFERENCE/README.md",
            ROOT / "docs/10_REFERENCE/KNOWN_ISSUES.md",
            ROOT / "docs/11_DEVELOPMENT/SUPPORT.md",
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
        ROOT / "examples/README.md",
        ROOT / "examples/interchange_polars_pandas.py",
        ROOT / "profiles/prod.example.json",
        ROOT / "docs/01_GETTING_STARTED/prod.example.json",
        ROOT / "docs/01_GETTING_STARTED/ENGINE_SELECTION.md",
        ROOT / "docs/01_GETTING_STARTED/BEST_PRACTICES.md",
        ROOT / "docs/01_GETTING_STARTED/COMPARE.md",
        ROOT / "docs/01_GETTING_STARTED/COOKBOOK.md",
        ROOT / "docs/01_GETTING_STARTED/OPS_EXAMPLES.md",
        ROOT / "docs/01_GETTING_STARTED/PORTABLE_VS_NATIVE.md",
        ROOT / "docs/01_GETTING_STARTED/PORTABLE_FAILURE_COOKBOOK.md",
        ROOT / "docs/01_GETTING_STARTED/INTERCHANGE_GATE_A_FAQ.md",
        ROOT / "docs/05_PIPELINES/PROFILE_PRIMER.md",
        ROOT / "docs/10_REFERENCE/KNOWN_ISSUES.md",
        ROOT / "docs/10_REFERENCE/CONFIGURATION_TODAY.md",
        ROOT / "docs/10_REFERENCE/RUNTIME_CONFIGURATION.md",
        ROOT / "docs/10_REFERENCE/EXCEPTIONS.md",
        ROOT / "docs/10_REFERENCE/API_PLAN_RUNTIME.md",
        ROOT / "docs/11_DEVELOPMENT/SUPPORT.md",
        ROOT / "docs/11_DEVELOPMENT/PERFORMANCE.md",
        ROOT / "docs/01_GETTING_STARTED/INSTALLATION.md",
        ROOT / "docs/01_GETTING_STARTED/QUICKSTART.md",
        ROOT / "docs/01_GETTING_STARTED/TROUBLESHOOTING.md",
        ROOT / "docs/02_FOUNDATIONS/SECURITY.md",
        ROOT / "docs/04_TRANSFORMATIONS/CALLBACKS.md",
        ROOT / "docs/04_TRANSFORMATIONS/ERROR_HANDLING.md",
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
        ROOT / "docs/06_EXECUTION/STORAGE_TODAY.md",
        ROOT / "docs/06_EXECUTION/OBSERVABILITY_TODAY.md",
        ROOT / "docs/06_EXECUTION/CI_INTEGRATION.md",
        ROOT / "docs/06_EXECUTION/DEPLOYMENT.md",
        ROOT / "docs/06_EXECUTION/RUN_REPORTS.md",
        ROOT / "docs/07_PLUGIN_SDK/THIRD_PARTY_COMPILER_TUTORIAL.md",
        ROOT / "docs/07_PLUGIN_SDK/BUILDING_A_PLUGIN.md",
        ROOT / "docs/07_PLUGIN_SDK/TESTING_PLUGINS.md",
        ROOT / "docs/07_PLUGIN_SDK/OVERVIEW.md",
        ROOT / "docs/07_PLUGIN_SDK/DATAFRAME_PLUGIN.md",
        ROOT / "docs/09_EXAMPLES/PORTABLE_TRANSFORMS.md",
        ROOT / "docs/09_EXAMPLES/PREFECT_RUN.md",
        ROOT / "docs/09_EXAMPLES/INTERCHANGE_POLARS_PANDAS.md",
        ROOT / "docs/09_EXAMPLES/SAMPLE_PROJECT.md",
        ROOT / "docs/09_EXAMPLES/CONTRACT_FIRST_TUTORIAL.md",
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
        prior_status = f"Available in ETLantic {prior_minor}.0"
        prior_status_short = f"Available in ETLantic {prior_minor}"
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
            if f"=={prior_minor}.0" in text and "plugin_allowlist" in text.lower():
                raise SystemExit(f"{path} still allowlists plugins at {prior_minor}.0")
            if prior_status in text or (
                prior_status_short in text and f"{prior_minor}.0" in text
            ):
                raise SystemExit(
                    f"{path} still presents {prior_minor} as available/current"
                )
            if f"Configuration in {prior_minor}.0" in text:
                raise SystemExit(
                    f"{path} still titles Configuration in {prior_minor}.0"
                )
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
    plugin_stable_classifier = "Development Status :: 5 - Production/Stable"
    root_beta_classifier = "Development Status :: 4 - Beta"
    alpha_classifier = "Development Status :: 3 - Alpha"
    next_minor = None
    try:
        maj_s, min_s = major_minor.split(".")
        next_minor = f"{maj_s}.{int(min_s) + 1}"
    except ValueError:
        next_minor = None
    experimental_packages = {"etlantic-datafusion"}
    reference_packages = {"etlantic-fastapi"}
    root_pyproject_path = ROOT / "pyproject.toml"
    root_text = root_pyproject_path.read_text(encoding="utf-8")
    if root_beta_classifier not in root_text:
        raise SystemExit(f"{root_pyproject_path} missing Beta classifier")
    if plugin_stable_classifier in root_text:
        raise SystemExit(
            f"{root_pyproject_path} should use Beta, not Production/Stable"
        )
    for path in (*(ROOT / "packages").glob("etlantic-*/pyproject.toml"),):
        text = path.read_text(encoding="utf-8")
        pkg_name = path.parent.name
        if pkg_name in experimental_packages:
            if alpha_classifier not in text:
                raise SystemExit(f"{path} experimental package should use Alpha")
            if next_minor is not None:
                expected_alt = f"etlantic>={major_minor}.0,<{next_minor}"
                if expected_alt not in text:
                    raise SystemExit(
                        f"{path} must depend on {expected_alt} (found mismatched core range)"
                    )
            continue
        if pkg_name in reference_packages:
            if root_beta_classifier not in text:
                raise SystemExit(f"{path} reference package should use Beta")
            if plugin_stable_classifier in text:
                raise SystemExit(
                    f"{path} reference package should use Beta, not Production/Stable"
                )
            if next_minor is not None:
                expected_alt = f"etlantic>={major_minor}.0,<{next_minor}"
                if expected_alt not in text:
                    raise SystemExit(
                        f"{path} must depend on {expected_alt} (found mismatched core range)"
                    )
            continue
        if alpha_classifier in text:
            raise SystemExit(f"{path} still uses Alpha classifier")
        if plugin_stable_classifier not in text:
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

    # Adopter-facing pages must use current milestone vocabulary.
    major_minor = ".".join(package_version.split(".")[:2])
    doc_status = (ROOT / "docs/02_FOUNDATIONS/DOCUMENTATION_STATUS.md").read_text(
        encoding="utf-8"
    )
    if f"Available in {major_minor}" not in doc_status:
        raise SystemExit(
            f"DOCUMENTATION_STATUS.md must reference Available in {major_minor}"
        )
    surface_inventory = (ROOT / "docs/10_REFERENCE/SURFACE_INVENTORY.md").read_text(
        encoding="utf-8"
    )
    if f"{major_minor} reference envelope" not in surface_inventory:
        raise SystemExit(
            f"SURFACE_INVENTORY.md must reference {major_minor} reference envelope"
        )
    upgrade_hub = (ROOT / "docs/01_GETTING_STARTED/UPGRADE.md").read_text(
        encoding="utf-8"
    )
    prev_major, prev_minor = major_minor.split(".")
    prev_minor_int = int(prev_minor)
    if prev_minor_int > 0:
        prior_migration = (
            f"MIGRATION_{prev_major}_{prev_minor_int - 1}_TO_"
            f"{prev_major}_{prev_minor_int}"
        )
    else:
        prior_migration = f"MIGRATION_{int(prev_major) - 1}_9_TO_{prev_major}_0"
    if (
        prior_migration not in upgrade_hub
        and "MIGRATION_0_19_TO_0_20" not in upgrade_hub
    ):
        raise SystemExit(f"UPGRADE.md must link prior migration ({prior_migration})")
    if f"{major_minor} configuration cheat sheet" not in upgrade_hub.lower():
        raise SystemExit(
            f"UPGRADE.md must include {major_minor} configuration cheat sheet"
        )

    surface_inventory_json = ROOT / "src/etlantic/schemas/surface-inventory.json"
    inventory = json.loads(surface_inventory_json.read_text(encoding="utf-8"))
    if inventory.get("version") != package_version:
        raise SystemExit(
            f"surface-inventory.json version {inventory.get('version')!r} "
            f"!= package {package_version}"
        )
    cli_flags_stable = inventory.get("cli_flags_stable", [])
    if "--accept-legacy-bindings" not in cli_flags_stable:
        raise SystemExit(
            "surface-inventory.json cli_flags_stable must include "
            "--accept-legacy-bindings"
        )

    # CLI.md must document every public CLI command (contract vs Typer surface).
    sys.path.insert(0, str(ROOT / "src"))
    from etlantic.agents import PUBLIC_CLI_COMMANDS

    cli_md = (ROOT / "docs/10_REFERENCE/CLI.md").read_text(encoding="utf-8")
    for cmd in PUBLIC_CLI_COMMANDS:
        heading = f"## `{cmd}`"
        if heading not in cli_md:
            raise SystemExit(f"CLI.md missing section for public command: {heading}")

    # Current-patch install pins must match package_version on green-path pages.
    pin = f"=={package_version}"
    parts = package_version.split(".")
    prior_minor = (
        f"{parts[0]}.{int(parts[1]) - 1}.0"
        if len(parts) >= 2 and parts[1].isdigit() and int(parts[1]) > 0
        else None
    )
    green_path_docs = [
        ROOT / "docs/01_GETTING_STARTED/INSTALLATION.md",
        ROOT / "docs/01_GETTING_STARTED/QUICKSTART.md",
        ROOT / "docs/01_GETTING_STARTED/LEARNING_PATH.md",
        ROOT / "docs/01_GETTING_STARTED/FIRST_PIPELINE.md",
        ROOT / "docs/01_GETTING_STARTED/prod.example.json",
        ROOT / "docs/10_REFERENCE/CONFIGURATION_TODAY.md",
        ROOT / "docs/10_REFERENCE/COMPATIBILITY.md",
        ROOT / "README.md",
    ]
    for path in green_path_docs:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if prior_minor and prior_minor in text and package_version != prior_minor:
            # Allow historical ranges like >=0.25.0,<0.26 and dedicated migration pages.
            hard_pin = f"=={prior_minor}"
            version_example = f'etlantic.version = "{prior_minor}"'
            prints_prior = f"prints `{prior_minor}`"
            if (
                hard_pin in text
                and pin not in text
                and f"etlantic=={package_version}" not in text
            ):
                raise SystemExit(
                    f"{path} still pins {hard_pin}; expected {pin} for current release"
                )
            if version_example in text:
                raise SystemExit(
                    f"{path} still shows {version_example}; expected "
                    f'etlantic.version = "{package_version}"'
                )
            if prints_prior in text:
                raise SystemExit(
                    f"{path} still says prints `{prior_minor}`; expected "
                    f"`{package_version}`"
                )
            # COMPATIBILITY / narrative "for 0.25.0" without current version nearby
            if (
                f"for {prior_minor}" in text
                and package_version not in text
                and f"0.{parts[1]}" not in path.name
            ):
                raise SystemExit(
                    f"{path} still references tested surface for {prior_minor}; "
                    f"retarget to {package_version}"
                )
        if (
            path.suffix == ".json"
            and pin not in text
            and f'"{package_version}"' not in text
            and prior_minor
            and f"=={prior_minor}" in text
        ):
            raise SystemExit(f"{path} allowlist pins must use {pin}")

    exceptions_md = (ROOT / "docs/10_REFERENCE/EXCEPTIONS.md").read_text(
        encoding="utf-8"
    )
    if (
        "still work pre-1.0" in exceptions_md
        or "exception aliases still work" in exceptions_md
    ):
        raise SystemExit(
            "EXCEPTIONS.md must not claim removed root exception aliases still work; "
            "see Migration 0.25→0.26"
        )

    subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_runnable_docs.py")],
        check=True,
    )

    # Production trust examples must set security_mode, not only security_domain.
    # Fail-closed plugin trust is gated by security_mode == "production".
    domain_only = re.compile(
        r'security_domain\s*=\s*["\']production["\']'
        r'|["\']security_domain["\']\s*:\s*["\']production["\']'
    )
    mode_present = re.compile(
        r'security_mode\s*=\s*["\']production["\']'
        r'|["\']security_mode["\']\s*:\s*["\']production["\']'
    )
    bare_profile_production = re.compile(
        r"(?:python\s+-m\s+)?etlantic\s+\w+[^\n]*--profile\s+production\b"
    )
    trust_scan_roots = [
        ROOT / "docs/01_GETTING_STARTED",
        ROOT / "docs/02_FOUNDATIONS",
        ROOT / "docs/05_PIPELINES",
        ROOT / "docs/06_EXECUTION",
        ROOT / "docs/07_PLUGIN_SDK",
    ]
    for root in trust_scan_roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            # Skip pages that only document the built-in empty template failure.
            for match in domain_only.finditer(text):
                start = max(0, match.start() - 400)
                end = min(len(text), match.end() + 400)
                window = text[start:end]
                if not mode_present.search(window):
                    raise SystemExit(
                        f'{path}: security_domain="production" without nearby '
                        'security_mode="production" (fail-closed trust requires '
                        "security_mode)"
                    )
            # Day-2 howtos must not recommend bare --profile production as a
            # working CI command (empty allowlist fail-closed).
            if path.name in {
                "SECURITY_HOWTO.md",
                "BEST_PRACTICES.md",
                "OPS_EXAMPLES.md",
                "COOKBOOK.md",
                "PRODUCTION_PROFILES.md",
            }:
                for cmd in bare_profile_production.finditer(text):
                    line_start = text.rfind("\n", 0, cmd.start()) + 1
                    line_end = text.find("\n", cmd.start())
                    line = text[line_start : line_end if line_end >= 0 else None]
                    if "fail" in line.lower() or "empty" in line.lower():
                        continue
                    preceding = text[max(0, cmd.start() - 200) : cmd.start()].lower()
                    if (
                        "do not" in preceding
                        or "not use" in preceding
                        or "expected to fail" in preceding
                        or "expected to fail"
                        in text[max(0, line_start - 400) : line_start].lower()
                    ):
                        continue
                    raise SystemExit(
                        f"{path}: avoid recommending bare --profile production; "
                        "use an allowlisted profile file with security_mode"
                    )

    # Curated stable-surface docstring gate (Pipeline, Profile, authoring, service).
    # To gate a new stable surface:
    # 1. Import the class/function above.
    # 2. Add methods to `curated` (or symbols to `curated_functions`).
    # 3. If the API fails closed / raises on bad input, add to
    #    `require_raises` or `function_require_raises`.
    # Docstrings must include Returns:; Args: when there are non-self params;
    # Raises: when listed in the require sets.
    import inspect

    def _doc_has_sections(
        doc: str | None, *, need_args: bool, need_raises: bool
    ) -> list[str]:
        missing: list[str] = []
        body = doc or ""
        if need_args and "Args:" not in body and "Arguments:" not in body:
            missing.append("Args")
        if "Returns:" not in body and "Return:" not in body:
            missing.append("Returns")
        if need_raises and "Raises:" not in body:
            missing.append("Raises")
        return missing

    def _has_non_self_params(fn: object) -> bool:
        try:
            params = list(inspect.signature(fn).parameters.values())
        except (TypeError, ValueError):
            return True
        interesting = (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
            inspect.Parameter.VAR_POSITIONAL,
        )
        return any(
            p.name not in {"self", "cls"} and p.kind in interesting for p in params
        )

    sys.path.insert(0, str(ROOT / "src"))
    from etlantic.authoring.builders import pipeline_definition
    from etlantic.authoring.definition import PipelineDefinition
    from etlantic.authoring.edits import EditCommand, apply_edit
    from etlantic.authoring.serialize import (
        pipeline_fingerprint,
        pipeline_from_dict,
        pipeline_to_dict,
        read_pipeline_json,
        write_pipeline_json,
    )
    from etlantic.orchestration import compile_plan
    from etlantic.pipeline import Pipeline
    from etlantic.plan.explain import explain_plan
    from etlantic.plan.freeze import deep_freeze
    from etlantic.plan.planner import plan_pipeline
    from etlantic.plan.serialize import verify_plan_fingerprint
    from etlantic.profile import Profile
    from etlantic.service import AuthoringService

    curated = {
        Pipeline: (
            "validate",
            "plan",
            "explain_plan",
            "run",
            "arun",
            "inspect",
            "to_dpcs",
            "from_dpcs",
        ),
        Profile: (
            "to_dict",
            "from_dict",
            "with_updates",
            "to_plan_snapshot",
            "from_plan_snapshot",
        ),
        PipelineDefinition: (
            "to_dict",
            "from_dict",
            "with_fingerprint",
        ),
        EditCommand: ("to_dict", "from_dict"),
        AuthoringService: (
            "negotiation",
            "catalog",
            "put_definition",
            "get_definition",
            "apply_edit",
            "validate",
            "plan",
            "submit_run",
            "cancel_run",
            "job_status",
        ),
    }
    require_raises = {
        (Pipeline, "validate"),
        (Pipeline, "plan"),
        (Pipeline, "explain_plan"),
        (Pipeline, "run"),
        (Pipeline, "arun"),
        (Pipeline, "from_dpcs"),
        (Profile, "from_dict"),
        (Profile, "from_plan_snapshot"),
        (PipelineDefinition, "from_dict"),
        (EditCommand, "from_dict"),
        (AuthoringService, "negotiation"),
        (AuthoringService, "catalog"),
        (AuthoringService, "put_definition"),
        (AuthoringService, "get_definition"),
        (AuthoringService, "apply_edit"),
        (AuthoringService, "validate"),
        (AuthoringService, "plan"),
        (AuthoringService, "submit_run"),
        (AuthoringService, "cancel_run"),
        (AuthoringService, "job_status"),
    }
    curated_functions = {
        "etlantic.authoring.pipeline_definition": pipeline_definition,
        "etlantic.authoring.apply_edit": apply_edit,
        "etlantic.authoring.pipeline_fingerprint": pipeline_fingerprint,
        "etlantic.authoring.pipeline_to_dict": pipeline_to_dict,
        "etlantic.authoring.pipeline_from_dict": pipeline_from_dict,
        "etlantic.authoring.write_pipeline_json": write_pipeline_json,
        "etlantic.authoring.read_pipeline_json": read_pipeline_json,
        "etlantic.plan.deep_freeze": deep_freeze,
        "etlantic.plan.verify_plan_fingerprint": verify_plan_fingerprint,
        "etlantic.plan.plan_pipeline": plan_pipeline,
        "etlantic.plan.explain_plan": explain_plan,
        "etlantic.orchestration.compile_plan": compile_plan,
    }
    function_require_raises = {
        "etlantic.authoring.apply_edit",
        "etlantic.authoring.pipeline_from_dict",
        "etlantic.authoring.read_pipeline_json",
        "etlantic.authoring.pipeline_definition",
        "etlantic.plan.verify_plan_fingerprint",
        "etlantic.plan.plan_pipeline",
        "etlantic.orchestration.compile_plan",
    }
    failures: list[str] = []
    for cls, names in curated.items():
        for name in names:
            fn = getattr(cls, name)
            missing = _doc_has_sections(
                inspect.getdoc(fn),
                need_args=_has_non_self_params(fn),
                need_raises=(cls, name) in require_raises,
            )
            if missing:
                failures.append(
                    f"{cls.__name__}.{name} missing docstring sections: "
                    + ", ".join(missing)
                )
    for qualname, fn in curated_functions.items():
        missing = _doc_has_sections(
            inspect.getdoc(fn),
            need_args=_has_non_self_params(fn),
            need_raises=qualname in function_require_raises,
        )
        if missing:
            failures.append(
                f"{qualname} missing docstring sections: " + ", ".join(missing)
            )
    if failures:
        raise SystemExit(
            "Stable-surface docstring gate failed:\n- " + "\n- ".join(failures)
        )

    print(f"Documentation consistency checks passed for {package_version}.")


if __name__ == "__main__":
    main()
