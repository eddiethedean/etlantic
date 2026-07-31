"""Small dependency-free documentation consistency checks."""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import textwrap
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).parents[1]
MARKDOWN_LINK_RE = re.compile(
    r"!?\[[^\]\n]*\]\(\s*(<[^>\n]+>|[^)\s]+)"
    r"(?:\s+[\"'][^)\n]*[\"'])?\s*\)"
)
MARKDOWN_REFERENCE_RE = re.compile(r"(?m)^\s{0,3}\[[^\]\n]+\]:\s*(<[^>\n]+>|[^\s]+)")
PYTHON_FENCE_RE = re.compile(r"```(?:python|py)\s*\n(.*?)```", re.DOTALL)
INLINE_MARKDOWN_LINK_RE = re.compile(
    r"!?\[[^\]\n]*\]\([^)\n]*\)|\[[^\]\n]*\]\[[^\]\n]*\]"
)
STANDARD_PAGES = {
    "ODCS": ROOT / "docs/03_DATA_CONTRACTS/ODCS.md",
    "DTCS": ROOT / "docs/04_TRANSFORMATIONS/DTCS.md",
    "DPCS": ROOT / "docs/05_PIPELINES/DPCS.md",
}
STANDARD_URLS = {
    acronym: (
        "https://etlantic.readthedocs.io/en/v0.39.0/"
        f"{page.relative_to(ROOT / 'docs').with_suffix('')}/"
    )
    for acronym, page in STANDARD_PAGES.items()
}
STANDARD_URLS_ALIASES = {
    acronym: {
        STANDARD_URLS[acronym],
        (
            "https://etlantic.readthedocs.io/en/latest/"
            f"{page.relative_to(ROOT / 'docs').with_suffix('')}/"
        ),
        (
            "https://etlantic.readthedocs.io/en/stable/"
            f"{page.relative_to(ROOT / 'docs').with_suffix('')}/"
        ),
    }
    for acronym, page in STANDARD_PAGES.items()
}


def load_release_facts() -> dict:
    """Load machine-readable release facts (single source of truth)."""
    path = ROOT / "docs" / "release-facts.json"
    if not path.is_file():
        raise SystemExit(f"Missing {path.relative_to(ROOT)}")
    data = json.loads(path.read_text(encoding="utf-8"))
    required = (
        "current_version",
        "current_minor",
        "previous_minor",
        "next_minor",
        "whats_new",
        "migration",
        "exit_gate",
        "docs_version_slug",
        "docs_base_url",
        "maturity",
    )
    missing = [k for k in required if k not in data]
    if missing:
        raise SystemExit(f"release-facts.json missing keys: {missing}")
    return data


def versioned_readthedocs_url(page: Path, *, docs_base_url: str) -> str:
    """Return immutable RTD URL for a docs page under the release slug."""
    base = docs_base_url.rstrip("/") + "/"
    relative = page.relative_to(ROOT / "docs")
    if relative == Path("README.md"):
        return base
    route = relative.with_suffix("").as_posix()
    if route.endswith("/README"):
        route = route.removesuffix("/README")
    return f"{base}{route}/"


def readthedocs_url(page: Path) -> str:
    """Return the canonical public URL for a Markdown page under ``docs/``."""
    relative = page.relative_to(ROOT / "docs")
    if relative == Path("README.md"):
        return "https://etlantic.readthedocs.io/en/latest/"
    route = relative.with_suffix("").as_posix()
    if route.endswith("/README"):
        route = route.removesuffix("/README")
    return f"https://etlantic.readthedocs.io/en/latest/{route}/"


def version_from(path: Path, pattern: str) -> str:
    match = re.search(pattern, path.read_text(encoding="utf-8"))
    if match is None:
        raise SystemExit(f"Could not find version in {path}")
    return match.group(1)


def markdown_without_code(text: str) -> str:
    """Remove fenced and inline code before inspecting Markdown links."""
    visible: list[str] = []
    fence_char: str | None = None
    fence_length = 0
    for line in text.splitlines():
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match is not None:
            marker = match.group(1)
            if fence_char is None:
                fence_char = marker[0]
                fence_length = len(marker)
            elif marker[0] == fence_char and len(marker) >= fence_length:
                fence_char = None
                fence_length = 0
            visible.append("")
            continue
        visible.append(line if fence_char is None else "")
    return re.sub(r"(?<!`)`[^`\n]+`(?!`)", "", "\n".join(visible))


def check_nav_page_status_markers() -> None:
    """Require status frontmatter or banner on primary-nav product pages."""
    mkdocs = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    nav_paths: list[str] = []
    for match in re.finditer(r"(?m)^\s+-\s+[^:]+:\s+(\S+\.md)\s*$", mkdocs):
        nav_paths.append(match.group(1))
    missing: list[str] = []
    for rel in sorted(set(nav_paths)):
        if rel.startswith("11_DEVELOPMENT/") and any(
            token in rel
            for token in (
                "_PLAN",
                "EXIT_GATE_",
                "MIGRATION_",
                "ROADMAP",
                "DOCUMENTATION_AUDIT",
                "ARCHITECTURE_DECISIONS",
            )
        ):
            continue
        path = ROOT / "docs" / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        head = "\n".join(text.splitlines()[:40])
        has_frontmatter_status = bool(re.search(r"(?ms)^---\n.*?^status:\s*\S+", text))
        has_banner = (
            "Status:" in head or "**Status:" in head or "status:" in head.lower()
        )
        if not has_frontmatter_status and not has_banner:
            missing.append(rel)
    if missing:
        raise SystemExit(
            "Nav product pages missing status frontmatter or Status banner "
            "(first 40 lines):\n- " + "\n- ".join(missing[:40])
        )


def check_not_in_nav_orphans() -> None:
    """Every not_in_nav page outside archives must have an inbound docs link."""
    mkdocs = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    nin_match = re.search(r"(?ms)^not_in_nav:\s*\|\s*\n(.*?)(?=^\S|\Z)", mkdocs)
    if nin_match is None:
        return
    not_in_nav = {
        line.strip()
        for line in nin_match.group(1).splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    archive_prefixes = (
        "01_GETTING_STARTED/WHATS_NEW_0_",
        "11_DEVELOPMENT/DOCUMENTATION_AUDIT_0_",
        "11_DEVELOPMENT/EXIT_GATE_0_",
        "11_DEVELOPMENT/MIGRATION_0_",
        "01_GETTING_STARTED/EARLIER_RELEASES.md",
        "03_DATA_CONTRACTS/DATACONTRACTMODEL.md",
    )
    # Build inbound link set from docs markdown.
    inbound: set[str] = set()
    for path in (ROOT / "docs").rglob("*.md"):
        if "theme" in path.parts:
            continue
        visible = markdown_without_code(path.read_text(encoding="utf-8"))
        for match in MARKDOWN_LINK_RE.finditer(visible):
            target = match.group(1).strip()
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1]
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            href = target.split("#", 1)[0].split("?", 1)[0]
            if not href.endswith(".md"):
                continue
            dest = (path.parent / href).resolve()
            try:
                rel = dest.relative_to((ROOT / "docs").resolve()).as_posix()
            except ValueError:
                continue
            inbound.add(rel)
    orphans: list[str] = []
    for rel in sorted(not_in_nav):
        if any(rel.startswith(prefix) or rel == prefix for prefix in archive_prefixes):
            continue
        if rel in inbound:
            continue
        orphans.append(rel)
    if orphans:
        raise SystemExit(
            "not_in_nav pages lack inbound docs links (add hub link or archive):\n- "
            + "\n- ".join(orphans[:40])
        )


