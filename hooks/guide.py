from __future__ import annotations

import re
from typing import Any


GUIDE_TEMPLATE = "guide.html"
H1 = re.compile(r"^#[ \t]+(.+?)[ \t]*$")
FENCE = re.compile(r"^( {0,3})(`{3,}|~{3,})([^\r\n]*)$")


def find_h1s(markdown: str) -> list[tuple[int, int, str]]:
    matches = []
    fence: str | None = None
    offset = 0
    for line in markdown.splitlines(keepends=True):
        fence_match = FENCE.match(line.rstrip("\r\n"))
        if fence:
            if (
                fence_match
                and fence_match.group(2)[0] == fence[0]
                and len(fence_match.group(2)) >= len(fence)
                and not fence_match.group(3).strip()
            ):
                fence = None
        elif fence_match:
            marker = fence_match.group(2)
            suffix = fence_match.group(3)
            if marker[0] != "`" or "`" not in suffix:
                fence = marker
        else:
            heading = H1.fullmatch(line.rstrip("\r\n"))
            if heading:
                matches.append((offset, offset + len(line), heading.group(1).strip()))
        offset += len(line)
    return matches


def on_page_markdown(markdown: str, *, page: Any, **_: Any) -> str:
    if page.meta.get("template") != GUIDE_TEMPLATE:
        return markdown
    matches = find_h1s(markdown)
    if len(matches) != 1:
        raise ValueError(f"{page.file.src_uri}: expected exactly one H1")
    start, end, title = matches[0]
    page.meta["title"] = title
    before = markdown[:start].rstrip("\n")
    after = markdown[end:].strip("\n")
    parts = [part for part in (before, after) if part]
    return "\n\n".join(parts) + ("\n" if parts else "")


def on_page_context(
    context: dict[str, Any], *, page: Any, nav: Any, **_: Any
) -> dict[str, Any]:
    if page.meta.get("template") != GUIDE_TEMPLATE:
        return context
    guide_pages = sorted(
        (
            candidate
            for candidate in nav.pages
            if candidate.meta.get("template") == GUIDE_TEMPLATE
        ),
        key=lambda candidate: candidate.meta["guide_number"],
    )
    current = guide_pages.index(page)
    context["guide_series"] = {
        "index": current + 1,
        "total": len(guide_pages),
        "previous": guide_pages[current - 1] if current > 0 else None,
        "next": guide_pages[current + 1] if current + 1 < len(guide_pages) else None,
        "after_next": guide_pages[current + 2] if current + 2 < len(guide_pages) else None,
    }
    return context
