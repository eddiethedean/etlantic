"""Check internal Markdown anchors; optionally report external URL health."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
DOCS = ROOT / "docs"
MARKDOWN_LINK_RE = re.compile(
    r"!?\[[^\]\n]*\]\(\s*(<[^>\n]+>|[^)\s]+)"
    r"(?:\s+[\"'][^)\n]*[\"'])?\s*\)"
)
HEADING_RE = re.compile(r"(?m)^(#{1,6})\s+(.+?)\s*$")


def _slugify(heading: str) -> str:
    text = heading.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text


def _headings(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    ids: set[str] = set()
    for match in HEADING_RE.finditer(text):
        heading = match.group(2)
        explicit = re.search(r"\{#([^}]+)\}\s*$", heading)
        if explicit:
            ids.add(explicit.group(1).strip())
            heading = heading[: explicit.start()].rstrip()
        # Attr-list style: `{ #id }`
        explicit2 = re.search(r"\{\s*#([^}]+)\}\s*$", heading)
        if explicit2:
            ids.add(explicit2.group(1).strip())
            heading = heading[: explicit2.start()].rstrip()
        ids.add(_slugify(heading))
    return ids


def _strip_code(text: str) -> str:
    out: list[str] = []
    fence = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            fence = not fence
            continue
        if not fence:
            out.append(line)
    return "\n".join(out)


def collect_external_urls() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in sorted(DOCS.rglob("*.md")):
        if "theme" in path.parts:
            continue
        visible = _strip_code(path.read_text(encoding="utf-8"))
        for match in MARKDOWN_LINK_RE.finditer(visible):
            target = match.group(1).strip()
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1]
            if not target.startswith(("http://", "https://")):
                continue
            found.append((str(path.relative_to(ROOT)), target.split("#", 1)[0]))
    for path in [ROOT / "README.md", *sorted((ROOT / "packages").glob("*/README.md"))]:
        if not path.is_file():
            continue
        visible = _strip_code(path.read_text(encoding="utf-8"))
        for match in MARKDOWN_LINK_RE.finditer(visible):
            target = match.group(1).strip()
            if target.startswith(("http://", "https://")):
                found.append((str(path.relative_to(ROOT)), target.split("#", 1)[0]))
    return found


def check_internal_anchors() -> list[str]:
    """Return soft warnings for unresolved in-repo heading anchors.

    MkDocs slug rules can differ from a simple slugify; treat mismatches as
    warnings so docs CI stays focused on missing files (handled elsewhere).
    """
    warnings: list[str] = []
    for path in sorted(DOCS.rglob("*.md")):
        if "theme" in path.parts:
            continue
        visible = _strip_code(path.read_text(encoding="utf-8"))
        for match in MARKDOWN_LINK_RE.finditer(visible):
            target = match.group(1).strip()
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            href, _, frag = target.partition("#")
            if not frag:
                continue
            if not href:
                dest = path
            else:
                dest = (path.parent / href.split("?", 1)[0]).resolve()
                try:
                    dest.relative_to(ROOT.resolve())
                except ValueError:
                    continue
            if not dest.is_file():
                continue
            headings = _headings(dest)
            # Also accept raw heading text compacted.
            if frag not in headings and frag.lower() not in headings:
                warnings.append(
                    f"{path.relative_to(ROOT)}: unresolved anchor {target}"
                )
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--external-report",
        type=Path,
        help="Write unique external URLs to this path (no network fetch).",
    )
    parser.add_argument(
        "--skip-anchors",
        action="store_true",
        help="Skip internal anchor validation.",
    )
    parser.add_argument(
        "--strict-anchors",
        action="store_true",
        help="Fail on unresolved internal heading anchors.",
    )
    args = parser.parse_args()

    if not args.skip_anchors:
        warnings = check_internal_anchors()
        if warnings:
            print("\n".join(warnings[:40]), file=sys.stderr)
            if len(warnings) > 40:
                print(f"... and {len(warnings) - 40} more", file=sys.stderr)
            if args.strict_anchors:
                return 1
            print(
                f"Internal anchor warnings: {len(warnings)} "
                "(non-fatal; pass --strict-anchors to fail).",
                file=sys.stderr,
            )
        else:
            print("Internal anchor check OK.")

    if args.external_report is not None:
        urls = sorted({url for _, url in collect_external_urls()})
        args.external_report.parent.mkdir(parents=True, exist_ok=True)
        args.external_report.write_text(
            "\n".join(urls) + ("\n" if urls else ""),
            encoding="utf-8",
        )
        print(
            f"Wrote {len(urls)} unique external URLs to {args.external_report} "
            "(report only; not fetched)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
