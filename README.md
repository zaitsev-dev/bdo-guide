# BDO Guide

Статический сайт пошагового гайда для новичков Black Desert.

## Локальный запуск

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/check_guide_metadata.py docs/guide
.venv/bin/python -m mkdocs serve
```

## Проверка production-сборки

```bash
.venv/bin/python scripts/check_guide_metadata.py docs/guide
.venv/bin/python scripts/check_markdown_layout.py docs prompts
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m mkdocs build --strict --site-dir site
```

Контент находится в `docs/guide/`. Один ролик соответствует одной Markdown-статье.

Каждая статья использует `template: guide.html` и обязательные front matter-поля `guide_number`, `description`, `author`, `source_title`, `source_url`, `video_id`. Каждый шаг `###` помечается `.guide-step`, `data-level` и `data-timecode`; уровень и таймкод не дублируются в видимом тексте, а выводятся шаблоном статьи.
