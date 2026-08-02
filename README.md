# Вики Мини-станции (`ministation_wiki`)

MediaWiki + PostgreSQL для сервера **Мини-станция** (SS14).

- Движок — **MediaWiki** (страницы, правки, категории)
- БД — **PostgreSQL** (создаётся скриптом)
- Спрайты RSI — отдельный FastAPI-сервис
- Скин **MiniStation** — Exo 2 / Press Start 2P, янтарный акцент, light/dark
- Оркестрация — Python **venv** (`python -m tools …`), без Docker

> MediaWiki — PHP. Venv ставит зависимости Python и запускает CLI; на хосте нужны **PHP 8.5+** (последняя стабильная ветка; `pdo_pgsql`, `pgsql`, `intl`, `mbstring`, `xml`, `curl`, `openssl`) и **PostgreSQL**.

Windows:

```bash
winget install PHP.PHP.8.5
# затем включите extension=pdo_pgsql, pgsql, intl, … в php.ini рядом с php.exe
```

## Быстрый старт

```bash
cd ministation_wiki
python -m venv .venv

# Linux/macOS
source .venv/bin/activate
# Windows
# .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env
# заполните PG* / MW_ADMIN_PASS / SS14_RESOURCES

python -m tools setup     # скачать MW, создать БД, install.php, скин/расширение
python -m tools migrate   # импорт content/ru/*.md
python -m tools start     # MediaWiki :3000 + sprites :3001
```

Откройте http://127.0.0.1:3000/

### Команды

| Команда | Назначение |
|---------|------------|
| `python -m tools setup` | PHP-check, скачать MediaWiki, Postgres role/DB/schema, `install.php`, линки skin/ext |
| `python -m tools db` | только PostgreSQL |
| `python -m tools migrate` | Markdown → wikitext → страницы MW |
| `python -m tools start` | `php -S` + uvicorn спрайтов |

## Спрайты

В статьях MediaWiki:

```
{{#sprite:Objects/Weapons/Melee/knife.rsi/icon|scale=3}}
```

Нужен `SS14_RESOURCES` (папка `Resources` билда со `Textures/`).  
HTTP: `GET http://127.0.0.1:3001/sprite/…`

Публичный URL для картинок задаётся `SPRITE_PUBLIC_URL` (за Caddy обычно `https://wiki.ministation.ru/sprite` или отдельный прокси).

## Структура

```
mediawiki/              # ядро (скачивается setup'ом, в .gitignore)
skins/MiniStation/      # кастомный скин
extensions/SS14Sprites/ # {{#sprite:}}
tools/                  # setup / db / migrate / start
app/                    # FastAPI только /sprite
content/ru/             # исходники для migrate
config/                 # LocalSettings.custom.php (генерирует setup)
```

## systemd

Два unit-файла в `deploy/`:

- `ministation-wiki.service` — MediaWiki (`php -S` или php-fpm + Caddy)
- `ministation-wiki-sprites.service` — uvicorn спрайтов

Пример Caddy: `deploy/Caddyfile.snippet` (вики на `:3000`, `/sprite/*` → `:3001`).

## Лицензия

Код обвязки — для проекта Мини-станция. MediaWiki — GPL. Контент и спрайты SS14 — по лицензиям соответствующих репозиториев.
