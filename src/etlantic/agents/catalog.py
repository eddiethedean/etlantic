"""Vendor-neutral ETLantic AI task catalog (`etlantic.ai_task/1`)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

AI_TASK_SCHEMA = "etlantic.ai_task/1"

FORBIDDEN_ACTIONS = frozenset(
    {
        "run.submit",
        "schedule.create",
        "schedule.pause",
        "schedule.trigger",
        "erasure.approve",
        "erasure.execute",
        "dlq.redrive",
        "secret.resolve",
        "plugin.install",
        "network.contact",
        "tools.grant",
        "baseline.acknowledge",
        "notification.route",
    }
)

READ_ONLY_EVIDENCE = (
    "inspect",
    "validate",
    "plan",
    "diff",
    "impact",
    "context_bundle",
)

ALLOWED_PROPOSAL_ACTIONS = frozenset(READ_ONLY_EVIDENCE)

_FORBIDDEN_ACTION_PREFIXES = frozenset(
    {
        "run",
        "schedule",
        "erasure",
        "dlq",
        "secret",
        "plugin",
        "network",
        "tools",
        "baseline",
        "notification",
        "approval",
        "approvals",
    }
)


@dataclass(frozen=True, slots=True)
class AiTask:
    """One vendor-neutral agent workflow."""

    task_id: str
    title: str
    description: str
    required_evidence: tuple[str, ...]
    approval_hook: str
    forbidden_actions: tuple[str, ...] = tuple(sorted(FORBIDDEN_ACTIONS))
    adapters: tuple[str, ...] = ("codex", "claude", "cursor")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": AI_TASK_SCHEMA,
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "required_evidence": list(self.required_evidence),
            "approval_hook": self.approval_hook,
            "forbidden_actions": list(self.forbidden_actions),
            "adapters": list(self.adapters),
        }


CANONICAL_TASKS: tuple[AiTask, ...] = (
    AiTask(
        task_id="explain_pipeline",
        title="Explain a pipeline",
        description="Inspect graph, plan, and diagnostics without execution.",
        required_evidence=READ_ONLY_EVIDENCE,
        approval_hook="pre_plan",
    ),
    AiTask(
        task_id="scaffold_model",
        title="Scaffold a model",
        description="Propose contract-compatible authoring files for review.",
        required_evidence=("validate", "diff", "impact", "proposal"),
        approval_hook="pre_promote",
    ),
    AiTask(
        task_id="diagnose_wiring",
        title="Diagnose wiring",
        description="Explain validation and capability diagnostics.",
        required_evidence=("validate", "inspect", "plan"),
        approval_hook="pre_plan",
    ),
    AiTask(
        task_id="generate_contracts",
        title="Generate contracts",
        description="Propose ODCS/DTCS/DPCS artifacts as reviewable files.",
        required_evidence=("validate", "diff", "proposal"),
        approval_hook="pre_promote",
    ),
    AiTask(
        task_id="create_conformance_tests",
        title="Create conformance tests",
        description="Propose tests that use public SDK imports only.",
        required_evidence=("validate", "proposal"),
        approval_hook="pre_promote",
    ),
    AiTask(
        task_id="review_security",
        title="Review security",
        description="Check redaction, allowlists, and secret-free artifacts.",
        required_evidence=("inspect", "context_bundle"),
        approval_hook="privileged_op",
    ),
    AiTask(
        task_id="propose_migration",
        title="Propose a migration",
        description="Propose reviewable schema or pipeline migrations.",
        required_evidence=("diff", "impact", "proposal"),
        approval_hook="pre_promote",
    ),
    AiTask(
        task_id="propose_optimization",
        title="Propose an optimization",
        description="Advisory 0.45 optimizer candidate; never apply without approval.",
        required_evidence=("plan", "diff", "proposal"),
        approval_hook="pre_promote",
    ),
)


def task_catalog() -> tuple[AiTask, ...]:
    """Return the frozen vendor-neutral catalog."""
    return CANONICAL_TASKS


def catalog_to_dict() -> dict[str, Any]:
    return {
        "schema": AI_TASK_SCHEMA,
        "tasks": [task.to_dict() for task in CANONICAL_TASKS],
        "forbidden_actions": sorted(FORBIDDEN_ACTIONS),
        "adapter_boundary": "same structured proposal and approval for all adapters",
    }


def task_by_id(task_id: str) -> AiTask | None:
    for task in CANONICAL_TASKS:
        if task.task_id == task_id:
            return task
    return None


def action_is_forbidden(action: str) -> bool:
    """True for canonical mutate verbs and any sibling under those prefixes."""
    if action in FORBIDDEN_ACTIONS:
        return True
    prefix = action.split(".", 1)[0]
    return prefix in _FORBIDDEN_ACTION_PREFIXES


def catalog_from_mapping(payload: Mapping[str, Any]) -> tuple[AiTask, ...]:
    """Parse an untrusted catalog payload; never grant extra actions."""
    tasks: list[AiTask] = []
    for item in payload.get("tasks") or ():
        if not isinstance(item, Mapping):
            continue
        task_id = str(item.get("task_id") or "")
        known = task_by_id(task_id)
        if known is None:
            continue
        tasks.append(known)
    return tuple(tasks) if tasks else CANONICAL_TASKS
