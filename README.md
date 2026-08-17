# BDO Guide

Статический сайт пошагового гайда для новичков Black Desert.

## Локальный запуск

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m mkdocs serve
```

## Проверка production-сборки

```bash
.venv/bin/python -m mkdocs build --strict --site-dir site
```

Контент находится в `docs/guide/`. Один ролик соответствует одной Markdown-статье.
