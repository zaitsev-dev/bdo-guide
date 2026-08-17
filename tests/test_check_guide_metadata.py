import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.check_guide_metadata import (
    parse_timecode_range,
    validate_guide_directory,
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

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_SCRIPT = REPOSITORY_ROOT / "scripts/check_guide_metadata.py"


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

    def test_rejects_historical_visible_level_label_variants(self):
        for label in (
            "Уровень твинка",
            "Уровень персонажа",
            "Уровень",
        ):
            with self.subTest(label=label):
                source = VALID_ARTICLE.replace(
                    "Текст шага.",
                    f"- **{label}:** 10\n\nТекст шага.",
                )
                errors = self.validate(source)
                self.assertTrue(
                    any("метаданные шага видимы" in error for error in errors)
                )

    def test_does_not_reject_unrelated_level_prose(self):
        source = VALID_ARTICLE.replace(
            "Текст шага.",
            "- **Совет:** уровень доверия важен.\n\n"
            "В тексте можно упомянуть **уровень персонажа**.\n\n"
            "Текст шага.",
        )
        self.assertEqual(self.validate(source), [])

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


class ValidateGuideDirectoryTests(unittest.TestCase):
    def test_rejects_missing_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory, "missing")
            errors = validate_guide_directory(missing)

        self.assertTrue(any("не существует" in error for error in errors))

    def test_rejects_directory_without_guide_articles(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            Path(path, "index.md").write_text("# Гайд\n", encoding="utf-8")
            errors = validate_guide_directory(path)

        self.assertTrue(any("нет статей" in error for error in errors))

    def test_accepts_directory_with_valid_guide_article(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            Path(path, "01-example.md").write_text(
                VALID_ARTICLE,
                encoding="utf-8",
            )
            self.assertEqual(validate_guide_directory(path), [])


class GuideMetadataCliTests(unittest.TestCase):
    def run_validator(self, path: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR_SCRIPT), str(path)],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_returns_zero_for_valid_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            Path(path, "01-example.md").write_text(
                VALID_ARTICLE,
                encoding="utf-8",
            )
            result = self.run_validator(path)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")

    def test_returns_nonzero_for_missing_and_empty_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = (root / "missing", root / "empty")
            paths[1].mkdir()

            for path in paths:
                with self.subTest(path=path.name):
                    result = self.run_validator(path)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertTrue(result.stdout.strip())
