import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

import markdown
from mkdocs.commands.build import build
from mkdocs.config import load_config
from mkdocs.utils.meta import get_data

from hooks.guide import find_h1s
from scripts.check_guide_metadata import HeadingCollector

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
        self.step_metadata = []
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
            self.step_metadata.append(
                {
                    "level": values.get("data-level"),
                    "timecode": values.get("data-timecode"),
                }
            )

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

        cls.guides = []
        for source in Path("docs/guide").glob("[0-9][0-9]-*.md"):
            body, meta = get_data(source.read_text(encoding="utf-8"))
            titles = find_h1s(body)
            rendered = markdown.markdown(body, extensions=["attr_list", "toc"])
            headings = HeadingCollector()
            headings.feed(rendered)
            cls.guides.append(
                {
                    "slug": source.stem,
                    "number": meta["guide_number"],
                    "title": titles[0][2],
                    "source_title": meta["source_title"],
                    "source_url": meta["source_url"],
                    "video_id": meta["video_id"],
                    "author": meta["author"],
                    "steps": sum(tag == "h3" for tag, _ in headings.headings),
                }
            )
        cls.guides.sort(key=lambda guide: guide["number"])
        cls.guides_by_slug = {guide["slug"]: guide for guide in cls.guides}
        cls.guide_slugs = [guide["slug"] for guide in cls.guides]
        cls.pages = {}
        for slug in cls.guide_slugs:
            html = Path(
                cls.temp.name, "guide", slug, "index.html"
            ).read_text(encoding="utf-8")
            parser = StructureParser()
            parser.feed(html)
            cls.pages[slug] = (html, parser)

    def test_discovers_every_guide_article(self):
        built_slugs = sorted(
            page.parent.name
            for page in Path(self.temp.name, "guide").glob("*/index.html")
        )
        self.assertEqual(built_slugs, sorted(self.guide_slugs))
        self.assertNotIn("index", self.guide_slugs)

    def test_each_guide_renders_one_unnumbered_h1(self):
        for slug, (_, parser) in self.pages.items():
            with self.subTest(slug=slug):
                self.assertEqual(parser.h1_count, 1)
                self.assertEqual(
                    parser.h1_text,
                    [self.guides_by_slug[slug]["title"]],
                )

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

                expected = self.guides_by_slug[slug]
                self.assertEqual(
                    elements["data-guide-page"]["data-guide-number"],
                    str(expected["number"]),
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
                self.assertEqual(
                    len(parser.step_ids),
                    self.guides_by_slug[slug]["steps"],
                )

    def test_second_guide_preserves_valid_level_and_defaults_only_invalid_level(self):
        _, parser = self.pages["02-horses"]
        levels_by_timecode = {
            step["timecode"]: step["level"] for step in parser.step_metadata
        }
        self.assertEqual(levels_by_timecode["14:20–15:50"], "10")
        self.assertEqual(levels_by_timecode["18:40–20:20"], "Не важно")

    def test_each_guide_renders_dynamic_series_navigation(self):
        total = len(self.guides)
        for index, guide in enumerate(self.guides):
            with self.subTest(slug=guide["slug"]):
                _, parser = self.pages[guide["slug"]]
                series_text = " ".join("".join(parser.series_text).split())
                self.assertIn(f"Гайд {index + 1} из {total}", series_text)

                expected_anchors = []
                if index + 1 < total:
                    following = self.guides[index + 1]
                    self.assertIn(
                        f"Следующая статья · Гайд №{following['number']}",
                        series_text,
                    )
                    expected_anchors.append(
                        {
                            "href": f"../{following['slug']}/",
                            "text": "Перейти к следующей статье",
                            "role": "next",
                        }
                    )
                else:
                    self.assertIn(
                        "Вы дошли до конца опубликованной серии.",
                        series_text,
                    )

                if index > 0:
                    previous = self.guides[index - 1]
                    expected_anchors.append(
                        {
                            "href": f"../{previous['slug']}/",
                            "text": (
                                f"← Гайд №{previous['number']}: "
                                f"{previous['title']}"
                            ),
                            "role": "secondary",
                        }
                    )

                if index + 2 < total:
                    after_next = self.guides[index + 2]
                    expected_anchors.append(
                        {
                            "href": f"../{after_next['slug']}/",
                            "text": (
                                f"После следующей · Гайд №{after_next['number']}: "
                                f"{after_next['title']} →"
                            ),
                            "role": "secondary",
                        }
                    )

                self.assertEqual(parser.series_anchors, expected_anchors)

    def test_each_guide_renders_exact_source_byline(self):
        for expected in self.guides:
            with self.subTest(slug=expected["slug"]):
                _, parser = self.pages[expected["slug"]]
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
