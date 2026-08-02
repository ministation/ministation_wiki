from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

from tools.config import CONTENT_DIR, MW_ADMIN, MW_DIR, PHP_BIN

SPRITE_RE = re.compile(
    r"\{\{sprite:([^}|]+)(?:\|([^}]+))?\}\}",
    re.IGNORECASE,
)
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

INFOBOX_TEMPLATE = """<div class="wiki-infobox">
{{#if:{{{title|}}}|<div class="wiki-infobox__title">{{{title}}}</div>}}
{{#if:{{{image|}}}|<div class="wiki-infobox__image">{{{image}}}</div>}}
{| class="wiki-infobox__table"
{{#if:{{{отдел|}}}|
! отдел
{{!}} {{{отдел}}}
{{!}}-
}}{{#if:{{{доступ|}}}|
! доступ
{{!}} {{{доступ}}}
{{!}}-
}}{{#if:{{{сложность|}}}|
! сложность
{{!}} {{{сложность}}}
}}
|}
</div>
"""

# 1:1 with ministation.ru home hero; Wiki button → Сайт
MS_HERO_TEMPLATE = """<div class="card hero-card hero-top ms-hero">
<h2 class="hero-brand">Мини<span>-</span>станция</h2>
<span class="tagline">Космическая станция 14</span>
<p class="description">Мини-станция - это некоммерческий, самый безбашенный проект в игре Космическая станция 14, где ты сможешь как вдоволь поучаствовать в эпичных баталиях, так и показать свой ролевой отыгрыш.</p>
<div class="social-links">
<a href="http://cdn.ministation.ru/" target="_blank" rel="noopener" class="link-btn website"><i class="fa-solid fa-cloud"></i> CDN</a>
<a href="https://discord.gg/mini-station" target="_blank" rel="noopener" class="link-btn discord"><i class="fa-brands fa-discord"></i> Discord</a>
<a href="https://t.me/mini_station" target="_blank" rel="noopener" class="link-btn telegram"><i class="fa-brands fa-telegram"></i> Telegram</a>
<a href="https://ministation.ru" target="_blank" rel="noopener" class="link-btn wiki"><i class="fa-solid fa-globe"></i> Сайт</a>
<a href="https://ministation.ru/donate" target="_blank" rel="noopener" class="link-btn boosty"><i class="fa-solid fa-heart"></i> Донат</a>
<a href="https://github.com/ministation/mini-station-goob" target="_blank" rel="noopener" class="link-btn github"><i class="fa-brands fa-github"></i> GitHub</a>
</div>
</div>
"""