def check_docs_ban_absolute_rtd_latest() -> None:
    """Prefer relative Markdown links inside docs/; ban absolute RTD /en/latest/."""
    banned = "https://etlantic.readthedocs.io/en/latest/"
    docs_root = ROOT / "docs"
    for path in sorted(docs_root.rglob("*.md")):
        if "theme" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if banned in text:
            raise SystemExit(
                f"{path.relative_to(ROOT)}: ban absolute Read the Docs "
                f"{banned!r} — use relative .md links under docs/"
            )


def check_local_markdown_links() -> None:
    """Fail on relative Markdown links whose repository target is missing."""
    root_resolved = ROOT.resolve()
    ignored_parts = {".git", ".venv", "node_modules", "site"}
    for path in ROOT.rglob("*.md"):
        if any(part in ignored_parts for part in path.parts):
            continue
        visible = markdown_without_code(path.read_text(encoding="utf-8"))
        matches = list(MARKDOWN_LINK_RE.finditer(visible))
        matches.extend(MARKDOWN_REFERENCE_RE.finditer(visible))
        for match in matches:
            raw_target = match.group(1).strip()
            if raw_target.startswith("<") and raw_target.endswith(">"):
                raw_target = raw_target[1:-1]
            target = unquote(raw_target).split("#", 1)[0].split("?", 1)[0]
            if (
                not target
                or target.startswith(("#", "/", "{{"))
                or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target)
            ):
                continue
            resolved = (path.parent / target).resolve()
            try:
                resolved.relative_to(root_resolved)
            except ValueError as err:
                raise SystemExit(
                    f"{path}: relative Markdown link leaves repository: {raw_target!r}"
                ) from err
            if not resolved.exists():
                raise SystemExit(
                    f"{path}: local Markdown link target does not exist: {raw_target!r}"
                )


