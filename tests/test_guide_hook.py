import unittest
from types import SimpleNamespace

from hooks.guide import on_page_context, on_page_markdown


def page(number, title):
    return SimpleNamespace(
        meta={"template": "guide.html", "guide_number": number, "title": title},
        title=title,
    )


class GuideMarkdownHookTests(unittest.TestCase):
    def test_extracts_h1_into_page_title(self):
        article = page(1, "старое значение")
        result = on_page_markdown(
            "# Настройки и плавный старт\n\n## Этап 1\n",
            page=article,
            config=None,
            files=None,
        )
        self.assertEqual(article.meta["title"], "Настройки и плавный старт")
        self.assertEqual(result, "## Этап 1\n")

    def test_leaves_non_guide_page_unchanged(self):
        article = SimpleNamespace(meta={})
        source = "# Главная\n"
        self.assertEqual(
            on_page_markdown(source, page=article, config=None, files=None),
            source,
        )

    def test_ignores_h1_like_line_inside_fenced_code(self):
        article = page(1, "старое значение")
        article.file = SimpleNamespace(src_uri="guide/01-start.md")
        source = "# Настройки\n\n```markdown\n# Не заголовок\n```\n"
        self.assertEqual(
            on_page_markdown(source, page=article, config=None, files=None),
            "```markdown\n# Не заголовок\n```\n",
        )
        self.assertEqual(article.meta["title"], "Настройки")

    def test_does_not_close_fence_with_text_after_marker(self):
        article = page(1, "старое значение")
        article.file = SimpleNamespace(src_uri="guide/01-start.md")
        source = "# Настройки\n\n```\n``` не закрывает блок\n# Не заголовок\n```\n"
        self.assertEqual(
            on_page_markdown(source, page=article, config=None, files=None),
            "```\n``` не закрывает блок\n# Не заголовок\n```\n",
        )


class GuideSeriesContextTests(unittest.TestCase):
    def test_returns_previous_next_and_after_next(self):
        pages = [page(1, "Один"), page(2, "Два"), page(3, "Три"), page(4, "Четыре")]
        context = on_page_context(
            {},
            page=pages[1],
            config=None,
            nav=SimpleNamespace(pages=pages),
        )
        series = context["guide_series"]
        self.assertEqual(series["index"], 2)
        self.assertEqual(series["total"], 4)
        self.assertIs(series["previous"], pages[0])
        self.assertIs(series["next"], pages[2])
        self.assertIs(series["after_next"], pages[3])

    def test_omits_neighbors_beyond_series_edges(self):
        pages = [page(1, "Один"), page(2, "Два")]
        context = on_page_context(
            {},
            page=pages[1],
            config=None,
            nav=SimpleNamespace(pages=pages),
        )
        self.assertIsNone(context["guide_series"]["next"])
        self.assertIsNone(context["guide_series"]["after_next"])
