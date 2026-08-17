import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from mkdocs.commands.build import build
from mkdocs.config import load_config


GUIDES = {
    "01-start": {
        "number": "1",
        "title": "Настройки, плавный старт и аккаунт с нуля",
        "source_title": "№1 ГАЙД ДЛЯ НОВИЧКОВ 2026 Настройки, Плавный старт. Аккаунт с нуля",
        "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "video_id": "dQw4w9WgXcQ",
        "author": "Dr DozA",
        "steps": 23,
    },
    "02-horses": {
        "number": "2",
        "title": "Гильдия, питомцы, твины и выбор лучшего коня",
        "source_title": "№2 ГАЙД ДЛЯ НОВИЧКОВ 2026 Гильдия и Заработок, Во Пико Какого коня взять",
        "source_url": "https://www.youtube.com/watch?v=F3S_L8nL_hY",
        "video_id": "F3S_L8nL_hY",
        "author": "Dr DozA",
        "steps": 17,
    },
    "03-plants": {
        "number": "3",
        "title": "Огороды и повышение параметров персонажа",
        "source_title": "№3 ГАЙД ДЛЯ НОВИЧКОВ 2026 Огороды и Повышение параметров персонажа в БДО",
        "source_url": "https://www.youtube.com/watch?v=Fq24n8O0YkE",
        "video_id": "Fq24n8O0YkE",
        "author": "Dr DozA",
        "steps": 16,
    },
    "04-magnus": {
        "number": "4",
        "title": "Магнус, горничные и Кальфеонская цепочка квестов",
        "source_title": "№4 ГАЙД ДЛЯ НОВИЧКОВ 2026 Магнус 2026. Горничные, Кальфеонская цепочка кв в БДО",
        "source_url": "https://www.youtube.com/watch?v=8d5ZnxDFXZk",
        "video_id": "8d5ZnxDFXZk",
        "author": "Dr DozA",
        "steps": 9,
    },
}

VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


class StructureParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.attrs = []
        self.h1_count = 0
        self.h1_text = []
        self.step_ids = []
        self.toc_hrefs = []
        self.byline_anchors = []
        self.byline_text = []
        self.series_anchors = []
        self.series_text = []
        self.stylesheets = []
        self.scripts = []
        self.visible_text = []
        self._heading = None
        self._open_anchors = []
        self._element_stack = []
        self._toc_depth = 0
        self._ignored_text_depth = 0

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        self.attrs.append((tag, values))
        classes = values.get("class", "").split()
        parent = self._element_stack[-1] if self._element_stack else {}
        in_byline = parent.get("in_byline", False) or "guide-byline" in classes
        in_series = parent.get("in_series", False) or "data-guide-series" in values
        series_role = parent.get("series_role", "other")
        if "guide-series__next" in classes:
            series_role = "next"
        elif "guide-series__secondary" in classes:
            series_role = "secondary"

        if tag in {"script", "style"}:
            self._ignored_text_depth += 1

        if tag == "h1":
            self.h1_count += 1
            self._heading = []

        if tag == "h3" and "guide-step" in classes:
            self.step_ids.append(values.get("id"))

        if tag == "ol":
            if self._toc_depth:
                self._toc_depth += 1
            elif "data-guide-step-list" in values:
                self._toc_depth = 1

        if tag == "a":
            anchor = {
                "href": values.get("href"),
                "text": [],
                "in_byline": in_byline,
                "in_series": in_series,
                "series_role": series_role,
            }
            self._open_anchors.append(anchor)
            if self._toc_depth:
                self.toc_hrefs.append(values.get("href"))

        if tag == "link" and "stylesheet" in values.get("rel", "").split():
            self.stylesheets.append(values.get("href"))
        if tag == "script" and values.get("src"):
            self.scripts.append(values["src"])

        if tag not in VOID_ELEMENTS:
            self._element_stack.append(
                {
                    "tag": tag,
                    "in_byline": in_byline,
                    "in_series": in_series,
                    "series_role": series_role,
                }
            )

    def handle_endtag(self, tag):
        if tag == "h1" and self._heading is not None:
            self.h1_text.append(" ".join("".join(self._heading).split()))
            self._heading = None

        if tag == "a" and self._open_anchors:
            anchor = self._open_anchors.pop()
            rendered_anchor = {
                "href": anchor["href"],
                "text": " ".join("".join(anchor["text"]).split()),
            }
            if anchor["in_byline"]:
                self.byline_anchors.append(rendered_anchor)
            if anchor["in_series"]:
                self.series_anchors.append(
                    {**rendered_anchor, "role": anchor["series_role"]}
                )

        if tag == "ol" and self._toc_depth:
            self._toc_depth -= 1

        if tag in {"script", "style"}:
            self._ignored_text_depth -= 1

        if self._element_stack:
            matching_index = next(
                (
                    index
                    for index in range(len(self._element_stack) - 1, -1, -1)
                    if self._element_stack[index]["tag"] == tag
                ),
                None,
            )
            if matching_index is not None:
                del self._element_stack[matching_index:]

    def handle_data(self, data):
        if self._heading is not None:
            self._heading.append(data)
        if self._open_anchors:
            self._open_anchors[-1]["text"].append(data)
        scope = self._element_stack[-1] if self._element_stack else {}
        if scope.get("in_byline"):
            self.byline_text.append(data)
        if scope.get("in_series"):
            self.series_text.append(data)
        if not self._ignored_text_depth:
            self.visible_text.append(data)

    def elements_with_attribute(self, name):
        return [(tag, attrs) for tag, attrs in self.attrs if name in attrs]


class GuideRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        config = load_config(
            config_file="mkdocs.yml",
            site_dir=cls.temp.name,
            strict=True,
        )
        build(config)

        cls.guide_slugs = sorted(
            source.stem
            for source in Path("docs/guide").glob("*.md")
            if source.name != "index.md"
        )
        cls.pages = {}
        for slug in cls.guide_slugs:
            html = Path(
                cls.temp.name, "guide", slug, "index.html"
            ).read_text(encoding="utf-8")
            parser = StructureParser()
            parser.feed(html)
            cls.pages[slug] = (html, parser)

    def test_discovers_every_guide_article(self):
        self.assertEqual(set(self.guide_slugs), set(GUIDES))
        self.assertNotIn("index", self.guide_slugs)

    def test_each_guide_renders_one_unnumbered_h1(self):
        for slug, (_, parser) in self.pages.items():
            with self.subTest(slug=slug):
                self.assertEqual(parser.h1_count, 1)
                if slug in GUIDES:
                    self.assertEqual(parser.h1_text, [GUIDES[slug]["title"]])

    def test_each_guide_renders_one_material_header_component(self):
        for slug, (_, parser) in self.pages.items():
            with self.subTest(slug=slug):
                matches = parser.elements_with_attribute("data-md-component")
                header_components = [
                    (tag, attrs)
                    for tag, attrs in matches
                    if attrs["data-md-component"] == "header"
                ]
                self.assertEqual(len(header_components), 1)
                self.assertEqual(header_components[0][0], "header")

    def test_each_guide_renders_unique_hooks_on_expected_elements(self):
        expected_hooks = {
            "data-guide-page": "div",
            "data-guide-video": "figure",
            "data-guide-step-list": "ol",
            "data-guide-context-level": "output",
            "data-guide-context-timecode": "button",
            "data-guide-series": "section",
        }
        for slug, (_, parser) in self.pages.items():
            with self.subTest(slug=slug):
                elements = {}
                for hook, expected_tag in expected_hooks.items():
                    matches = parser.elements_with_attribute(hook)
                    self.assertEqual(len(matches), 1, hook)
                    self.assertEqual(matches[0][0], expected_tag, hook)
                    elements[hook] = matches[0][1]

                if slug in GUIDES:
                    expected = GUIDES[slug]
                    self.assertEqual(
                        elements["data-guide-page"]["data-guide-number"],
                        expected["number"],
                    )
                    self.assertEqual(
                        elements["data-guide-video"]["data-video-id"],
                        expected["video_id"],
                    )

    def test_each_toc_links_once_to_every_rendered_guide_step(self):
        for slug, (_, parser) in self.pages.items():
            with self.subTest(slug=slug):
                self.assertGreater(len(parser.step_ids), 0)
                self.assertEqual(len(parser.step_ids), len(set(parser.step_ids)))
                self.assertEqual(
                    parser.toc_hrefs,
                    [f"#{step_id}" for step_id in parser.step_ids],
                )
                if slug in GUIDES:
                    self.assertEqual(len(parser.step_ids), GUIDES[slug]["steps"])

    def test_first_guide_links_to_next_two_guides_without_previous(self):
        _, parser = self.pages["01-start"]
        series_text = " ".join("".join(parser.series_text).split())
        self.assertIn("Следующая статья · Гайд №2", series_text)
        self.assertEqual(
            parser.series_anchors,
            [
                {
                    "href": "../02-horses/",
                    "text": "Перейти к следующей статье",
                    "role": "next",
                },
                {
                    "href": "../03-plants/",
                    "text": "После следующей · Гайд №3: Огороды и повышение параметров персонажа →",
                    "role": "secondary",
                },
            ],
        )

    def test_second_guide_links_to_previous_next_and_after_next(self):
        _, parser = self.pages["02-horses"]
        series_text = " ".join("".join(parser.series_text).split())
        self.assertIn("Следующая статья · Гайд №3", series_text)
        self.assertEqual(
            parser.series_anchors,
            [
                {
                    "href": "../03-plants/",
                    "text": "Перейти к следующей статье",
                    "role": "next",
                },
                {
                    "href": "../01-start/",
                    "text": "← Гайд №1: Настройки, плавный старт и аккаунт с нуля",
                    "role": "secondary",
                },
                {
                    "href": "../04-magnus/",
                    "text": "После следующей · Гайд №4: Магнус, горничные и Кальфеонская цепочка квестов →",
                    "role": "secondary",
                },
            ],
        )

    def test_last_guide_renders_end_state_and_only_previous_link(self):
        _, parser = self.pages["04-magnus"]
        series_text = " ".join("".join(parser.series_text).split())
        self.assertIn("Вы дошли до конца опубликованной серии.", series_text)
        self.assertEqual(
            parser.series_anchors,
            [
                {
                    "href": "../03-plants/",
                    "text": "← Гайд №3: Огороды и повышение параметров персонажа",
                    "role": "secondary",
                }
            ],
        )

    def test_each_guide_renders_exact_source_byline(self):
        for slug, expected in GUIDES.items():
            with self.subTest(slug=slug):
                _, parser = self.pages[slug]
                byline_text = " ".join("".join(parser.byline_text).split())
                self.assertEqual(
                    byline_text,
                    (
                        f"По материалам {expected['source_title']}. "
                        f"Автор оригинального гайда: {expected['author']}."
                    ),
                )
                self.assertEqual(
                    parser.byline_anchors,
                    [
                        {
                            "href": expected["source_url"],
                            "text": expected["source_title"],
                        }
                    ],
                )

    def test_each_guide_links_custom_assets(self):
        for slug, (_, parser) in self.pages.items():
            with self.subTest(slug=slug):
                self.assertIn("../../stylesheets/guide.css", parser.stylesheets)
                self.assertIn("../../javascripts/guide-video.js", parser.scripts)
                self.assertIn("../../javascripts/guide-toc.js", parser.scripts)

        for asset in (
            "stylesheets/guide.css",
            "javascripts/guide-video.js",
            "javascripts/guide-toc.js",
        ):
            with self.subTest(asset=asset):
                self.assertTrue(Path(self.temp.name, asset).is_file())

    def test_old_step_metadata_is_not_visible(self):
        for slug, (_, parser) in self.pages.items():
            with self.subTest(slug=slug):
                visible_text = " ".join("".join(parser.visible_text).split())
                self.assertNotIn("Уровень основы:", visible_text)
                self.assertNotIn("Таймкод:", visible_text)
