"""ETLantic agent guidance, context bundles, and human-governed proposals."""

from __future__ import annotations

from etlantic.agents.catalog import (
    CANONICAL_TASKS,
    FORBIDDEN_ACTIONS,
    AiTask,
    action_is_forbidden,
    catalog_to_dict,
    task_by_id,
    task_catalog,
)
from etlantic.agents.context import ContextBundle, assemble_context_bundle
from etlantic.agents.diagnostics import (
    ctx_diagnostic,
    guide_diagnostic,
    mcp_diagnostic,
    prop_diagnostic,
)
from etlantic.agents.guidance import (
    PUBLIC_CLI_COMMANDS,
    PUBLIC_SDK_IMPORTS,
    SECURITY_RULES,
    generate_agent_guidance,
    render_agents_md,
    render_claude_md,
    render_codex_skill_md,
    render_cursor_rule,
)
from etlantic.agents.mcp_trust import discover_mcp_servers, mcp_server_allowed
from etlantic.agents.proposal import (
    PROPOSAL_SCHEMA,
    Proposal,
    ProposalValidation,
    request_proposal_approval,
    validate_proposal,
)
from etlantic.agents.regions import merge_user_regions

__all__ = [
    "CANONICAL_TASKS",
    "FORBIDDEN_ACTIONS",
    "PROPOSAL_SCHEMA",
    "PUBLIC_CLI_COMMANDS",
    "PUBLIC_SDK_IMPORTS",
    "SECURITY_RULES",
    "AiTask",
    "ContextBundle",
    "Proposal",
    "ProposalValidation",
    "action_is_forbidden",
    "assemble_context_bundle",
    "catalog_to_dict",
    "ctx_diagnostic",
    "discover_mcp_servers",
    "generate_agent_guidance",
    "guide_diagnostic",
    "mcp_diagnostic",
    "mcp_server_allowed",
    "merge_user_regions",
    "prop_diagnostic",
    "render_agents_md",
    "render_claude_md",
    "render_codex_skill_md",
    "render_cursor_rule",
    "request_proposal_approval",
    "task_by_id",
    "task_catalog",
    "validate_proposal",
]