def check_python_code_fences() -> None:
    """Require every Python-labelled Markdown fence to be valid Python syntax."""
    ignored_parts = {".git", ".venv", "node_modules", "site"}
    for path in ROOT.rglob("*.md"):
        if any(part in ignored_parts for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        for match in PYTHON_FENCE_RE.finditer(text):
            code = textwrap.dedent(match.group(1))
            try:
                ast.parse(code, filename=str(path))
            except SyntaxError as exc:
                markdown_line = text.count("\n", 0, match.start()) + (exc.lineno or 1)
                raise SystemExit(
                    f"{path}:{markdown_line}: invalid Python documentation "
                    f"example: {exc.msg}"
                ) from exc


def check_standard_links() -> None:
    """Keep contract-standard mentions connected to their canonical guides."""
    docs_root = ROOT / "docs"
    standard_docs = set(docs_root.rglob("*.md"))
    standard_docs.update(
        {
            ROOT / "README.md",
            ROOT / "ROADMAP.md",
            ROOT / "CHANGELOG.md",
        }
    )
    for path in sorted(standard_docs):
        text = path.read_text(encoding="utf-8")
        visible = markdown_without_code(text)
        for acronym, canonical in STANDARD_PAGES.items():
            if path == canonical or re.search(rf"\b{acronym}\b", visible) is None:
                continue

            linked_to_canonical = False
            for match in MARKDOWN_LINK_RE.finditer(visible):
                raw_target = match.group(1).strip()
                if raw_target.startswith("<") and raw_target.endswith(">"):
                    raw_target = raw_target[1:-1]
                target = unquote(raw_target).split("#", 1)[0].split("?", 1)[0]
                if target in STANDARD_URLS_ALIASES[acronym]:
                    linked_to_canonical = True
                    break
                if not target or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                    continue
                if (path.parent / target).resolve() == canonical.resolve():
                    linked_to_canonical = True
                    break
            if not linked_to_canonical:
                raise SystemExit(
                    f"{path}: mentions {acronym} without linking its canonical "
                    f"guide {canonical.relative_to(ROOT)}"
                )

            fence_char: str | None = None
            fence_length = 0
            first_mention_linked: bool | None = None
            for line in text.splitlines():
                fence = re.match(r"^\s*(`{3,}|~{3,})", line)
                if fence is not None:
                    marker = fence.group(1)
                    if fence_char is None:
                        fence_char = marker[0]
                        fence_length = len(marker)
                    elif marker[0] == fence_char and len(marker) >= fence_length:
                        fence_char = None
                        fence_length = 0
                    continue
                if (
                    fence_char is not None
                    or line.lstrip().startswith("#")
                    or MARKDOWN_REFERENCE_RE.match(line)
                ):
                    continue

                code_spans = [
                    match.span() for match in re.finditer(r"(?<!`)`[^`\n]+`(?!`)", line)
                ]
                link_spans = [
                    match.span() for match in INLINE_MARKDOWN_LINK_RE.finditer(line)
                ]
                for mention in re.finditer(rf"\b{acronym}\b", line):
                    if any(start <= mention.start() < end for start, end in code_spans):
                        continue
                    first_mention_linked = any(
                        start <= mention.start() < end for start, end in link_spans
                    )
                    break
                if first_mention_linked is not None:
                    break

            if first_mention_linked is False:
                raise SystemExit(
                    f"{path}: first prose mention of {acronym} must be a Markdown link"
                )


def check_control_plane_plan() -> None:
    """Keep the first-class control-plane program explicit and fail-closed."""
    plan = ROOT / "docs/11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN.md"
    if not plan.exists():
        raise SystemExit("Missing first-class multi-tenant control-plane plan")

    text = plan.read_text(encoding="utf-8")
    required_plan_markers = (
        "Status: planned first-class feature program",
        "0.39 / CP1",
        "0.40 / CP2",
        "0.41 / CP3",
        "0.42 / CP4",
        "0.43 / CP-GA",
        "deny by default",
        "transactional outbox",
        "leases and fencing tokens",
        "free of source rows and resolved secret values",
        "RPO",
        "RTO",
        "Failure of any mandatory gate keeps the feature",
    )
    for marker in required_plan_markers:
        if marker not in text:
            raise SystemExit(
                f"{plan}: control-plane hardening marker is missing: {marker!r}"
            )

    linked_surfaces = (
        ROOT / "README.md",
        ROOT / "ROADMAP.md",
        ROOT / "docs/README.md",
        ROOT / "docs/01_GETTING_STARTED/CAPABILITIES.md",
        ROOT / "docs/01_GETTING_STARTED/EVALUATOR.md",
        ROOT / "docs/02_FOUNDATIONS/SECURITY.md",
        ROOT / "docs/06_EXECUTION/DEPLOYMENT.md",
        ROOT / "docs/06_EXECUTION/PRODUCTION_READINESS.md",
        ROOT / "docs/11_DEVELOPMENT/FASTAPI_INTEGRATION_PLAN.md",
        ROOT / "docs/11_DEVELOPMENT/SQLMODEL_INTEGRATION_PLAN.md",
        ROOT / "docs/11_DEVELOPMENT/ROADMAP_SUMMARY.md",
    )
    plan_rel = plan.relative_to(ROOT / "docs").with_suffix("").as_posix()
    plan_urls = {
        f"https://etlantic.readthedocs.io/en/latest/{plan_rel}/",
        f"https://etlantic.readthedocs.io/en/stable/{plan_rel}/",
        f"https://etlantic.readthedocs.io/en/v0.39.0/{plan_rel}/",
    }
    for path in linked_surfaces:
        surface = path.read_text(encoding="utf-8")
        if plan.name not in surface and not any(url in surface for url in plan_urls):
            raise SystemExit(
                f"{path}: must link the first-class control-plane plan {plan.name}"
            )

    roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    for marker in (
        "## 0.39 — Multi-Tenant Control Plane: API and Identity Foundation",
        "## 0.40 — Tenant Registry, Workspaces, and Persistence Isolation",
        "## 0.41 — Durable Submission, State, and Reproducibility",
        "## 0.42 — Tenant Policy, Quotas, Audit, and Supply-Chain Assurance",
        "## 0.43 — First-Class Multi-Tenant Control-Plane Graduation",
    ):
        if marker not in roadmap:
            raise SystemExit(f"ROADMAP.md missing control-plane gate {marker!r}")

    mkdocs = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    # Buildable via not_in_nav + ARCHIVE_INDEX; must still be listed in mkdocs.yml.
    if plan.relative_to(ROOT / "docs").as_posix() not in mkdocs:
        raise SystemExit(
            "mkdocs.yml must list the multi-tenant plan (nav or not_in_nav)"
        )

    capabilities = (ROOT / "docs/01_GETTING_STARTED/CAPABILITIES.md").read_text(
        encoding="utf-8"
    )
    if "Partial — see [Ops Pilot]" in capabilities:
        raise SystemExit(
            "Capabilities must not label the unshipped multi-tenant control "
            "plane as Partial"
        )


def check_zero_x_roadmap_phases() -> None:
    """Keep planned ETLantic phases on the explicitly chosen 0.x timeline."""
    roadmap_path = ROOT / "ROADMAP.md"
    roadmap = roadmap_path.read_text(encoding="utf-8")

    required_markers = (
        "This roadmap has no\n1.0 or 1.x phase",
        "## 0.37 — Stable Foundation",
        "## 0.38 — Data Connectivity and Connector SDK",
        "## 0.43 — First-Class Multi-Tenant Control-Plane Graduation",
        "## 0.44 — Developer Intelligence: LSP, IDE, and Static Analysis",
        "## 0.45 — Planner and Optimization SDK",
        "## 0.46 — Streaming and Event-Driven Pipelines",
        "## 0.47 — Remote Execution Federation",
        "## 0.48 — AI-Assisted, Human-Governed Engineering",
        "## 0.49 — Brownfield Adoption Bridges",
        "## 0.50 — Operator Console",
        "## 0.51 — Managed Runtime and Enterprise Provider Packs",
        "## 0.52 — TransformationModel Incubation",
    )
    for marker in required_markers:
        if marker not in roadmap:
            raise SystemExit(f"{roadmap_path}: missing 0.x roadmap marker {marker!r}")

    adoption_plan = ROOT / "docs/11_DEVELOPMENT/ADOPTION_ECOSYSTEM_PLAN.md"
    adoption_text = adoption_plan.read_text(encoding="utf-8")
    for marker in (
        "## AP — Application-Pipeline Testing",
        "## DC — Data Connectivity and Connector SDK",
        "## MI — Metadata and Catalog Interoperability",
        "## GP — GitOps Preview and Promotion Workflow",
        "## BA — Brownfield Adoption Bridges",
        "## OC — Operator Console",
        "## EP — Managed Runtime and Enterprise Provider Packs",
    ):
        if marker not in adoption_text:
            raise SystemExit(f"{adoption_plan}: missing first-class program {marker!r}")

    mkdocs = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    if adoption_plan.relative_to(ROOT / "docs").as_posix() not in mkdocs:
        raise SystemExit(
            "mkdocs.yml must list the adoption/ecosystem plan (nav or not_in_nav)"
        )

    phase_heading = re.compile(r"(?m)^#{1,4}\s+1\.(?:0|[1-9][0-9]*|x)\b")
    forward_phase_language = re.compile(
        r"(?i)\b(?:planned(?:\s+for)?|phase|graduation|gated\s+for|"
        r"continues?\s+in|toward|post-|proposed|intended|future\s+design)"
        r"[^\n]{0,80}\b1\.(?:0|[1-9][0-9]*|x)\b"
    )
    scan_roots = (ROOT / "ROADMAP.md", ROOT / "docs", ROOT / "packages")
    for scan_root in scan_roots:
        paths = [scan_root] if scan_root.is_file() else sorted(scan_root.rglob("*.md"))
        for path in paths:
            if "specifications" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            if phase_heading.search(text):
                raise SystemExit(f"{path}: roadmap phase headings must remain 0.x")
            match = forward_phase_language.search(text)
            if match:
                raise SystemExit(
                    f"{path}: forward-looking phase language must use 0.x: "
                    f"{match.group(0)!r}"
                )


def check_residual_table_version_drift(package_version: str) -> None:
    """Residual evaluation tables must track the current minor, not the prior one."""
    major_s, minor_s = package_version.split(".")[:2]
    prior_minor = f"{major_s}.{int(minor_s) - 1}"
    stale_header = f"| Topic | {prior_minor} |"
    pages = (
        ROOT / "docs/06_EXECUTION/DEPLOYMENT.md",
        ROOT / "docs/01_GETTING_STARTED/PERFORMANCE_ENVELOPE.md",
    )
    for path in pages:
        text = path.read_text(encoding="utf-8")
        if package_version not in text:
            continue
        if stale_header in text:
            raise SystemExit(
                f"{path}: residual evaluation table still labels {prior_minor}; "
                f"expected current minor header for {package_version}"
            )


def check_release_surface_version_drift(package_version: str) -> None:
    """Keep current-facing metadata, package summaries, and release claims aligned."""
    current_minor = ".".join(package_version.split(".")[:2])

    for path in sorted((ROOT / "docs").rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for marker in re.findall(r'(?m)^current_minor:\s*"([^"]+)"\s*$', text):
            if marker != current_minor:
                raise SystemExit(
                    f"{path}: current_minor={marker!r}; expected {current_minor!r}"
                )
        for marker in re.findall(r"\*\*Current (0\.\d+) boundary:", text):
            if marker != current_minor:
                raise SystemExit(
                    f"{path}: current boundary is {marker}; expected {current_minor}"
                )

    current_package_readmes = (
        "etlantic-airflow",
        "etlantic-datafusion",
        "etlantic-s3",
        "etlantic-iceberg",
        "etlantic-snowflake",
        "etlantic-fastapi",
        "etlantic-keyring",
        "etlantic-pandas",
        "etlantic-polars",
        "etlantic-pyspark",
        "etlantic-sql",
        "etlantic-sqlmodel",
        "medallantic",
    )
    for package in current_package_readmes:
        path = ROOT / "packages" / package / "README.md"
        opening = "\n".join(path.read_text(encoding="utf-8").splitlines()[:14])
        if current_minor not in opening:
            raise SystemExit(
                f"{path}: opening must identify the current {current_minor} line"
            )
        if "PyPI Production/Stable classifiers" in opening:
            raise SystemExit(
                f"{path}: README contradicts the package's Beta classifier"
            )

    issue_config = (ROOT / ".github/ISSUE_TEMPLATE/config.yml").read_text(
        encoding="utf-8"
    )
    if f"Current {current_minor} guide" not in issue_config:
        raise SystemExit(
            ".github/ISSUE_TEMPLATE/config.yml must point to the current "
            f"{current_minor} guide"
        )

    roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    current_row = re.compile(
        rf"(?m)^\| Current \| {re.escape(current_minor)} \| [^|]+ "
        r"\| Gate-ready for tag/publish \|$"
    )
    if current_row.search(roadmap) is None:
        raise SystemExit(
            "ROADMAP.md must mark the current release gate-ready for tag/publish"
        )

    planning_hub = (ROOT / "docs/11_DEVELOPMENT/PLAN_INDEX.md").read_text(
        encoding="utf-8"
    )
    if f"ETLantic {current_minor} can do now" not in planning_hub:
        raise SystemExit(
            "PLAN_INDEX.md must direct readers to the current release surface"
        )
    if f"No {current_minor} capability is shipped" in planning_hub:
        raise SystemExit(
            "PLAN_INDEX.md still describes the current release as unshipped"
        )

    release_claim_paths = (
        ROOT / "docs/01_GETTING_STARTED/RELEASE_ARTIFACT_VERIFICATION.md",
        ROOT / "docs/01_GETTING_STARTED/ENTERPRISE_EVALUATION.md",
        ROOT / "docs/01_GETTING_STARTED/EVALUATOR.md",
        ROOT / "docs/06_EXECUTION/PRODUCTION_READINESS.md",
        ROOT / "docs/11_DEVELOPMENT/RELEASE_PROCESS.md",
    )
    premature_claims = (
        f"CycloneDX SBOM failed for v{package_version}",
        f"as with **v{package_version}**",
    )
    for path in release_claim_paths:
        text = path.read_text(encoding="utf-8")
        for claim in premature_claims:
            if claim in text:
                raise SystemExit(
                    f"{path}: predicted release outcome must be verified after publish: "
                    f"{claim!r}"
                )

    release_process = (ROOT / "docs/11_DEVELOPMENT/RELEASE_PROCESS.md").read_text(
        encoding="utf-8"
    )
    release_distributions = (
        "etlantic",
        "etlantic-polars",
        "etlantic-pandas",
        "etlantic-sql",
        "etlantic-pyspark",
        "etlantic-airflow",
        "etlantic-prefect",
        "etlantic-keyring",
        "etlantic-sqlmodel",
        "medallantic",
        "etlantic-sparkforge",
        "etlantic-datafusion",
        "etlantic-fastapi",
        "etlantic-s3",
        "etlantic-iceberg",
        "etlantic-snowflake",
    )
    for distribution in release_distributions:
        if f"| `{distribution}` |" not in release_process:
            raise SystemExit(
                "docs/11_DEVELOPMENT/RELEASE_PROCESS.md missing release "
                f"distribution {distribution}"
            )
    if "publishes sixteen distributions" not in release_process:
        raise SystemExit(
            "docs/11_DEVELOPMENT/RELEASE_PROCESS.md must state the 16-package "
            "release inventory"
        )


def check_observability_doc_consistency() -> None:
    obs_today = (ROOT / "docs/06_EXECUTION/OBSERVABILITY_TODAY.md").read_text(
        encoding="utf-8"
    )
    if "OBSERVABILITY_PROVIDER" in obs_today and "(future)" in obs_today:
        raise SystemExit(
            "OBSERVABILITY_TODAY.md must not label shipped OBSERVABILITY_PROVIDER "
            "as future"
        )


def check_quickstart_init_scaffold_sync() -> None:
    """Keep Quickstart aha imports aligned with etlantic init scaffold."""
    init_src = (ROOT / "src/etlantic/cli/cmds/init.py").read_text(encoding="utf-8")
    import_match = re.search(
        r"from etlantic import Data, Extract, Input, Load, Output, Pipeline, Transformation",
        init_src,
    )
    if import_match is None:
        raise SystemExit(
            "init.py scaffold must import Data, Extract, Input, Load, Output, "
            "Pipeline, Transformation from etlantic"
        )
    scaffold_import = import_match.group(0)
    quickstart = (ROOT / "docs/01_GETTING_STARTED/QUICKSTART.md").read_text(
        encoding="utf-8"
    )
    if scaffold_import not in quickstart:
        raise SystemExit(
            "QUICKSTART.md must include the init scaffold import line:\n"
            f"  {scaffold_import}"
        )
    if re.search(r"from etlantic import[^\n]*\bIdentity\b", quickstart):
        raise SystemExit(
            "QUICKSTART.md must not import Identity from etlantic "
            "(Identity is local in the init scaffold)"
        )


def check_api_reference_curated_root() -> None:
    """Curated-root table in API_REFERENCE must match _CURATED (no false claims)."""
    init_src = (ROOT / "src/etlantic/__init__.py").read_text(encoding="utf-8")
    curated_block = re.search(
        r"_CURATED: dict\[str, Any\] = \{([^}]+)\}",
        init_src,
        re.DOTALL,
    )
    if curated_block is None:
        raise SystemExit("Could not parse _CURATED from src/etlantic/__init__.py")
    curated = set(re.findall(r'"([^"]+)"\s*:', curated_block.group(1)))
    curated.discard("__version__")

    api_ref = (ROOT / "docs/10_REFERENCE/API_REFERENCE.md").read_text(encoding="utf-8")
    match = re.search(
        r"## Author essentials \(curated root\)\n(.*?)(?:\nOwning-module helpers|\n## )",
        api_ref,
        re.DOTALL,
    )
    if match is None:
        raise SystemExit(
            "API_REFERENCE.md missing Author essentials (curated root) section"
        )
    section = match.group(1)
    claimed: set[str] = set()
    for cell in re.findall(r"^\| `([^`]+)` \|", section, re.MULTILINE):
        for part in re.split(r"\s*/\s*", cell):
            name = part.strip().split("(", 1)[0].strip()
            if name:
                claimed.add(name)
    unknown = sorted(claimed - curated)
    if unknown:
        raise SystemExit(
            "API_REFERENCE curated-root table claims symbols not in _CURATED: "
            + ", ".join(unknown)
        )
    for banned in ("verify_plan_fingerprint", "deep_freeze"):
        if re.search(rf"`{banned}`", section):
            raise SystemExit(
                f"API_REFERENCE curated-root table must not list {banned} "
                "(owning-module only)"
            )


def check_stale_prior_minor_adopter_banners(package_version: str) -> None:
    """Fail closed on leftover prior-minor Beta / attestation copy."""
    parts = package_version.split(".")
    if len(parts) < 2:
        return
    major, minor = int(parts[0]), int(parts[1])
    if minor <= 0:
        return
    prior_minor = f"{major}.{minor - 1}"
    docs_home = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    banned_home = (
        f"{prior_minor} · Beta",
        f"ETLantic {prior_minor} is a **Beta**",
    )
    for needle in banned_home:
        if needle in docs_home:
            raise SystemExit(
                f"docs/README.md still contains stale prior-minor banner {needle!r}; "
                f"expected current {package_version} / {major}.{minor}"
            )

    wheel_re = re.compile(
        rf"etlantic-{re.escape(prior_minor)}\.\d+-.*\.whl"
        r"|etlantic-" + re.escape(prior_minor) + r"\.0-\*\.whl"
    )
    # Explicit attestation examples must use the current package wheel, not prior.
    stale_wheel = f"etlantic-{prior_minor}.0-*.whl"
    for path in (
        ROOT / "docs/01_GETTING_STARTED/ENTERPRISE_EVALUATION.md",
        ROOT / "docs/01_GETTING_STARTED/RELEASE_ARTIFACT_VERIFICATION.md",
    ):
        text = path.read_text(encoding="utf-8")
        if stale_wheel in text or wheel_re.search(text):
            raise SystemExit(
                f"{path.relative_to(ROOT)} still shows prior-minor attestation "
                f"wheel {stale_wheel!r}; pin to etlantic-{package_version}-*.whl"
            )


def check_mkdocs_nav_adoption_guards() -> None:
    """Keep deprecated Sources/Sinks and residual version stamps out of nav/status."""
    mkdocs = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    if "\nnav:" not in mkdocs:
        raise SystemExit("mkdocs.yml missing nav:")
    nav_part = mkdocs.split("\nnav:", 1)[1]
    if re.search(
        r"^\s+- .*: 05_PIPELINES/(SOURCES|SINKS)\.md\s*$",
        nav_part,
        re.MULTILINE,
    ):
        raise SystemExit(
            "mkdocs.yml nav must not include deprecated Sources/Sinks pages"
        )

    deployment = (ROOT / "docs/06_EXECUTION/DEPLOYMENT.md").read_text(encoding="utf-8")
    if re.search(r"ETLantic 0\.33 does not claim", deployment):
        raise SystemExit(
            "DEPLOYMENT.md still claims ETLantic 0.33; update to current minor"
        )
    exec_readme = (ROOT / "docs/06_EXECUTION/README.md").read_text(encoding="utf-8")
    if "0.32 operator path" in exec_readme:
        raise SystemExit("docs/06_EXECUTION/README.md still says '0.32 operator path'")


def main() -> None:
    package_version = version_from(
        ROOT / "src/etlantic/_version.py", r'__version__ = "([^"]+)"'
    )
    project_version = version_from(ROOT / "pyproject.toml", r'(?m)^version = "([^"]+)"')
    if package_version != project_version:
        raise SystemExit(
            f"Version mismatch: package={package_version}, project={project_version}"
        )

    facts = load_release_facts()
    if facts["current_version"] != package_version:
        raise SystemExit(
            "docs/release-facts.json current_version "
            f"{facts['current_version']!r} != package {package_version!r}"
        )
    major_minor = ".".join(package_version.split(".")[:2])
    if facts["current_minor"] != major_minor:
        raise SystemExit(
            "docs/release-facts.json current_minor "
            f"{facts['current_minor']!r} != {major_minor!r}"
        )
    previous_minor = str(facts["previous_minor"])
    docs_base_url = str(facts["docs_base_url"])
    expected_slug = f"v{package_version}"
    if facts.get("docs_version_slug") != expected_slug:
        raise SystemExit(
            f"docs/release-facts.json docs_version_slug must be {expected_slug!r}"
        )
    if f"/en/{expected_slug}/" not in docs_base_url:
        raise SystemExit(
            f"docs/release-facts.json docs_base_url must include /en/{expected_slug}/"
        )

    # If a package README chooses to pin an install, keep that pin synchronized
    # with core. READMEs do not have to repeat the exact current version.
    package_pin = re.compile(
        r"(?:etlantic(?:-[a-z0-9-]+)?|medallantic)"
        r"(?:\[[^\]]+\])?==(\d+\.\d+\.\d+)"
    )
    for readme in sorted((ROOT / "packages").glob("*/README.md")):
        text = readme.read_text(encoding="utf-8")
        for pin in package_pin.findall(text):
            if pin != package_version:
                raise SystemExit(
                    f"{readme} contains stale package pin {pin}; "
                    f"expected {package_version}"
                )

    check_local_markdown_links()
    check_docs_ban_absolute_rtd_latest()
    check_python_code_fences()
    check_standard_links()
    check_control_plane_plan()
    check_zero_x_roadmap_phases()
    check_residual_table_version_drift(package_version)
    check_release_surface_version_drift(package_version)
    check_observability_doc_consistency()
    check_quickstart_init_scaffold_sync()
    check_api_reference_curated_root()
    check_stale_prior_minor_adopter_banners(package_version)
    check_mkdocs_nav_adoption_guards()

    current_markers = [
        ROOT / "docs/01_GETTING_STARTED/FIRST_PIPELINE.md",
        ROOT / "docs/01_GETTING_STARTED/EVALUATOR.md",
        ROOT / "docs/01_GETTING_STARTED/FAQ.md",
        ROOT / "docs/01_GETTING_STARTED/CAPABILITIES.md",
        ROOT / "docs/10_REFERENCE/DIAGNOSTICS.md",
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
                f"| Topic | {prior_minor} |",
                f"| Concern | Status in {prior_minor} |",
                f"| Concern | {prior_minor} status |",
                f"pin all to `{prior_patch}`",
                f"(`{prior_patch}` with `{prior_patch}`)",
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
        raise SystemExit("mkdocs.yml still labels Start Here as Current 0.10 Guide")
    if f"Current {major_minor} Guide:" not in mkdocs:
        raise SystemExit(
            f"mkdocs.yml must label Start Here as Current {major_minor} Guide"
        )
    for section in (
        "  - Start Here:",
        "  - Tutorials:",
        "  - How-to:",
        "  - Concepts:",
        "  - Reference:",
        "  - Extend:",
        "  - Evaluate:",
        "  - Project:",
    ):
        if section not in mkdocs:
            raise SystemExit(f"mkdocs.yml missing public nav section {section!r}")

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
    development_readme = (ROOT / "docs/11_DEVELOPMENT/README.md").read_text(
        encoding="utf-8"
    )
    archive_url = (
        "https://etlantic.readthedocs.io/en/latest/11_DEVELOPMENT/ARCHIVE_INDEX/"
    )
    if "ARCHIVE_INDEX.md" not in development_readme and archive_url not in (
        development_readme
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
        current_exit_gate = (
            ROOT
            / "docs/11_DEVELOPMENT"
            / f"EXIT_GATE_{major_minor_for_notes.replace('.', '_')}.md"
        )
        if not current_exit_gate.exists():
            raise SystemExit(f"Missing {current_exit_gate.relative_to(ROOT)}")
        development_readme = (ROOT / "docs/11_DEVELOPMENT/README.md").read_text(
            encoding="utf-8"
        )
        migration_link = current_migration.name
        exit_gate_link = current_exit_gate.name
        if (
            migration_link not in development_readme
            and readthedocs_url(current_migration) not in development_readme
        ):
            raise SystemExit(
                "docs/11_DEVELOPMENT/README.md must link current migration "
                f"{migration_link}"
            )
        if (
            exit_gate_link not in development_readme
            and readthedocs_url(current_exit_gate) not in development_readme
        ):
            raise SystemExit(
                "docs/11_DEVELOPMENT/README.md must link current exit gate "
                f"{exit_gate_link}"
            )
        getting_started = (ROOT / "docs/01_GETTING_STARTED/README.md").read_text(
            encoding="utf-8"
        )
        whats_new_link = f"WHATS_NEW_{major_minor_for_notes.replace('.', '_')}.md"
        if (
            whats_new_link not in getting_started
            and readthedocs_url(whats_new_minor) not in getting_started
        ):
            raise SystemExit(
                "docs/01_GETTING_STARTED/README.md must link current What's New "
                f"{whats_new_link}"
            )
        # Adopter-facing migration link text must say prior → current (not
        # current → current). Ban blanket "does not implement MERGE".
        expected_migration_label = (
            f"Migration {previous_minor} → {major_minor_for_notes}"
        )
        bad_migration_label = (
            f"Migration {major_minor_for_notes} → {major_minor_for_notes}"
        )
        ships_in_prior = f"ships in {previous_minor}"
        adopter_migration_pages = (
            ROOT / "docs/01_GETTING_STARTED/CURRENT_VERSION.md",
            ROOT / "docs/01_GETTING_STARTED/UPGRADE.md",
            ROOT / "docs/01_GETTING_STARTED/WHATS_NEW_"
            f"{major_minor_for_notes.replace('.', '_')}.md",
            ROOT / "docs/01_GETTING_STARTED/FAQ.md",
            ROOT / "docs/01_GETTING_STARTED/MIGRATION_FROM_OTHER_TOOLS.md",
            ROOT / "docs/01_GETTING_STARTED/EVALUATOR.md",
            ROOT / "docs/01_GETTING_STARTED/ENTERPRISE_EVALUATION.md",
        )
        for path in adopter_migration_pages:
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            if bad_migration_label in text:
                raise SystemExit(
                    f"{path}: mislabeled migration link {bad_migration_label!r}; "
                    f"use {expected_migration_label!r}"
                )
            if (
                current_migration.name in text
                and expected_migration_label not in text
                and f"{previous_minor} → {major_minor_for_notes}" not in text
            ):
                raise SystemExit(
                    f"{path}: links {current_migration.name} without "
                    f"{expected_migration_label!r} (or From→To column "
                    f"{previous_minor} → {major_minor_for_notes})"
                )
            if ships_in_prior in text.lower():
                raise SystemExit(
                    f"{path}: still says {ships_in_prior!r}; update to "
                    f"{major_minor_for_notes}"
                )
        merge_ban_pages = (
            ROOT / "docs/01_GETTING_STARTED/INSTALLATION.md",
            ROOT / "docs/06_EXECUTION/SQL.md",
            ROOT / "docs/06_EXECUTION/SQL_TUTORIAL.md",
            ROOT / "docs/06_EXECUTION/SQL_PUSHDOWN.md",
            ROOT / "docs/06_EXECUTION/SQL_EXECUTION.md",
            ROOT / "docs/07_PLUGIN_SDK/SQL_DIALECT.md",
            ROOT / "docs/07_PLUGIN_SDK/SQL_PLUGIN.md",
            ROOT / "docs/10_REFERENCE/KNOWN_ISSUES.md",
            ROOT / "docs/10_REFERENCE/RUNTIME_CONFIGURATION.md",
            ROOT / "packages/etlantic-sql/README.md",
        )
        merge_ban = re.compile(
            r"(?:(?:reference plugin|etlantic-sql).{0,80}"
            r"does not (?:implement|advertise)\s+`?MERGE`?"
            r"|does not (?:implement|advertise)\s+`?MERGE`?\s+on\s+PostgreSQL)",
            re.IGNORECASE | re.DOTALL,
        )
        sqlite_demo_only = re.compile(
            r"(?:SQLite.{0,80}(?:demo-only|demos only|local demos only)"
            r"|(?:demo-only|demos only).{0,80}SQLite)",
            re.IGNORECASE | re.DOTALL,
        )
        for path in merge_ban_pages:
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            if merge_ban.search(text):
                raise SystemExit(
                    f"{path}: blanket 'does not implement MERGE' is outdated; "
                    "document PostgreSQL sql_merge=True / SQLite sql_merge=False"
                )
            if sqlite_demo_only.search(text):
                raise SystemExit(
                    f"{path}: SQLite is Tier A in 0.33, not demo-only; "
                    "document PostgreSQL-only merge separately"
                )
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
        "  - Extend:",
        "  - Project:",
        "11_DEVELOPMENT/ARCHIVE_INDEX.md",
    ):
        if required_nav not in mkdocs_text:
            raise SystemExit(f"mkdocs.yml missing required entry {required_nav!r}")
    if "05_PIPELINES/EXTRACTS.md" not in mkdocs_text:
        raise SystemExit("mkdocs.yml missing EXTRACTS.md (nav or not_in_nav)")
    if "05_PIPELINES/LOADS.md" not in mkdocs_text:
        raise SystemExit("mkdocs.yml missing LOADS.md (nav or not_in_nav)")
    # Design proposals stay archive-only (not_in_nav), never ahead of Reference.
    if "Design Proposals:" in mkdocs_text.split("\nnav:", 1)[-1]:
        raise SystemExit(
            "mkdocs.yml must not put Design Proposals in primary nav "
            "(use not_in_nav + ARCHIVE_INDEX)"
        )
    mkdocs_text = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    extend_idx = mkdocs_text.find("  - Extend:")
    compiler_idx = mkdocs_text.find(
        "Portable Transform Compiler: 07_PLUGIN_SDK/PORTABLE_TRANSFORM_COMPILER.md"
    )
    if extend_idx < 0 or compiler_idx < extend_idx:
        raise SystemExit(
            "mkdocs.yml must promote Portable Transform Compiler under Extend"
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
        "medallantic",
        "etlantic-keyring",
        "Graphviz",
        "Observability providers",
        "Run history providers",
        "Event consumers",
        "report query",
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
        ROOT / "docs/09_EXAMPLES/MEDALLANTIC.md",
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
        ROOT / "packages/medallantic/README.md",
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
        "MEDALLANTIC.md",
        "PORTABLE_TRANSFORMS.md",
        "INTERCHANGE_POLARS_PANDAS.md",
        "CONTRACT_FIRST_TUTORIAL.md",
        "PREFECT_RUN.md",
        "SAMPLE_PROJECT.md",
        "PRODUCTION_SAMPLE.md",
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
        ROOT / "docs/07_PLUGIN_SDK/RESOURCE_PROVIDER.md",
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

    # Day-0 install must not send adopters to mutable main when the current
    # version is already on PyPI (or when docs claim the pin).
    day0_paths = [
        ROOT / "docs/01_GETTING_STARTED/INSTALLATION.md",
        ROOT / "docs/01_GETTING_STARTED/QUICKSTART.md",
        ROOT / "docs/01_GETTING_STARTED/FIRST_PIPELINE.md",
        ROOT / "docs/01_GETTING_STARTED/SDK_10_MINUTES.md",
        ROOT / "docs/01_GETTING_STARTED/TROUBLESHOOTING.md",
        ROOT / "docs/06_EXECUTION/POLARS_TUTORIAL.md",
        ROOT / "docs/README.md",
    ]
    main_install = "git+https://github.com/eddiethedean/etlantic.git@main"
    for path in day0_paths:
        text = path.read_text(encoding="utf-8")
        if main_install in text and "contributor" not in text.lower()[:800]:
            # Allow @main only in clearly labeled contributor/source sections
            # after the day-0 install block. Fail if it appears in the first
            # install instructions (top of file before "Install from source").
            head = text.split("## Install from source", 1)[0]
            head = head.split("## Repository checkout", 1)[0]
            if main_install in head or f"Until {previous_minor}.0 is on PyPI" in head:
                raise SystemExit(
                    f"{path}: day-0 install must use PyPI pin, not git+…@main "
                    f"(see RELEASE_ARTIFACT_VERIFICATION / INSTALLATION)"
                )
        if "SPDX SBOM" in text:
            raise SystemExit(f"{path}: do not claim SPDX SBOM digests")

    supply_chain_paths = [
        ROOT / "docs/01_GETTING_STARTED/ENTERPRISE_EVALUATION.md",
        ROOT / "docs/01_GETTING_STARTED/EVALUATOR.md",
        ROOT / "docs/06_EXECUTION/PRODUCTION_READINESS.md",
        ROOT / "SECURITY.md",
        ROOT / "docs/02_FOUNDATIONS/SECURITY.md",
        ROOT / "docs/01_GETTING_STARTED/COMPARE.md",
    ]
    for path in supply_chain_paths:
        text = path.read_text(encoding="utf-8")
        if "SPDX SBOM" in text:
            raise SystemExit(
                f"{path}: replace SPDX SBOM claims with SHA-256 digests / "
                "attestations / optional CycloneDX (see RELEASE_ARTIFACT_VERIFICATION)"
            )
        if re.search(r"\bships?\s+.*\bSBOM digests\b", text, flags=re.I):
            raise SystemExit(
                f"{path}: avoid unqualified 'SBOM digests' — use SHA-256 "
                f"manifest language (v{package_version} CycloneDX optional)"
            )
    verification = ROOT / "docs/01_GETTING_STARTED/RELEASE_ARTIFACT_VERIFICATION.md"
    if not verification.is_file():
        raise SystemExit(
            "missing docs/01_GETTING_STARTED/RELEASE_ARTIFACT_VERIFICATION.md"
        )
    verification_text = verification.read_text(encoding="utf-8")
    for needle in (
        "release-artifacts.json",
        "sbom-warning.txt",
        "attestation",
        "SHA-256",
    ):
        if needle not in verification_text:
            raise SystemExit(
                f"RELEASE_ARTIFACT_VERIFICATION.md must mention {needle!r}"
            )

    if "Green path" not in (ROOT / "docs/README.md").read_text(encoding="utf-8"):
        raise SystemExit("docs/README.md missing Green path rail")
    docs_home = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    green_idx = docs_home.find("Green path")
    if green_idx < 0:
        raise SystemExit("docs/README.md missing Green path rail")
    green_block = docs_home[green_idx : green_idx + 700]
    install_pos = green_block.find("pip install etlantic")
    quickstart_pos = green_block.find("Quickstart")
    if install_pos < 0 or (quickstart_pos >= 0 and install_pos > quickstart_pos):
        raise SystemExit(
            "docs/README.md Green path must lead with pip install etlantic"
        )
    if "prefer from-source until PyPI" in docs_home:
        raise SystemExit("docs/README.md still prefers from-source install")
    # Current What's New must not point at the prior release notes file.
    whats_new_current_link = Path(str(facts["whats_new"])).name
    prior_whats_new = f"WHATS_NEW_{previous_minor.replace('.', '_')}.md"
    # Homepage "current release" row must target current What's New.
    if "Review the current release" in docs_home:
        idx = docs_home.find("Review the current release")
        snippet = docs_home[idx : idx + 160]
        if prior_whats_new in snippet and whats_new_current_link not in snippet:
            raise SystemExit(
                "docs/README.md 'Review the current release' still links prior "
                f"What's New ({prior_whats_new})"
            )
        if whats_new_current_link not in snippet:
            raise SystemExit(
                "docs/README.md 'Review the current release' must link "
                f"{whats_new_current_link}"
            )
    # CAPABILITIES / ROADMAP must not claim the prior minor as "current".
    for path, banned in (
        (
            ROOT / "docs/01_GETTING_STARTED/CAPABILITIES.md",
            f"## What works today ({previous_minor})",
        ),
        (
            ROOT / "ROADMAP.md",
            f"**Current release:** ETLantic **{previous_minor}.0**",
        ),
    ):
        text = path.read_text(encoding="utf-8")
        if banned in text:
            raise SystemExit(
                f"{path.relative_to(ROOT)} still claims prior minor as current: "
                f"{banned!r}"
            )
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
        and versioned_readthedocs_url(
            ROOT / "docs" / str(facts["whats_new"]),
            docs_base_url=docs_base_url,
        )
        not in docs_home
        and readthedocs_url(ROOT / "docs" / str(facts["whats_new"])) not in docs_home
    ):
        raise SystemExit(
            f"docs/README.md must link What's new in {major_minor} to {whats_new_current_link}"
        )
    # Release-facing READMEs must prefer immutable versioned docs URLs.
    release_facing = [
        ROOT / "README.md",
        *sorted((ROOT / "packages").glob("*/README.md")),
    ]
    latest_prefix = "https://etlantic.readthedocs.io/en/latest/"
    versioned_prefix = docs_base_url.rstrip("/") + "/"
    for path in release_facing:
        text = path.read_text(encoding="utf-8")
        if latest_prefix in text:
            raise SystemExit(
                f"{path.relative_to(ROOT)}: release-facing README must use "
                f"{versioned_prefix} (not /en/latest/)"
            )
    known = (ROOT / "docs/10_REFERENCE/KNOWN_ISSUES.md").read_text(encoding="utf-8")
    if "etlantic-airflow" not in known:
        raise SystemExit(
            "KNOWN_ISSUES.md must state Airflow is available via etlantic-airflow"
        )
    mkdocs = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    if "site_url: https://etlantic.readthedocs.io/" not in mkdocs:
        raise SystemExit("mkdocs.yml site_url must be https://etlantic.readthedocs.io/")
    future_viz = mkdocs.find("Visualization (beyond Mermaid)")
    if future_viz >= 0:
        raise SystemExit(
            "mkdocs.yml still nests shipped viz under Visualization (beyond Mermaid)"
        )
    for shipped_viz in (
        "08_VISUALIZATION/GRAPHVIZ.md",
        "08_VISUALIZATION/HTML.md",
        "08_VISUALIZATION/LINEAGE.md",
    ):
        if shipped_viz not in mkdocs:
            raise SystemExit(
                f"mkdocs.yml must list shipped viz page {shipped_viz} "
                "(nav or not_in_nav)"
            )
    if "AIRFLOW_COMPILE.md" not in mkdocs or "MEDALLANTIC.md" not in mkdocs:
        raise SystemExit("mkdocs.yml missing runnable example guide pages")
    if "RUNTIME_CONFIGURATION.md" not in mkdocs:
        raise SystemExit("mkdocs.yml missing RUNTIME_CONFIGURATION.md")
    if "hooks:" not in mkdocs or "docs/hooks.py" not in mkdocs:
        raise SystemExit("mkdocs.yml must register docs/hooks.py for search exclusions")
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
    if "AIRFLOW_COMPILE/" not in banner_js or "MEDALLANTIC/" not in banner_js:
        raise SystemExit(
            "status-banner.js must exclude runnable example guides from design banner"
        )
    if "PRODUCTION_SAMPLE/" not in banner_js:
        raise SystemExit(
            "status-banner.js must exclude PRODUCTION_SAMPLE from design-example banner"
        )
    if "PREFECT_RUN/" not in banner_js:
        raise SystemExit(
            "status-banner.js must exclude PREFECT_RUN from design-example banner"
        )
    if "CONTRACT_FIRST_TUTORIAL/" not in banner_js:
        raise SystemExit(
            "status-banner.js must exclude CONTRACT_FIRST_TUTORIAL from design banner"
        )

    # GitHub blob links into docs/ must point at files that still exist.
    blob_re = re.compile(
        r"https://github\.com/[^/\s]+/[^/\s]+/blob/[^/\s]+/(docs/[^\s)#]+\.md)"
    )
    for path in (ROOT / "docs").rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        for match in blob_re.finditer(text):
            rel = match.group(1)
            if not (ROOT / rel).exists():
                raise SystemExit(f"{path}: dead GitHub docs link to missing {rel}")
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
    for future_sdk in ("RESOURCE_PROVIDER",):
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
        ROOT / "packages/medallantic/pyproject.toml",
        ROOT / "packages/etlantic-sparkforge/pyproject.toml",
        ROOT / "packages/etlantic-fastapi/pyproject.toml",
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
        ROOT / "packages/medallantic/src/medallantic/__init__.py",
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
        # Case-insensitive "Current {prior} Guide" drift (title case variants).
        current_guide_re = re.compile(
            rf"Current\s+{re.escape(prior_minor)}\s+Guide",
            re.IGNORECASE,
        )
        for path in (
            ROOT / "docs/01_GETTING_STARTED/LEARNING_PATH.md",
            ROOT / "docs/01_GETTING_STARTED/ENTERPRISE_EVALUATION.md",
            ROOT / "docs/01_GETTING_STARTED/CURRENT_VERSION.md",
            ROOT / "docs/01_GETTING_STARTED/README.md",
            ROOT / "mkdocs.yml",
        ):
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            if current_guide_re.search(text):
                raise SystemExit(
                    f"{path} still presents Current {prior_minor} Guide "
                    f"(case-insensitive)"
                )

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

        # Version placeholders outside normal scrub paths.
        prior_patch = f"{prior_minor}.0"
        for path, needles in (
            (
                ROOT / ".github/ISSUE_TEMPLATE/bug_report.yml",
                (prior_patch, f"etlantic-polars=={prior_patch}"),
            ),
            (
                ROOT / "packages/medallantic/docs/compatibility.md",
                (f"medallantic {prior_minor}.x", f"etlantic {prior_minor}.x"),
            ),
            (
                ROOT / "packages/medallantic/docs/README.md",
                (f"Medallantic {prior_minor} ",),
            ),
            (
                ROOT / "src/etlantic/plugin_trust.py",
                (f"=={prior_patch}",),
            ),
        ):
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            for needle in needles:
                if needle in text:
                    raise SystemExit(
                        f"{path} still contains stale prior-minor pin {needle!r}"
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
        ROOT / "docs/01_GETTING_STARTED/END_TO_END_PILOT.md",
        ROOT / "docs/01_GETTING_STARTED/ENTERPRISE_EVALUATION.md",
        ROOT / "docs/01_GETTING_STARTED/PILOT_EVIDENCE_PACKET.md",
        ROOT / "docs/01_GETTING_STARTED/RELEASE_ARTIFACT_VERIFICATION.md",
        ROOT / "docs/01_GETTING_STARTED/PORTABLE_VS_NATIVE.md",
        ROOT / "docs/01_GETTING_STARTED/PORTABLE_FAILURE_COOKBOOK.md",
        ROOT / "docs/01_GETTING_STARTED/INTERCHANGE_GATE_A_FAQ.md",
        ROOT / "docs/05_PIPELINES/PROFILE_PRIMER.md",
        ROOT / "docs/05_PIPELINES/PROFILES.md",
        ROOT / "docs/05_PIPELINES/PROFILES_HUB.md",
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
        ROOT / "docs/08_VISUALIZATION/APPLICATION_INTEGRATION.md",
        ROOT / "docs/09_EXAMPLES/PRODUCTION_SAMPLE.md",
        ROOT / "docs/09_EXAMPLES/AIRFLOW_COMPILE.md",
        ROOT / "docs/09_MEDALLANTIC/GETTING_STARTED.md",
        ROOT / "docs/09_MEDALLANTIC/TROUBLESHOOTING.md",
        ROOT / "docs/10_REFERENCE/API_QUALITY.md",
        ROOT / "docs/10_REFERENCE/DIAGNOSTICS.md",
        *sorted((ROOT / "docs/10_REFERENCE/api_optional").glob("*.md")),
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
        ROOT / "packages/medallantic/README.md",
        ROOT / "packages/medallantic/docs/getting-started.md",
        ROOT / "packages/medallantic/ROADMAP.md",
        ROOT / "packages/etlantic-s3/README.md",
        ROOT / "packages/etlantic-iceberg/README.md",
        ROOT / "packages/etlantic-snowflake/README.md",
        ROOT / "packages/etlantic-prefect/README.md",
        ROOT / "examples/portable_polars_kernel.py",
        ROOT / "examples/portable_pandas_kernel.py",
        ROOT / "examples/sample_pilot/profiles/prod.json",
    ]
    if prior_minor is not None:
        prior_pin = f"etlantic=={prior_minor}.0"
        prior_range = f">={prior_minor}.0,<{major_minor}"
        prior_range_short = f">={prior_minor},<{major_minor}"
        prior_tag = f"v{prior_minor}.0"
        prior_status = f"Available in ETLantic {prior_minor}.0"
        prior_status_short = f"Available in ETLantic {prior_minor}"
        prior_prior_minor = None
        try:
            maj_s, min_s = prior_minor.split(".")
            if int(min_s) > 0:
                prior_prior_minor = f"{maj_s}.{int(min_s) - 1}"
        except ValueError:
            prior_prior_minor = None
        stale_pins: list[str] = [prior_pin]
        if prior_prior_minor is not None:
            stale_pins.extend(
                [
                    f"etlantic=={prior_prior_minor}.0",
                    f"etlantic=={prior_prior_minor}.1",
                    f"=={prior_prior_minor}.0",
                    f"=={prior_prior_minor}.1",
                ]
            )
        for path in prior_pin_paths:
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            stale_package_pin = re.search(
                rf"(?:etlantic(?:-[a-z0-9]+)*|medallantic)=={re.escape(prior_minor)}\.0",
                text,
            )
            if stale_package_pin is not None:
                raise SystemExit(
                    f"{path} still pins prior-minor package "
                    f"{stale_package_pin.group(0)}"
                )
            for stale in stale_pins:
                if stale in text:
                    raise SystemExit(f"{path} still pins {stale}")
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
            expect_prior = f"expect {prior_minor}.0"
            prints_prior_full = f"prints `{prior_minor}.0`"
            prints_prior_plain = f"prints {prior_minor}.0"
            if expect_prior in text:
                raise SystemExit(
                    f"{path} still says {expect_prior!r}; expected "
                    f"expect {package_version}"
                )
            if prints_prior_full in text or prints_prior_plain in text:
                raise SystemExit(
                    f"{path} still says prints `{prior_minor}.0`; expected "
                    f"`{package_version}`"
                )

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
    # Classifiers and plugin dependency ranges must match the Beta pilot envelope.
    plugin_stable_classifier = "Development Status :: 5 - Production/Stable"
    root_beta_classifier = "Development Status :: 4 - Beta"
    alpha_classifier = "Development Status :: 3 - Alpha"
    next_minor = None
    try:
        maj_s, min_s = major_minor.split(".")
        next_minor = f"{maj_s}.{int(min_s) + 1}"
    except ValueError:
        next_minor = None
    experimental_packages = {
        "etlantic-datafusion",
        "etlantic-s3",
        "etlantic-iceberg",
        "etlantic-snowflake",
    }
    reference_packages = {"etlantic-fastapi"}
    redirect_packages = {"etlantic-sparkforge"}
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
        if pkg_name in redirect_packages:
            inactive_classifier = "Development Status :: 7 - Inactive"
            if inactive_classifier not in text:
                raise SystemExit(
                    f"{path} redirect package should use Inactive classifier"
                )
            if next_minor is not None:
                expected_med = f"medallantic>={major_minor}.0,<{next_minor}"
                if expected_med not in text:
                    raise SystemExit(
                        f"{path} must depend on {expected_med} (found mismatched medallantic range)"
                    )
            continue
        if alpha_classifier in text:
            raise SystemExit(f"{path} still uses Alpha classifier")
        if plugin_stable_classifier in text:
            raise SystemExit(
                f"{path} should use Beta, not Production/Stable (Beta pilot envelope)"
            )
        if root_beta_classifier not in text:
            raise SystemExit(f"{path} missing Beta classifier")
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

    subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_surface_inventory.py")],
        check=True,
    )
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_diagnostic_stability.py")],
        check=True,
    )
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_protocol_freeze.py")],
        check=True,
    )

    # CLI.md must document every public CLI command (contract vs Typer surface).
    sys.path.insert(0, str(ROOT / "src"))
    from etlantic.agents import PUBLIC_CLI_COMMANDS

    cli_md = (ROOT / "docs/10_REFERENCE/CLI.md").read_text(encoding="utf-8")
    for cmd in PUBLIC_CLI_COMMANDS:
        heading = f"## `{cmd}`"
        if heading not in cli_md:
            raise SystemExit(f"CLI.md missing section for public command: {heading}")

    # Typer surface vs CLI.md (top-level + key subcommands like report query / viz *).
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_cli_docs.py")],
        check=True,
    )

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
            prints_prior_full = f"prints `{prior_minor}.0`"
            expect_prior = f"expect {prior_minor}.0"
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
            if prints_prior in text or prints_prior_full in text:
                raise SystemExit(
                    f"{path} still says prints `{prior_minor}` / "
                    f"`{prior_minor}.0`; expected `{package_version}`"
                )
            if expect_prior in text:
                raise SystemExit(
                    f"{path} still says {expect_prior!r}; expected "
                    f"expect {package_version}"
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
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_api_docs_coverage.py")],
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

    check_nav_page_status_markers()
    check_not_in_nav_orphans()
    external = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/check_external_links.py"),
            "--external-report",
            str(ROOT / "site" / "external-urls.txt"),
        ],
        cwd=ROOT,
        check=False,
    )
    if external.returncode != 0:
        raise SystemExit("check_external_links.py failed")

    print(f"Documentation consistency checks passed for {package_version}.")


if __name__ == "__main__":
    main()
