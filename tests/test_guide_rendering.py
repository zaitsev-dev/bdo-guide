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
        "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "video_id": "dQw4w9WgXcQ",
        "steps": 23,
    },
    "02-horses": {
        "number": "2",
        "title": "Гильдия, питомцы, твины и выбор лучшего коня",
        "source_url": "https://www.youtube.com/watch?v=F3S_L8nL_hY",
        "video_id": "F3S_L8nL_hY",
        "steps": 17,
    },
    "03-plants": {
        "number": "3",
        "title": "Огороды и повышение параметров персонажа",
        "source_url": "https://www.youtube.com/watch?v=Fq24n8O0YkE",
        "video_id": "Fq24n8O0YkE",
        "steps": 16,
    },
    "04-magnus": {
        "number": "4",
        "title": "Магнус, горничные и Кальфеонская цепочка квестов",
        "source_url": "https://www.youtube.com/watch?v=8d5ZnxDFXZk",
        "video_id": "8d5ZnxDFXZk",
        "steps": 9,
    },
}


class StructureParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.attrs = []
        self.h1_count = 0
        self.h1_text = []
        self.step_ids = []
        self.toc_hrefs = []
        self.anchors = []
        self.stylesheets = []
        self.scripts = []
        self.visible_text = []
        self._heading = None
        self._open_anchors = []
        self._toc_depth = 0
        self._ignored_text_depth = 0

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        self.attrs.append((tag, values))

        if tag in {"script", "style"}:
            self._ignored_text_depth += 1

        if tag == "h1":
            self.h1_count += 1
            self._heading = []

        classes = values.get("class", "").split()
        if tag == "h3" and "guide-step" in classes:
            self.step_ids.append(values.get("id"))

        if tag == "ol":
            if self._toc_depth:
                self._toc_depth += 1
            elif "data-guide-step-list" in values:
                self._toc_depth = 1

        if tag == "a":
            anchor = {"href": values.get("href"), "text": []}
            self._open_anchors.append(anchor)
            if self._toc_depth:
                self.toc_hrefs.append(values.get("href"))

        if tag == "link" and "stylesheet" in values.get("rel", "").split():
            self.stylesheets.append(values.get("href"))
        if tag == "script" and values.get("src"):
            self.scripts.append(values["src"])

    def handle_endtag(self, tag):
        if tag == "h1" and self._heading is not None:
            self.h1_text.append(" ".join("".join(self._heading).split()))
            self._heading = None

        if tag == "a" and self._open_anchors:
            anchor = self._open_anchors.pop()
            anchor["text"] = " ".join("".join(anchor["text"]).split())
            self.anchors.append(anchor)

        if tag == "ol" and self._toc_depth:
            self._toc_depth -= 1

        if tag in {"script", "style"}:
            self._ignored_text_depth -= 1

    def handle_data(self, data):
        if self._heading is not None:
            self._heading.append(data)
        if self._open_anchors:
            self._open_anchors[-1]["text"].append(data)
        if not self._ignored_text_depth:
            self.visible_text.append(data)

    def has_attribute(self, name):
        return any(name in attrs for _, attrs in self.attrs)

    def first_attributes_with(self, name):
        return next(attrs for _, attrs in self.attrs if name in attrs)

    def anchor_href(self, text):
        return next(anchor["href"] for anchor in self.anchors if anchor["text"] == text)


class GuideRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        config = load_config(
            config_file="mkdocs.yml",
            site_dir=cls.temp.name,
            strict=True,
        )
        build(config)

        cls.pages = {}
        for slug in GUIDES:
            html = Path(
                cls.temp.name, "guide", slug, "index.html"
            ).read_text(encoding="utf-8")
            parser = StructureParser()
            parser.feed(html)
            cls.pages[slug] = (html, parser)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_each_guide_renders_one_unnumbered_h1(self):
        for slug, expected in GUIDES.items():
            with self.subTest(slug=slug):
                _, parser = self.pages[slug]
                self.assertEqual(parser.h1_count, 1)
                self.assertEqual(parser.h1_text, [expected["title"]])

    def test_each_guide_renders_shell_video_toc_context_and_series_hooks(self):
        required_hooks = {
            "data-guide-page",
            "data-guide-video",
            "data-guide-step-list",
            "data-guide-context-level",
            "data-guide-context-timecode",
            "data-guide-series",
        }
        for slug, expected in GUIDES.items():
            with self.subTest(slug=slug):
                _, parser = self.pages[slug]
                self.assertTrue(all(parser.has_attribute(hook) for hook in required_hooks))
                guide = parser.first_attributes_with("data-guide-page")
                video = parser.first_attributes_with("data-guide-video")
                self.assertEqual(guide["data-guide-number"], expected["number"])
                self.assertEqual(video["data-video-id"], expected["video_id"])

    def test_each_toc_links_once_to_every_rendered_guide_step(self):
        for slug, expected in GUIDES.items():
            with self.subTest(slug=slug):
                _, parser = self.pages[slug]
                self.assertEqual(len(parser.step_ids), expected["steps"])
                self.assertEqual(len(parser.step_ids), len(set(parser.step_ids)))
                self.assertEqual(
                    parser.toc_hrefs,
                    [f"#{step_id}" for step_id in parser.step_ids],
                )

    def test_first_guide_links_to_next_two_guides_without_previous(self):
        html, parser = self.pages["01-start"]
        self.assertIn("Следующая статья · Гайд №2", html)
        self.assertEqual(
            parser.anchor_href("Перейти к следующей статье"),
            "../02-horses/",
        )
        self.assertEqual(
            parser.anchor_href(
                "После следующей · Гайд №3: Огороды и повышение параметров персонажа →"
            ),
            "../03-plants/",
        )
        self.assertNotIn("← Гайд №", html)

    def test_second_guide_links_to_previous_next_and_after_next(self):
        html, parser = self.pages["02-horses"]
        self.assertIn("Следующая статья · Гайд №3", html)
        self.assertEqual(
            parser.anchor_href("← Гайд №1: Настройки, плавный старт и аккаунт с нуля"),
            "../01-start/",
        )
        self.assertEqual(
            parser.anchor_href("Перейти к следующей статье"),
            "../03-plants/",
        )
        self.assertEqual(
            parser.anchor_href(
                "После следующей · Гайд №4: Магнус, горничные и Кальфеонская цепочка квестов →"
            ),
            "../04-magnus/",
        )

    def test_last_guide_renders_end_state_and_only_previous_link(self):
        html, parser = self.pages["04-magnus"]
        self.assertIn("Вы дошли до конца опубликованной серии.", html)
        self.assertEqual(
            parser.anchor_href("← Гайд №3: Огороды и повышение параметров персонажа"),
            "../03-plants/",
        )
        self.assertNotIn("Следующая статья ·", html)
        self.assertNotIn("После следующей ·", html)

    def test_each_guide_links_source_and_custom_assets(self):
        for slug, expected in GUIDES.items():
            with self.subTest(slug=slug):
                _, parser = self.pages[slug]
                hrefs = {anchor["href"] for anchor in parser.anchors}
                self.assertIn(expected["source_url"], hrefs)
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
        for slug in GUIDES:
            with self.subTest(slug=slug):
                _, parser = self.pages[slug]
                visible_text = " ".join("".join(parser.visible_text).split())
                self.assertNotIn("Уровень основы:", visible_text)
                self.assertNotIn("Таймкод:", visible_text)
