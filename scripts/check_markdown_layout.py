#!/usr/bin/env python3
"""Reject Markdown lists that are joined to the preceding paragraph."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable, Sequence


LIST_MARKER = re.compile(r"^(?:[-+*]|\d+[.)])\s+")
ANY_LIST_MARKER = re.compile(r"^\s*(?:[-+*]|\d+[.)])\s+")
FENCE_MARKER = re.compile(r"^\s*(`{3,}|~{3,})")


def find_missing_blank_lines(markdown: str) -> list[int]:
    """Return line numbers where a top-level list starts after nonblank prose."""

    violations: list[int] = []
    previous_line = ""
    previous_was_list_item = False
    active_fence: str | None = None

    for line_number, line in enumerate(markdown.splitlines(), start=1):
        fence = FENCE_MARKER.match(line)
        if fence:
            marker = fence.group(1)
            if active_fence is None:
                active_fence = marker[0]
            elif marker[0] == active_fence:
                active_fence = None
            previous_line = line
            previous_was_list_item = False
            continue

        is_top_level_list_item = (
            bool(LIST_MARKER.match(line)) if active_fence is None else False
        )
        if (
            is_top_level_list_item
            and previous_line.strip()
            and not previous_was_list_item
        ):
            violations.append(line_number)

        previous_line = line
        previous_was_list_item = (
            bool(ANY_LIST_MARKER.match(line)) if active_fence is None else False
        )

    return violations


def markdown_files(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_dir():
            yield from sorted(path.rglob("*.md"))
        elif path.suffix.lower() == ".md":
            yield path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that Markdown lists are separated from prose by a blank line."
    )
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args(argv)

    failed = False
    for path in markdown_files(args.paths):
        violations = find_missing_blank_lines(path.read_text(encoding="utf-8"))
        for line_number in violations:
            failed = True
            print(
                f"{path}:{line_number}: add a blank line before this Markdown list"
            )

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
