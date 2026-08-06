from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

from tools.config import CONTENT_DIR, MW_ADMIN, MW_DIR, MW_LANG, PHP_BIN

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

# Hero is injected on the main page via OutputPageBeforeHTML (tools/setup.py).
# Never put raw <a href> HTML into wikitext — MW shows it as escaped garbage.


def parse_frontmatter(text: str) -> tuple[dict, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    raw = m.group(1)
    try:
        meta = yaml.safe_load(raw) or {}
    except yaml.YAMLError:
        # Titles with unquoted ":" (e.g. Справка: спрайты) break YAML — recover.
        meta = {}
        for line in raw.splitlines():
            if ":" not in line or line.strip().startswith("-"):
                continue
            key, _, val = line.partition(":")
            key, val = key.strip(), val.strip().strip("\"'")
            if not key:
                continue
            if key == "categories":
                continue
            meta[key] = val
        cats = re.findall(r"^\s*-\s+(.+)$", raw, re.M)
        if cats:
            meta["categories"] = [c.strip().strip("\"'") for c in cats]
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


def page_title_from_path(path: Path, meta: dict | None = None) -> str:
    meta = meta or {}
    # Explicit MediaWiki title (for Russian / spaced names)
    for key in ("page", "mw_title"):
        raw = meta.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    stem = path.stem
    # Russian MediaWiki main page is «Заглавная страница», not «Main Page»
    if stem in ("Main_Page", "Main Page", "Заглавная_страница"):
        if MW_LANG.lower().startswith("ru"):
            return "Заглавная страница"
        return "Main Page"
    return stem.replace("_", " ")


def build_page(meta: dict, body: str) -> str:
    wikitext = md_to_wikitext(body)
    # Strip obsolete hero template calls (hero is PHP-injected on main page)
    wikitext = re.sub(r"\{\{\s*MsHero\s*\}\}", "", wikitext, flags=re.I)
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


def migrate(*, seed_remote: bool = False, apply_remote: bool = True) -> None:
    if not (MW_DIR / "LocalSettings.php").is_file():
        raise SystemExit("MediaWiki is not installed. Run: python -m tools setup")
    if not CONTENT_DIR.is_dir():
        raise SystemExit(f"Content dir missing: {CONTENT_DIR}")

    # Refresh LocalSettings.custom (main page title, inline CSS, …)
    try:
        from tools.setup import write_custom_settings_snippet

        write_custom_settings_snippet()
    except Exception as e:  # noqa: BLE001
        print(f"WARNING: could not refresh LocalSettings.custom.php: {e}")

    ensure_infobox_template()
    files = sorted(CONTENT_DIR.glob("*.md"))
    if not files:
        print("No markdown files found.")
    for path in files:
        raw = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(raw)
        title = page_title_from_path(path, meta)
        text = build_page(meta, body)
        edit_page(title, text)

    # Keep English title as redirect for old links / $wgMainPage mistakes
    if MW_LANG.lower().startswith("ru"):
        edit_page(
            "Main Page",
            "#REDIRECT [[Заглавная страница]]\n",
            summary="redirect to Russian main page",
        )

    print(f"Migrated {len(files)} markdown page(s).")

    if seed_remote:
        from tools.import_remote import cmd_seed

        print("\nFetching remote content…")
        cmd_seed()

    from tools.import_remote import IMPORT_DIR, cmd_apply

    wiki_files = list(IMPORT_DIR.rglob("*.wiki")) if IMPORT_DIR.is_dir() else []
    if apply_remote and wiki_files:
        print(f"\nApplying {len(wiki_files)} imported page(s)…")
        cmd_apply()
    elif apply_remote and not wiki_files:
        print(
            "\nNo content/import/*.wiki yet. To pull remote pages:\n"
            "  python -m tools migrate --seed\n"
            "or: python -m tools import_remote seed && python -m tools migrate"
        )


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if argv and argv[0] in ("-h", "--help"):
        print(
            "Usage: python -m tools migrate [--seed] [--no-import]\n"
            "  Import content/ru/*.md into MediaWiki (Заглавная страница + pages).\n"
            "  --seed       also download remote seed pages first\n"
            "  --no-import  skip applying content/import/*.wiki"
        )
        return 0
    seed = "--seed" in argv
    apply_remote = "--no-import" not in argv
    migrate(seed_remote=seed, apply_remote=apply_remote)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
