# Вики Мини-станции (`ministation_wiki`)

Лёгкий движок вики под **Space Station 14** для сервера Мини-станция.

- Страницы — Markdown (как у MediaWiki по духу: инфобоксы, категории, `[[ссылки]]`)
- UI — как на [ministation.ru](https://ministation.ru): Exo 2 + Press Start 2P, янтарный акцент, светлая/тёмная тема
- Спрайты — вырезка кадров из `.rsi` сборки (`Textures/…`)

## Быстрый старт

```bash
cd ministation_wiki
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# укажите путь к Resources вашей сборки:
# SS14_RESOURCES=/home/ss14_user/mini-station-goob/Resources
uvicorn app.main:app --host 127.0.0.1 --port 3000
```

Откройте http://127.0.0.1:3000/

В Caddy для `wiki.ministation.ru` уже заложен прокси на `:3000`.

## Синтаксис страниц

Файлы лежат в `content/ru/*.md`.

```markdown
---
title: Название
categories:
  - Роли
---

{{infobox
| title = Пример
| image = {{sprite:Objects/Weapons/Melee/knife.rsi/icon|scale=3}}
| отдел = Сервис
}}

Текст со [[Jobs|ссылкой на роли]].

{{sprite:Clothing/Uniforms/Jumpsuit/security.rsi/icon|scale=2}}
```

### Спрайты

| Запись | Смысл |
|--------|--------|
| `{{sprite:Path/File.rsi/state}}` | кадр state |
| `\|scale=3` | nearest-neighbor upscale |
| `\|frame=0` | кадр анимации |
| `\|dir=0` | направление (0..directions-1) |

Путь относительно `Resources/Textures/`.

HTTP: `GET /sprite/Objects/Weapons/Melee/knife.rsi/icon?scale=3`

## Структура

```
app/
  main.py           # FastAPI
  wiki/store.py     # файловое хранилище страниц
  wiki/renderer.py  # markdown + wiki-разметка
  sprites/rsi.py    # RSI → PNG cache
content/ru/         # статьи
templates/          # Jinja
static/             # CSS/JS
```

## systemd (пример)

```ini
[Unit]
Description=Mini Station Wiki
After=network.target

[Service]
User=ss14_user
WorkingDirectory=/home/ss14_user/ministation_wiki
EnvironmentFile=/home/ss14_user/ministation_wiki/.env
ExecStart=/home/ss14_user/ministation_wiki/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 3000
Restart=always

[Install]
WantedBy=multi-user.target
```

## Лицензия

Код движка — для проекта Мини-станция. Контент статей и спрайты SS14 подчиняются лицензиям соответствующих репозиториев.
