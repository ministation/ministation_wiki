---
title: Справка: спрайты
categories:
  - Навигация
  - Справка
---

# Спрайты SS14 в статьях

Текстуры качаются из git:

```
python -m tools sprites
```

В wikitext:

```
{{#sprite:Objects/Weapons/Melee/knife.rsi/icon|scale=3}}
```

| Параметр | Смысл |
|----------|--------|
| путь | относительно `Textures/`, с `.rsi` и именем state |
| `scale=N` | увеличение (nearest-neighbor) |
| `frame=N` | кадр анимации |
| `dir=N` | направление |
| `alt=текст` | alt у картинки |

Примеры:

* {{#sprite:Clothing/Uniforms/Jumpsuit/security.rsi/icon|scale=3}}
* нож: `{{#sprite:Objects/Weapons/Melee/knife.rsi/icon|scale=2}}`

Нужен запущенный сервис спрайтов (`python -m tools start`, порт 3001).
