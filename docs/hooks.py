"""MkDocs hooks for ETLantic docs site hygiene."""

from __future__ import annotations

# Archive / maintainer history: keep buildable via ARCHIVE_INDEX, exclude from search.
_SEARCH_EXCLUDE_PREFIXES = (
    "11_DEVELOPMENT/MIGRATION_",
    "11_DEVELOPMENT/EXIT_GATE_",
    "11_DEVELOPMENT/DOCUMENTATION_AUDIT_",
    "11_DEVELOPMENT/DESIGN_PROPOSALS",
    "11_DEVELOPMENT/PERFORMANCE_RESULTS",
    "11_DEVELOPMENT/PORTABLE_TRANSFORM_PLAN",
    "11_DEVELOPMENT/SCHEDULER_AND_PREFECT_PLAN",
    "11_DEVELOPMENT/DTCS_",
    "11_DEVELOPMENT/CONTRACTMODEL_UPGRADE_PLAN",
    "11_DEVELOPMENT/TRANSFORMATIONMODEL_PLAN",
    "11_DEVELOPMENT/INTEROPERABILITY_FOUNDATION_PLAN",
    "11_DEVELOPMENT/SCHEMA_DRIFT_PLAN",
    "11_DEVELOPMENT/ETL_RELIABILITY_PLAN",
    "11_DEVELOPMENT/SQLMODEL_INTEGRATION_PLAN",
    "11_DEVELOPMENT/SPARKFORGE_ADOPTION",
    "11_DEVELOPMENT/FASTAPI_INTEGRATION_PLAN",
    "11_DEVELOPMENT/MULTI_TENANT_CONTROL_PLANE_PLAN",
    "11_DEVELOPMENT/ADOPTION_ECOSYSTEM_PLAN",
    "11_DEVELOPMENT/UI_UX_PLAN",
    "11_DEVELOPMENT/PROGRAMMATIC_AUTHORING_0_24",
    "11_DEVELOPMENT/REMOVAL_CANDIDATES_",
    "11_DEVELOPMENT/adr/",
    "01_GETTING_STARTED/WHATS_NEW_0_1",
    "01_GETTING_STARTED/WHATS_NEW_0_2",
    "01_GETTING_STARTED/WHATS_NEW_0_3",
)


def _should_exclude_from_search(src_uri: str) -> bool:
    # Current What's New stays searchable (0.34+); older notes match WHATS_NEW_0_1*/0_2*/0_3*.
    if src_uri.startswith("01_GETTING_STARTED/WHATS_NEW_0_34"):
        return False
    return any(src_uri.startswith(prefix) for prefix in _SEARCH_EXCLUDE_PREFIXES)


def on_page_markdown(markdown, page, config, files):
    """Mark archive / historical pages so Material search skips them."""
    path = page.file.src_uri
    if _should_exclude_from_search(path):
        meta = getattr(page, "meta", None)
        if meta is None:
            page.meta = {}
            meta = page.meta
        meta["search"] = {"exclude": True}
    return markdown
