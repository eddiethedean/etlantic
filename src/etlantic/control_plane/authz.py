"""Authorization helpers and CP1 non-enumeration disclosure policy.

Policy (frozen for CP1 incubation):

* Deny **outside** the caller's authorized tenant/workspace scope → opaque
  ``not_found`` (HTTP 404). Existence must not leak across tenants/workspaces.
* Deny **inside** an authorized scope when the action is not permitted →
  ``forbidden`` (HTTP 403).
* Explicit ``AuthzDecision.disclosure`` overrides the default mapping when set.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from etlantic.control_plane.errors import ControlPlaneError
from etlantic.control_plane.models import ControlPlaneContext
from etlantic.control_plane.protocols import (
    Authorizer,
    AuthzDecision,
    DefinitionRepository,
)

Disclosure = Literal["not_found", "forbidden"]


def map_deny_disclosure(
    decision: AuthzDecision,
    *,
    resource_in_caller_scope: bool,
) -> Disclosure:
    """Map an authorization deny to opaque ``not_found`` or ``forbidden``.

    Args:
        decision: Deny decision from an authorizer.
        resource_in_caller_scope: True when the resource is known to live in
            the caller's authorized tenant/workspace (for example after a
            prior authorized list). False for cross-scope or unknown existence.

    Returns:
        Disclosure kind to use in the public error envelope.
    """
    if decision.disclosure in ("not_found", "forbidden"):
        return decision.disclosure  # type: ignore[return-value]
    if resource_in_caller_scope:
        return "forbidden"
    return "not_found"


def raise_for_deny(
    decision: AuthzDecision,
    *,
    resource_in_caller_scope: bool,
    detail: str | None = None,
) -> None:
    """Raise a non-enumerating :class:`ControlPlaneError` when denied.

    No-op when ``decision.allowed`` is True.
    """
    if decision.allowed:
        return
    disclosure = map_deny_disclosure(
        decision, resource_in_caller_scope=resource_in_caller_scope
    )
    message = (
        detail
        or decision.reason
        or ("Resource not found" if disclosure == "not_found" else "Forbidden")
    )
    if disclosure == "not_found":
        raise ControlPlaneError.not_found(message)
    raise ControlPlaneError.forbidden(message)


def require_authorized(
    authorizer: Authorizer,
    ctx: ControlPlaneContext,
    action: str,
    resource: str,
    *,
    resource_in_caller_scope: bool = False,
) -> None:
    """Authorize ``action`` on ``resource`` before any store lookup.

    Raises:
        ControlPlaneError: On deny, using the non-enumeration disclosure map.

    Disclosure mapping:
        * ``decision.disclosure == "forbidden"`` → HTTP 403
        * ``decision.disclosure == "not_found"`` → HTTP 404
        * unset disclosure → 403 when ``resource_in_caller_scope`` else 404
    """
    decision = authorizer.authorize(ctx, action, resource)
    raise_for_deny(decision, resource_in_caller_scope=resource_in_caller_scope)


def require_authorized_run(
    authorizer: Authorizer,
    ctx: ControlPlaneContext,
    action: str,
    run_id: str,
    *,
    probe_exists: Any = None,
) -> None:
    """Authorize a run action with ADR in-scope 403 vs cross-scope 404.

    Authz runs first. When denied:

    * explicit ``disclosure=\"forbidden\"`` → 403
    * when the run exists in the caller's scoped store → 403 (in-scope forbid)
    * otherwise → opaque 404 (cross-scope / unknown)

    ``probe_exists`` is a zero-arg callable returning True when the run is
    present in the caller's scope. It is only invoked after a deny so
    cross-scope existence is never disclosed via the store of another tenant.
    """
    resource = f"run:{run_id}"
    decision = authorizer.authorize(ctx, action, resource)
    if decision.allowed:
        return
    if decision.disclosure == "forbidden":
        raise_for_deny(decision, resource_in_caller_scope=True)
        return
    exists = False
    if probe_exists is not None:
        try:
            exists = bool(probe_exists())
        except KeyError:
            exists = False
    if exists:
        raise ControlPlaneError.forbidden(decision.reason or "Forbidden")
    raise_for_deny(decision, resource_in_caller_scope=False)


def authorized_get_definition(
    authorizer: Authorizer,
    repository: DefinitionRepository,
    ctx: ControlPlaneContext,
    definition_id: str,
    *,
    action: str = "definition.read",
) -> Mapping[str, Any]:
    """Authorize then fetch a definition; never lookup on cross-scope deny.

    Cross-scope / unknown denies map to opaque not_found without calling the
    repository. Missing resources after an allow also surface as not_found.
    """
    resource = f"definition:{definition_id}"
    decision = authorizer.authorize(ctx, action, resource)
    if not decision.allowed:
        # Default: treat as out-of-scope / non-enumerating unless authorizer
        # explicitly marks an in-scope action deny via disclosure=forbidden.
        in_scope = decision.disclosure == "forbidden"
        raise_for_deny(decision, resource_in_caller_scope=in_scope)
    try:
        return repository.get(ctx, definition_id)
    except ControlPlaneError:
        raise
    except KeyError as exc:
        raise ControlPlaneError.not_found(
            f"Definition {definition_id!r} not found"
        ) from exc


__all__ = [
    "Disclosure",
    "authorized_get_definition",
    "map_deny_disclosure",
    "raise_for_deny",
    "require_authorized",
    "require_authorized_run",
]
