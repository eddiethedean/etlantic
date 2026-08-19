"""Preserve-user-region merge for generated agent guidance files."""

from __future__ import annotations

import re
from dataclasses import dataclass

from etlantic.agents.diagnostics import guide_diagnostic
from etlantic.diagnostics import Diagnostic

_START = re.compile(
    r"<!--\s*etlantic:user-region:start\s+id=(?P<id>[^\s>]+)\s*-->",
    re.IGNORECASE,
)
_END = "<!-- etlantic:user-region:end -->"


@dataclass(frozen=True, slots=True)
class RegionMergeResult:
    text: str
    diagnostics: tuple[Diagnostic, ...]
    preserved: tuple[str, ...]


def extract_user_regions(text: str) -> tuple[dict[str, str], list[Diagnostic]]:
    """Return id → inner text for well-formed user regions."""
    regions: dict[str, str] = {}
    diagnostics: list[Diagnostic] = []
    pos = 0
    while True:
        match = _START.search(text, pos)
        if match is None:
            break
        ident = match.group("id").strip().strip("\"'")
        end = text.find(_END, match.end())
        if end < 0:
            diagnostics.append(
                guide_diagnostic(
                    "malformed_region",
                    f"User region {ident!r} is missing an end marker.",
                    path=("user_region", ident),
                )
            )
            break
        inner = text[match.end() : end]
        if ident in regions:
            diagnostics.append(
                guide_diagnostic(
                    "conflict",
                    f"Duplicate user region id {ident!r}.",
                    path=("user_region", ident),
                )
            )
        regions[ident] = inner
        pos = end + len(_END)
    return regions, diagnostics


def merge_user_regions(
    generated: str,
    existing: str | None,
) -> RegionMergeResult:
    """Keep marked user regions from ``existing`` while replacing generated text.

    If ``generated`` has no placeholders, preserved regions are appended in a
    generated trailer so they are not silently dropped.
    """
    if not existing:
        return RegionMergeResult(generated, (), ())
    regions, diagnostics = extract_user_regions(existing)
    if diagnostics:
        return RegionMergeResult(existing, tuple(diagnostics), ())
    if not regions:
        return RegionMergeResult(generated, (), ())

    merged = generated
    preserved: list[str] = []
    missing_placeholders: list[str] = []
    for ident, inner in regions.items():
        placeholder = f"<!-- etlantic:user-region:start id={ident} -->{inner}{_END}"
        start_token = f"<!-- etlantic:user-region:start id={ident} -->"
        if start_token in merged:
            merged = re.sub(
                rf"<!--\s*etlantic:user-region:start\s+id={re.escape(ident)}\s*-->"
                rf".*?{re.escape(_END)}",
                placeholder,
                merged,
                count=1,
                flags=re.DOTALL | re.IGNORECASE,
            )
            preserved.append(ident)
        else:
            missing_placeholders.append(ident)

    if missing_placeholders:
        trailer = ["", "## User-owned regions", ""]
        for ident in missing_placeholders:
            trailer.append(f"<!-- etlantic:user-region:start id={ident} -->")
            trailer.append(regions[ident].rstrip("\n"))
            trailer.append(_END)
            trailer.append("")
            preserved.append(ident)
        merged = merged.rstrip() + "\n" + "\n".join(trailer)
    if not merged.endswith("\n"):
        merged += "\n"
    return RegionMergeResult(merged, tuple(diagnostics), tuple(preserved))