def parse_frontmatter(text: str) -> tuple[dict, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta = yaml.safe_load(m.group(1)) or {}
    return meta if isinstance(meta, dict) else {}, text[m.end() :]


def convert_sprites(text: str) -> str:
    def repl(m: re.Match) -> str:
        target = m.group(1).strip()
        opts = m.group(2)
        if opts:
            return "{{#sprite:" + target + "|" + opts + "}}"
        return "{{#sprite:" + target + "}}"

    return SPRITE_RE.sub(repl, text)


def _find_balanced_blocks(text: str, opener: str) -> list[tuple[int, int]]:
    """Return [start, end) spans for {{opener ...}} with nested {{ }} support."""
    spans: list[tuple[int, int]] = []
    lower = text.lower()
    needle = "{{" + opener.lower()
    i = 0
    while True:
        start = lower.find(needle, i)
        if start < 0:
            break
        depth = 0
        j = start
        while j < len(text) - 1:
            if text[j : j + 2] == "{{":
                depth += 1
                j += 2
                continue
            if text[j : j + 2] == "}}":
                depth -= 1
                j += 2
                if depth == 0:
                    spans.append((start, j))
                    break
                continue
            j += 1
        else:
            break
        i = spans[-1][1]
    return spans


def convert_infobox_block(raw: str) -> str:
    # strip {{infobox ... }}
    inner = raw.strip()
    if inner.lower().startswith("{{infobox"):
        inner = inner[len("{{infobox") :]
        if inner.endswith("}}"):
            inner = inner[:-2]
    params: list[str] = []
    for line in inner.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        line = line[1:].strip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        if key == "сложности":
            key = "сложность"
        val = convert_sprites(val.strip())
        params.append(f"{key}={val}")
    return "{{Infobox\n|" + "\n|".join(params) + "\n}}"


def convert_infoboxes(text: str) -> str:
    spans = _find_balanced_blocks(text, "infobox")
    if not spans:
        return text
    parts: list[str] = []
    last = 0
    for start, end in spans:
        parts.append(text[last:start])
        parts.append(convert_infobox_block(text[start:end]))
        last = end
    parts.append(text[last:])
    return "".join(parts)


def md_to_wikitext(body: str) -> str:
    """Convert Markdown-ish body to wikitext; keep wiki constructs intact."""
    placeholders: dict[str, str] = {}

    def stash_spans(src: str, opener: str) -> str:
        spans = _find_balanced_blocks(src, opener)
        if not spans:
            return src
        parts: list[str] = []
        last = 0
        for start, end in spans:
            parts.append(src[last:start])
            key = f"@@MWPH{len(placeholders)}@@"
            placeholders[key] = src[start:end]
            parts.append(key)
            last = end
        parts.append(src[last:])
        return "".join(parts)

    text = stash_spans(body, "infobox")
    # remaining {{sprite:...}} (not inside stashed infobox)
    def stash_sprite(m: re.Match) -> str:
        key = f"@@MWPH{len(placeholders)}@@"
        placeholders[key] = m.group(0)
        return key

    text = SPRITE_RE.sub(stash_sprite, text)

    lines = text.splitlines()
    out: list[str] = []
    in_code = False
    in_table = False
    table_rows: list[list[str]] = []

    def flush_table() -> None:
        nonlocal table_rows, in_table
        if not table_rows:
            in_table = False
            return
        header = table_rows[0]
        out.append('{| class="wikitable"')
        out.append("! " + " !! ".join(header))
        for row in table_rows[1:]:
            out.append("|-")
            out.append("| " + " || ".join(row))
        out.append("|}")
        table_rows = []
        in_table = False

    def parse_table_row(line: str) -> list[str] | None:
        if not line.startswith("|") or line.count("|") < 2:
            return None
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-+:?", c or "") for c in cells):
            return []  # separator
        return cells

    for line in lines:
        if line.strip().startswith("```"):
            if in_table:
                flush_table()
            if in_code:
                out.append("</pre>")
                in_code = False
            else:
                out.append("<pre>")
                in_code = True
            continue
        if in_code:
            out.append(line)
            continue

        row = parse_table_row(line)
        if row is not None:
            if row == []:
                continue
            in_table = True
            table_rows.append(row)
            continue
        if in_table:
            flush_table()

        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()
            out.append(f"{'=' * level} {title} {'=' * level}")
            continue

        list_item = re.match(r"^(\s*)[-*]\s+(.*)$", line)
        if list_item:
            out.append(f"* {list_item.group(2)}")
            continue

        line = re.sub(r"\*\*(.+?)\*\*", r"'''\1'''", line)
        line = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"''\1''", line)
        line = re.sub(r"`([^`]+)`", r"<code>\1</code>", line)
        line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"[\2 \1]", line)

        out.append(line)

    if in_table:
        flush_table()
    if in_code:
        out.append("</pre>")

    text = "\n".join(out)
    for key, raw in placeholders.items():
        if raw.lower().lstrip().startswith("{{infobox"):
            text = text.replace(key, convert_infobox_block(raw))
        else:
            text = text.replace(key, convert_sprites(raw))

    return text.strip() + "\n"


def page_title_from_path(path: Path) -> str:
    return path.stem.replace("_", " ")


def build_page(meta: dict, body: str) -> str:
    wikitext = md_to_wikitext(body)
    cats = meta.get("categories") or []
    if isinstance(cats, str):
        cats = [cats]
    cat_lines = [f"[[Category:{c}]]" for c in cats]
    display = meta.get("title")
    parts = []
    if display:
        parts.append(f"{{{{DISPLAYTITLE:{display}}}}}")
    parts.append(wikitext.rstrip())
    if cat_lines:
        parts.append("")
        parts.extend(cat_lines)
    return "\n".join(parts) + "\n"


def edit_page(title: str, text: str, summary: str = "import from content/ru") -> None:
    cmd = [
        PHP_BIN,
        "maintenance/run.php",
        "edit",
        f"--user={MW_ADMIN}",
        f"--summary={summary}",
        "--no-rc",
        title,
    ]
    print(f"Import: {title}")
    proc = subprocess.run(
        cmd,
        cwd=MW_DIR,
        input=text,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(f"edit failed for {title}: {proc.returncode}")


def ensure_infobox_template() -> None:
    edit_page("Template:Infobox", INFOBOX_TEMPLATE, summary="ensure Infobox template")
    edit_page("Template:MsHero", MS_HERO_TEMPLATE, summary="ensure MiniStation home hero")


def migrate() -> None:
    if not (MW_DIR / "LocalSettings.php").is_file():
        raise SystemExit("MediaWiki is not installed. Run: python -m tools setup")
    if not CONTENT_DIR.is_dir():
        raise SystemExit(f"Content dir missing: {CONTENT_DIR}")

    ensure_infobox_template()
    files = sorted(CONTENT_DIR.glob("*.md"))
    if not files:
        print("No markdown files found.")
        return
    for path in files:
        raw = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(raw)
        title = page_title_from_path(path)
        text = build_page(meta, body)
        edit_page(title, text)
    print(f"Migrated {len(files)} page(s).")


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if argv and argv[0] in ("-h", "--help"):
        print("Usage: python -m tools migrate\nImport content/ru/*.md into MediaWiki.")
        return 0
    migrate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
