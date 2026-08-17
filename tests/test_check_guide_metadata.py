import tempfile
import unittest
from pathlib import Path

from scripts.check_guide_metadata import (
    parse_timecode_range,
    validate_guide_file,
)


VALID_ARTICLE = """---
template: guide.html
guide_number: 1
description: Короткий лид статьи.
author: Dr DozA
source_title: Исходный ролик
source_url: https://www.youtube.com/watch?v=dQw4w9WgXcQ
video_id: dQw4w9WgXcQ
---
# Настройки и плавный старт

## Этап 1. Подготовка

### 1. Первый шаг {.guide-step data-level="Не важен" data-timecode="00:00–01:45"}

Текст шага.

## Итоги

Краткий итог.
"""


class ParseTimecodeRangeTests(unittest.TestCase):
    def test_parses_minutes_and_seconds(self):
        self.assertEqual(parse_timecode_range("01:45–02:22"), (105, 142))

    def test_parses_single_start(self):
        self.assertEqual(parse_timecode_range("1:02:03"), (3723, None))

    def test_rejects_invalid_seconds(self):
        with self.assertRaises(ValueError):
            parse_timecode_range("01:75–02:22")


class ValidateGuideFileTests(unittest.TestCase):
    def validate(self, source: str, filename: str = "01-example.md") -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, filename)
            path.write_text(source, encoding="utf-8")
            return validate_guide_file(path)

    def test_accepts_complete_article(self):
        self.assertEqual(self.validate(VALID_ARTICLE), [])

    def test_rejects_guide_number_in_h1(self):
        errors = self.validate(VALID_ARTICLE.replace(
            "# Настройки и плавный старт",
            "# Гайд №1: Настройки и плавный старт",
        ))
        self.assertTrue(any("номер гайда" in error for error in errors))

    def test_rejects_visible_level_and_timecode(self):
        source = VALID_ARTICLE.replace(
            "Текст шага.",
            "- **Уровень основы:** 1–10\n- **Таймкод:** 00:00–01:45\n\nТекст шага.",
        )
        errors = self.validate(source)
        self.assertTrue(any("метаданные шага видимы" in error for error in errors))

    def test_rejects_step_without_level(self):
        source = VALID_ARTICLE.replace(' data-level="Не важен"', "")
        errors = self.validate(source)
        self.assertTrue(any("data-level" in error for error in errors))

    def test_rejects_step_without_timecode(self):
        source = VALID_ARTICLE.replace(
            ' data-timecode="00:00–01:45"',
            "",
        )
        errors = self.validate(source)
        self.assertTrue(any("data-timecode" in error for error in errors))

    def test_rejects_filename_number_mismatch(self):
        errors = self.validate(VALID_ARTICLE, filename="02-example.md")
        self.assertTrue(any("имени файла" in error for error in errors))

    def test_rejects_float_guide_number(self):
        source = VALID_ARTICLE.replace("guide_number: 1", "guide_number: 1.0")
        errors = self.validate(source)
        self.assertTrue(any("целым числом" in error for error in errors))

    def test_rejects_boolean_guide_number(self):
        source = VALID_ARTICLE.replace("guide_number: 1", "guide_number: true")
        errors = self.validate(source)
        self.assertTrue(any("целым числом" in error for error in errors))

    def test_rejects_video_id_not_matching_source_url(self):
        source = VALID_ARTICLE.replace(
            "video_id: dQw4w9WgXcQ",
            "video_id: F3S_L8nL_hY",
        )
        errors = self.validate(source)
        self.assertTrue(any("video_id" in error for error in errors))
