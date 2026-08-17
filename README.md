# BDO Guide

Статический пошаговый гайд для новичков Black Desert на MkDocs Material. Один видеоролик соответствует одной Markdown-статье в `docs/guide/`.

## Добавление статьи

1. Создайте файл `docs/guide/NN-slug.md`, например `docs/guide/05-farm-and-fight.md`.
2. Используйте актуальный шаблон `prompts/video-to-guide-article.md`.
3. Проверьте, что `guide_number` уникален, совпадает с номером файла и продолжает серию без пропусков.
4. Для каждого шага `###` укажите `.guide-step`, `data-level` и `data-timecode`.

Обязательные поля front matter:

```yaml
template: guide.html
guide_number: 5
description: Краткое описание статьи
author: Автор или канал
source_title: Название исходного ролика
source_url: https://www.youtube.com/watch?v=VIDEO_ID
video_id: VIDEO_ID
```

MkDocs автоматически обнаруживает новые Markdown-файлы. Менять `mkdocs.yml` или вручную добавлять статью в навигацию не нужно. Порядок, предыдущая и следующие статьи вычисляются по `guide_number`.

## Первый запуск

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Окружение создаётся один раз. При следующих сборках повторять эти команды не требуется.

## Проверка новой статьи

Сначала убедитесь, что в статьях нет незакрытых редакторских пометок:

```bash
rg -n '<!-- REVIEW:' docs
```

Отсутствие вывода и код возврата `1` означают, что пометок нет.

Затем запустите полный набор проверок:

```bash
.venv/bin/python scripts/check_guide_metadata.py docs/guide
.venv/bin/python scripts/check_markdown_layout.py docs prompts
.venv/bin/python -m unittest discover -s tests -v
node --check docs/javascripts/guide-toc.js
node --check docs/javascripts/guide-video.js
```

Валидатор проверяет обязательные метаданные, последовательность номеров, YouTube ID, атрибуты шагов, таймкоды и отсутствие старых видимых строк уровня/таймкода.

## Собрать сайт

```bash
.venv/bin/python -m mkdocs build --strict --site-dir site
```

Готовый статический сайт появится в `site/`. Этот каталог генерируется автоматически и не должен добавляться в Git.

## Запустить локальный просмотр

```bash
.venv/bin/python -m mkdocs serve --dev-addr 127.0.0.1:8000
```

После запуска доступны:

- главная: <http://127.0.0.1:8000/>;
- новая статья №5: <http://127.0.0.1:8000/guide/05-farm-and-fight/>.

MkDocs автоматически пересобирает сайт после сохранения файлов. Для остановки сервера нажмите `Ctrl+C`.

## Опубликовать

После успешной локальной проверки добавьте только нужные файлы, создайте коммит и отправьте `main`:

```bash
git add docs/guide/05-farm-and-fight.md
git commit -m "docs: add guide 5"
git push origin main
```

Push в `main` запускает `.github/workflows/deploy.yml`: GitHub Actions повторяет проверки, собирает сайт и публикует GitHub Pages.
