import unittest

from scripts.check_markdown_layout import find_missing_blank_lines


class FindMissingBlankLinesTests(unittest.TestCase):
    def test_detects_numbered_list_joined_to_paragraph(self):
        markdown = "Инструкция:\n1. Первый шаг\n2. Второй шаг\n"

        self.assertEqual(find_missing_blank_lines(markdown), [2])

    def test_detects_bulleted_list_joined_to_paragraph(self):
        markdown = "Награды:\n- Серебро\n- Купон\n"

        self.assertEqual(find_missing_blank_lines(markdown), [2])

    def test_allows_list_separated_from_paragraph(self):
        markdown = "Инструкция:\n\n1. Первый шаг\n2. Второй шаг\n"

        self.assertEqual(find_missing_blank_lines(markdown), [])

    def test_ignores_list_markers_inside_fenced_code(self):
        markdown = "```markdown\nТекст:\n1. Это пример\n```\n"

        self.assertEqual(find_missing_blank_lines(markdown), [])

    def test_allows_top_level_item_after_nested_list_item(self):
        markdown = "2. Настройки:\n   - Первый параметр\n   - Второй параметр\n3. Сохранить\n"

        self.assertEqual(find_missing_blank_lines(markdown), [])


if __name__ == "__main__":
    unittest.main()
