#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import markdown
from mkdocs.utils.meta import get_data


REQUIRED_META = (
    "template",
    "guide_number",
    "description",
    "author",
    "source_title",
    "source_url",
    "video_id",
)
VISIBLE_STEP_META = re.compile(
    r"(?m)^- \*\*(?:Уровень основы|Таймкод):\*\*"
)
GUIDE_NUMBER_IN_TITLE = re.compile(r"(?i)\bгайд\s*№?\s*\d+")
FILENAME_NUMBER = re.compile(r"^(\d{2})-")


def _clock_to_seconds(value: str) -> int:
    parts = value.split(":")
    if len(parts) not in (2, 3) or not all(part.isdigit() for part in parts):
        raise ValueError(f"invalid clock: {value}")
    numbers = [int(part) for part in parts]
    if numbers[-1] > 59 or (len(numbers) == 3 and numbers[-2] > 59):
        raise ValueError(f"invalid clock: {value}")
    if len(numbers) == 2:
        minutes, seconds = numbers
        return minutes * 60 + seconds
    hours, minutes, seconds = numbers
    return hours * 3600 + minutes * 60 + seconds


def parse_timecode_range(value: str) -> tuple[int, int | None]:
    clocks = value.split("–")
    if len(clocks) not in (1, 2):
        raise ValueError(f"invalid timecode range: {value}")
    start = _clock_to_seconds(clocks[0])
    end = _clock_to_seconds(clocks[1]) if len(clocks) == 2 else None
    if end is not None and end <= start:
        raise ValueError(f"timecode end must be after start: {value}")
    return start, end


class HeadingCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.headings: list[tuple[str, dict[str, str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"h1", "h3"}:
            self.headings.append((tag, {key: value or "" for key, value in attrs}))


def _youtube_video_id(source_url: str) -> str | None:
    parsed = urlparse(source_url)
    if parsed.netloc not in {"youtube.com", "www.youtube.com", "youtu.be"}:
        return None
    if parsed.netloc == "youtu.be":
        return parsed.path.lstrip("/") or None
    return parse_qs(parsed.query).get("v", [None])[0]


def validate_guide_file(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    body, meta = get_data(source)
    errors: list[str] = []

    for key in REQUIRED_META:
        if meta.get(key) in (None, ""):
            errors.append(f"{path}: отсутствует front matter `{key}`")

    if meta.get("template") != "guide.html":
        errors.append(f"{path}: template должен быть guide.html")

    guide_number = meta.get("guide_number")
    if type(guide_number) is not int:
        errors.append(f"{path}: guide_number должен быть целым числом")

    match = FILENAME_NUMBER.match(path.name)
    if type(guide_number) is int and match and guide_number != int(match.group(1)):
        errors.append(f"{path}: guide_number не совпадает с номером имени файла")

    if meta.get("video_id") and _youtube_video_id(str(meta.get("source_url", ""))) != meta["video_id"]:
        errors.append(f"{path}: video_id не совпадает с source_url")

    rendered = markdown.markdown(body, extensions=["attr_list", "toc"])
    collector = HeadingCollector()
    collector.feed(rendered)
    h1_headings = [attrs for tag, attrs in collector.headings if tag == "h1"]
    h3_headings = [attrs for tag, attrs in collector.headings if tag == "h3"]

    if len(h1_headings) != 1:
        errors.append(f"{path}: требуется ровно один заголовок #")
    first_h1 = next((line[2:].strip() for line in body.splitlines() if line.startswith("# ")), "")
    if GUIDE_NUMBER_IN_TITLE.search(first_h1):
        errors.append(f"{path}: уберите номер гайда из заголовка #")

    if VISIBLE_STEP_META.search(body):
        errors.append(f"{path}: метаданные шага видимы в потоке текста")

    previous_start = -1
    for index, attrs in enumerate(h3_headings, start=1):
        classes = attrs.get("class", "").split()
        if "guide-step" not in classes:
            errors.append(f"{path}: шаг {index} не имеет класса .guide-step")
        if not attrs.get("data-level"):
            errors.append(f"{path}: шаг {index} не имеет data-level")
        timecode = attrs.get("data-timecode")
        if not timecode:
            errors.append(f"{path}: шаг {index} не имеет data-timecode")
            continue
        try:
            start, _ = parse_timecode_range(timecode)
        except ValueError as error:
            errors.append(f"{path}: шаг {index}: {error}")
            continue
        if start < previous_start:
            errors.append(f"{path}: таймкоды шагов идут не по возрастанию")
        previous_start = start

    if not h3_headings:
        errors.append(f"{path}: статья не содержит шагов ###")
    return errors


def validate_guide_directory(path: Path) -> list[str]:
    files = sorted(path.glob("[0-9][0-9]-*.md"))
    errors = [error for file in files for error in validate_guide_file(file)]
    numbers = []
    for file in files:
        _, meta = get_data(file.read_text(encoding="utf-8"))
        if type(meta.get("guide_number")) is int:
            numbers.append(meta["guide_number"])
    if len(numbers) != len(set(numbers)):
        errors.append(f"{path}: guide_number должен быть уникальным")
    if numbers and sorted(numbers) != list(range(1, max(numbers) + 1)):
        errors.append(f"{path}: guide_number должен быть непрерывным, начиная с 1")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    errors = validate_guide_directory(args.path)
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
