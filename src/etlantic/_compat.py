"""Shared 0.15 compatibility helpers for vocabulary migrations."""

from __future__ import annotations

import warnings

_REMOVED_IN = "0.16"


def warn_source_sink_name(
    *,
    legacy_name: str,
    replacement: str,
    used_binding: bool,
    stacklevel: int = 2,
) -> None:
    """Emit a construction-time deprecation for Source/Sink."""
    if used_binding:
        message = (
            f"{legacy_name} and binding= are deprecated in ETLantic 0.15 and will "
            f"be removed in {_REMOVED_IN}. Use {replacement}(asset=...) instead."
        )
    else:
        message = (
            f"{legacy_name} is deprecated in ETLantic 0.15 and will be removed in "
            f"{_REMOVED_IN}. Use {replacement}(asset=...) instead."
        )
    warnings.warn(message, DeprecationWarning, stacklevel=stacklevel)


def warn_binding_kwarg(*, stacklevel: int = 2) -> None:
    """Emit a construction-time deprecation for binding= on Extract/Load."""
    warnings.warn(
        "binding= is deprecated in ETLantic 0.15 and will be removed in "
        f"{_REMOVED_IN}. Use asset= instead.",
        DeprecationWarning,
        stacklevel=stacklevel,
    )


def warn_binding_property(*, stacklevel: int = 2) -> None:
    """Emit a deprecation for the public .binding property."""
    warnings.warn(
        ".binding is deprecated in ETLantic 0.15 and will be removed in "
        f"{_REMOVED_IN}. Use .asset instead.",
        DeprecationWarning,
        stacklevel=stacklevel,
    )


def warn_profile_bindings(*, stacklevel: int = 2) -> None:
    """Emit a deprecation for Profile.bindings authoring."""
    warnings.warn(
        "Profile.bindings is deprecated in ETLantic 0.15 and will be removed in "
        f"{_REMOVED_IN}. Use Profile.assets instead.",
        DeprecationWarning,
        stacklevel=stacklevel,
    )


def warn_binding_overrides(*, stacklevel: int = 2) -> None:
    """Emit a deprecation for RunRequest.binding_overrides."""
    warnings.warn(
        "RunRequest.binding_overrides is deprecated in ETLantic 0.15 and will be "
        f"removed in {_REMOVED_IN}. Use asset_overrides instead.",
        DeprecationWarning,
        stacklevel=stacklevel,
    )


def resolve_asset_identifier(
    *,
    asset: str | None,
    binding: str | None,
    warn: bool,
    stacklevel: int = 2,
) -> str:
    """Normalize asset=/binding= into a non-empty logical asset identifier."""
    if asset is not None and binding is not None:
        raise TypeError(
            "Specify either asset= or binding=, not both. "
            "Prefer asset=; binding= is deprecated and will be removed in 0.16."
        )
    if asset is None and binding is None:
        raise TypeError("Extract/Load require asset= (binding= is deprecated).")
    if binding is not None:
        if warn:
            warn_binding_kwarg(stacklevel=stacklevel + 1)
        value = binding
    else:
        value = asset
    assert value is not None
    text = str(value).strip()
    if not text:
        raise ValueError("asset identifiers must be non-empty logical names")
    return text
