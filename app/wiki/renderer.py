from __future__ import annotations

import html
import re
from urllib.parse import quote

import markdown
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from markdown.inlinepatterns import InlineProcessor
import xml.etree.ElementTree as etree

from app.wiki.store import slugify

# [[Page]] or [[Page|label]]
WIKI_LINK_RE = r"\[\[([^\]|#]+)(?:\|([^\]]+))?\]\]"

# {{sprite:path/to/file.rsi/state}} optional |frame=N|dir=N|scale=N
SPRITE_RE = re.compile(
    r"\{\{sprite:([^}|]+)(?:\|([^}]+))?\}\}",
    re.IGNORECASE,
)

# {{infobox\n| title = X\n| image = {{sprite:...}}\n| key = value\n}}
INFOBOX_RE = re.compile(r"\{\{infobox\s*(.*?)\}\}", re.IGNORECASE | re.DOTALL)


def _parse_sprite_opts(raw: str | None) -> dict[str, str]:
    opts: dict[str, str] = {}
    if not raw:
        return opts
    for part in raw.split("|"):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            opts[k.strip().lower()] = v.strip()
        else:
            opts[part.lower()] = "1"
    return opts


def expand_sprites(text: str) -> str:
    def repl(m: re.Match) -> str:
        target = m.group(1).strip()
        opts = _parse_sprite_opts(m.group(2))
        qs = []
        if "frame" in opts:
            qs.append(f"frame={quote(opts['frame'])}")
        if "dir" in opts:
            qs.append(f"dir={quote(opts['dir'])}")
        if "scale" in opts:
            qs.append(f"scale={quote(opts['scale'])}")
        q = ("?" + "&".join(qs)) if qs else ""
        src = f"/sprite/{quote(target, safe='/')}{q}"
        alt = html.escape(opts.get("alt") or target.split("/")[-1])
        cls = "wiki-sprite"
        if opts.get("pixel") != "0":
            cls += " wiki-sprite--pixel"
        return (
            f'<img class="{cls}" src="{html.escape(src)}" alt="{alt}" '
            f'loading="lazy" decoding="async" />'
        )

    return SPRITE_RE.sub(repl, text)


def expand_infoboxes(text: str) -> str:
    def repl(m: re.Match) -> str:
        block = m.group(1)
        rows: list[tuple[str, str]] = []
        title = ""
        image_html = ""
        for line in block.splitlines():
            line = line.strip()
            if not line.startswith("|"):
                continue
            line = line[1:].strip()
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip().lower()
            val = val.strip()
            if key in ("title", "name"):
                title = val
            elif key in ("image", "sprite", "icon"):
                image_html = expand_sprites(val) if "{{sprite" in val.lower() else val
            else:
                rows.append((key.replace("_", " ").title(), expand_sprites(val)))
        parts = ['<aside class="wiki-infobox">']
        if title:
            parts.append(f'<div class="wiki-infobox__title">{html.escape(title)}</div>')
        if image_html:
            parts.append(f'<div class="wiki-infobox__image">{image_html}</div>')
        if rows:
            parts.append('<table class="wiki-infobox__table">')
            for k, v in rows:
                parts.append(
                    f"<tr><th>{html.escape(k)}</th><td>{v}</td></tr>"
                )
            parts.append("</table>")
        parts.append("</aside>")
        return "\n".join(parts)

    return INFOBOX_RE.sub(repl, text)


class WikiLinkInlineProcessor(InlineProcessor):
    def handleMatch(self, m, data):  # noqa: N802
        target = m.group(1).strip()
        label = (m.group(2) or target).strip()
        slug = slugify(target)
        el = etree.Element("a")
        el.set("href", f"/wiki/{slug}")
        el.set("class", "wiki-link")
        el.text = label
        return el, m.start(0), m.end(0)


class WikiLinkExtension(Extension):
    def extendMarkdown(self, md):
        md.inlinePatterns.register(
            WikiLinkInlineProcessor(WIKI_LINK_RE, md),
            "wiki-link",
            175,
        )


class SpritePreprocessor(Preprocessor):
    def run(self, lines):
        text = "\n".join(lines)
        text = expand_infoboxes(text)
        text = expand_sprites(text)
        return text.split("\n")


class SpriteExtension(Extension):
    def extendMarkdown(self, md):
        md.preprocessors.register(SpritePreprocessor(md), "wiki-sprite", 25)


def render_markdown(source: str) -> str:
    raw = expand_infoboxes(source)
    raw = expand_sprites(raw)
    return markdown.markdown(
        raw,
        extensions=[
            "fenced_code",
            "tables",
            "toc",
            "sane_lists",
            "smarty",
            "attr_list",
            WikiLinkExtension(),
            "pymdownx.superfences",
            "pymdownx.tilde",
        ],
        output_format="html5",
    )
