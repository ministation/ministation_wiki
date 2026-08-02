"""
Import wikitext from a remote MediaWiki into content/import, then apply to local MW.

Examples:
  python -m tools import_remote seed
  python -m tools import_remote dump remote
  python -m tools import_remote apply --source remote
  python -m tools import_remote fetch remote --titles Капитан
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from tools.config import BASE_DIR, MW_DIR
from tools.migrate import edit_page

UA = "ministation_wiki-import/1.0 (+https://wiki.ministation.ru; content mirror for MiniStation)"
IMPORT_DIR = BASE_DIR / "content" / "import"

# Set REMOTE_WIKI_API (and optional REMOTE_WIKI_VIEW) to enable seed/dump/fetch.
_DEFAULT_API = os.getenv("REMOTE_WIKI_API", "").strip()
_DEFAULT_VIEW = os.getenv("REMOTE_WIKI_VIEW", "").strip()

SOURCES: dict[str, dict] = {
    "remote": {
        "name": "remote wiki",
        "api": _DEFAULT_API,
        "view": _DEFAULT_VIEW,
        "license": "",
        "seed_titles": [
            "Заглавная страница",
            "Шаблон:Mainpage/splash",
            "Шаблон:MainPage/Baby",
            "Шаблон:MainPage/Lore",
            "Шаблон:MainPage/Guides",
            "Шаблон:MainPage/Jobs",
            "Шаблон:MainPage/Antags",
            "Шаблон:MainPage/Items",
            "Шаблон:MainPage/Pepegas",
            "Шаблон:Pageframe",
            "Шаблон:PageButton",
            "Шаблон:PageList",
            "Шаблон:Icon",
            "Шаблон:ColorPaletteStyles",
        ],
        "seed_categories": [],
        "skip_titles": {
            "MediaWiki:Common.css",
            "MediaWiki:Tgui.css",
            "Заглавная страница",
        },
    },
}


@dataclass
class FetchedPage:
    source: str
    title: str
    wikitext: str
    pageid: int | None = None


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def api(source_key: str, **params) -> dict:
    cfg = SOURCES[source_key]
    if not cfg.get("api"):
        raise SystemExit(
            "REMOTE_WIKI_API is not set. Export the remote MediaWiki api.php URL, then retry."
        )
    params.setdefault("format", "json")
    url = cfg["api"] + "?" + urllib.parse.urlencode(params)
    return _http_get_json(url)


def category_titles(source_key: str, category: str, limit: int = 50) -> list[str]:
    title = category if category.startswith("Категория:") else f"Категория:{category}"
    out: list[str] = []
    cont: dict = {}
    while len(out) < limit:
        data = api(
            source_key,
            action="query",
            list="categorymembers",
            cmtitle=title,
            cmlimit=min(50, limit - len(out)),
            cmnamespace=0,
            **cont,
        )
        for m in data.get("query", {}).get("categorymembers", []):
            out.append(m["title"])
        cont = data.get("continue") or {}
        if not cont:
            break
    return out


def fetch_revisions(source_key: str, titles: list[str]) -> list[FetchedPage]:
    """Batch-fetch latest wikitext for titles (chunks of 10)."""
    pages: list[FetchedPage] = []
    missing: list[str] = []
    for i in range(0, len(titles), 10):
        chunk = titles[i : i + 10]
        data = api(
            source_key,
            action="query",
            prop="revisions",
            rvprop="content",
            rvslots="main",
            titles="|".join(chunk),
            redirects=1,
        )
        for page in (data.get("query") or {}).get("pages", {}).values():
            if "missing" in page or "revisions" not in page:
                missing.append(page.get("title", "?"))
                continue
            rev = page["revisions"][0]
            slot = rev.get("slots", {}).get("main", {})
            text = slot.get("*") if slot else rev.get("*")
            if text is None:
                missing.append(page.get("title", "?"))
                continue
            pages.append(
                FetchedPage(
                    source=source_key,
                    title=page["title"],
                    wikitext=text,
                    pageid=page.get("pageid"),
                )
            )
        time.sleep(0.15)
    if missing:
        print(
            f"  missing/skipped ({len(missing)}): {', '.join(missing[:12])}"
            + ("…" if len(missing) > 12 else "")
        )
    return pages


def safe_filename(title: str) -> str:
    name = title.replace("/", "__").replace(":", "_").replace("\\", "_")
    name = re.sub(r"[<>\"|?*]", "_", name)
    return name.strip() or "page"


def adapt_wikitext(text: str, source_key: str, title: str) -> str:
    """Normalize remote wikitext for MiniStation (no source attribution)."""
    text = text.strip()
    text = re.sub(
        r"\n*----\s*\n+\s*<small>Источник:[\s\S]*?</small>\s*$",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\n*\[\[Category:Импорт(?:/[^\]]+)?\]\]\s*", "\n", text)
    # TemplateStyles CSS is bundled in mainpage-widgets.css
    text = re.sub(r"<templatestyles\s+src=\"[^\"]+\"\s*/>\s*", "", text)
    text = re.sub(r"\{\{#seo:[\s\S]*?\}\}\s*", "", text)

    # Scrub foreign Discord invites that often appear in mirrored splash templates
    text = re.sub(
        r"https://discord\.gg/(?!mini-station)[A-Za-z0-9]+",
        "https://discord.gg/mini-station",
        text,
    )
    text = re.sub(
        r"https://discord\.com/channels/[^\s\]]+",
        "https://discord.gg/mini-station",
        text,
    )

    if title == "Шаблон:Mainpage/splash":
        text = re.sub(
            r"https://github\.com/(?!ministation/)[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",
            "https://github.com/ministation/mini-station-goob",
            text,
        )
        text = text.replace(
            "Добро пожаловать на русскую версию вики Paradise Station по игре Space Station 13!",
            "Добро пожаловать на вики Мини-станции по игре Space Station 14!",
        )
        text = text.replace(
            "Наш основной сервер находится по адресу:",
            "Сборка и сервер:",
        )
        text = re.sub(
            r"\[byond://[^\]]+\]",
            "[https://ministation.ru ministation.ru]",
            text,
        )
        text = re.sub(
            r"Основано на официальной вики\s*\[[^\]]+ Paradise Station\]",
            "По сборке [https://github.com/ministation/mini-station-goob mini-station-goob] · Space Station 14",
            text,
        )
        text = text.replace('class="paradise-info-string>', 'class="paradise-info-string">')
    return text.rstrip() + "\n"


def save_page(page: FetchedPage) -> Path:
    dest_dir = IMPORT_DIR / page.source
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"{safe_filename(page.title)}.wiki"
    body = adapt_wikitext(page.wikitext, page.source, page.title)
    meta = {
        "title": page.title,
        "source": page.source,
        "pageid": page.pageid,
    }
    header = (
        "<!-- ministation-import\n"
        + json.dumps(meta, ensure_ascii=False, indent=2)
        + "\n-->\n"
    )
    path.write_text(header + body, encoding="utf-8")
    return path


def collect_seed_titles(source_key: str) -> list[str]:
    cfg = SOURCES[source_key]
    titles: list[str] = list(cfg.get("seed_titles") or [])
    for cat, limit in cfg.get("seed_categories") or []:
        try:
            found = category_titles(source_key, cat, limit=limit)
            print(f"  category {cat}: {len(found)} page(s)")
            titles.extend(found)
        except Exception as e:  # noqa: BLE001
            print(f"  category {cat}: skip ({e})")
    seen: set[str] = set()
    out: list[str] = []
    for t in titles:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def cmd_seed(sources: list[str] | None = None) -> None:
    keys = sources or list(SOURCES)
    for key in keys:
        if key not in SOURCES:
            raise SystemExit(f"Unknown source: {key}")
        print(f"Seeding from {key} ({SOURCES[key]['name']})…")
        titles = collect_seed_titles(key)
        print(f"  fetching {len(titles)} title(s)…")
        pages = fetch_revisions(key, titles)
        for p in pages:
            path = save_page(p)
            print(f"  + {p.title} → {path.relative_to(BASE_DIR)}")
        print(f"Done {key}: saved {len(pages)} page(s)")


def cmd_fetch(
    source_key: str,
    titles: list[str] | None = None,
    category: str | None = None,
    limit: int = 50,
) -> None:
    if source_key not in SOURCES:
        raise SystemExit(f"Unknown source: {source_key}. Choose: {', '.join(SOURCES)}")
    want: list[str] = list(titles or [])
    if category:
        want.extend(category_titles(source_key, category, limit=limit))
    if not want:
        raise SystemExit("Provide --titles and/or --category")
    seen: set[str] = set()
    uniq = []
    for t in want:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    print(f"Fetching {len(uniq)} from {source_key}…")
    pages = fetch_revisions(source_key, uniq)
    for p in pages:
        path = save_page(p)
        print(f"  + {p.title} → {path.relative_to(BASE_DIR)}")


def parse_import_file(path: Path) -> tuple[str, str]:
    raw = path.read_text(encoding="utf-8")
    title = path.stem.replace("__", "/")
    body = raw
    if raw.startswith("<!-- ministation-import"):
        end = raw.find("-->")
        if end > 0:
            block = raw[len("<!-- ministation-import") : end].strip()
            try:
                meta = json.loads(block)
                title = meta.get("title") or title
            except json.JSONDecodeError:
                pass
            body = raw[end + 3 :].lstrip("\n")
    body = adapt_wikitext(body, path.parent.name, title)
    body = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        r"[\2 \1]",
        body,
    )
    return title, body


def all_titles(source_key: str, namespaces: list[int], limit: int | None = None) -> list[str]:
    out: list[str] = []
    for ns in namespaces:
        cont: dict = {}
        while True:
            data = api(
                source_key,
                action="query",
                list="allpages",
                apnamespace=ns,
                aplimit=500,
                **cont,
            )
            for p in data.get("query", {}).get("allpages", []):
                out.append(p["title"])
                if limit is not None and len(out) >= limit:
                    return out
            cont = data.get("continue") or {}
            if not cont:
                break
            time.sleep(0.1)
    return out


def cmd_dump(source_key: str, namespaces: list[int], limit: int | None = None) -> None:
    if source_key not in SOURCES:
        raise SystemExit(f"Unknown source: {source_key}. Choose: {', '.join(SOURCES)}")
    print(f"Listing pages from {source_key} (ns={namespaces})…")
    titles = all_titles(source_key, namespaces, limit=limit)
    print(f"  fetching {len(titles)} title(s)…")
    pages = fetch_revisions(source_key, titles)
    for i, p in enumerate(pages):
        path = save_page(p)
        if len(pages) <= 40 or i % 25 == 0:
            print(f"  + {p.title} → {path.relative_to(BASE_DIR)}")
    print(f"Done dump {source_key}: saved {len(pages)} page(s)")


def cmd_apply(source_filter: str | None = None) -> None:
    if not (MW_DIR / "LocalSettings.php").is_file():
        raise SystemExit("MediaWiki missing. Run: python -m tools setup")
    root = IMPORT_DIR
    if not root.is_dir():
        raise SystemExit("No imports yet. Run: python -m tools import_remote seed")
    files = sorted(root.rglob("*.wiki"))
    if source_filter:
        files = [f for f in files if f.parent.name == source_filter]
    if not files:
        raise SystemExit("No .wiki files to apply")
    n = 0
    skipped = 0
    for path in files:
        title, body = parse_import_file(path)
        if not body.strip():
            continue
        src = path.parent.name
        skip = set((SOURCES.get(src) or {}).get("skip_titles") or ())
        if title in skip:
            skipped += 1
            continue
        if title.endswith("/styles.css"):
            skipped += 1
            continue
        edit_page(title, body, summary="обновление контента вики Мини-станции")
        n += 1
    print(f"Applied {n} page(s) into MediaWiki" + (f" (skipped {skipped})" if skipped else "") + ".")


def cmd_images(source_key: str = "remote") -> None:
    """Upload images from data/remote_images (or data/<source>_images)."""
    img_dir = BASE_DIR / "data" / f"{source_key}_images"
    if source_key == "remote" and not img_dir.is_dir():
        img_dir = BASE_DIR / "data" / "remote_images"
    if not img_dir.is_dir():
        raise SystemExit(f"No images at {img_dir}")
    script = MW_DIR / "maintenance" / "importImages.php"
    if not script.is_file():
        raise SystemExit("MediaWiki missing. Run: python -m tools setup")
    files = [p for p in img_dir.iterdir() if p.is_file()]
    if not files:
        raise SystemExit(f"Empty {img_dir}")
    print(f"Importing {len(files)} image(s) from {img_dir}…")
    import subprocess

    from tools.config import PHP_BIN

    subprocess.run(
        [PHP_BIN, str(script), str(img_dir), "--overwrite"],
        check=False,
        cwd=str(MW_DIR),
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        prog="python -m tools import_remote",
        description="Import pages from a remote MediaWiki into content/import, then apply locally.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_seed = sub.add_parser("seed", help="Download curated seed sets")
    p_seed.add_argument("sources", nargs="*", help="source key(s), default: remote")

    p_fetch = sub.add_parser("fetch", help="Fetch specific titles or a category")
    p_fetch.add_argument("source", choices=sorted(SOURCES))
    p_fetch.add_argument("--titles", nargs="*", default=[])
    p_fetch.add_argument("--category", default=None)
    p_fetch.add_argument("--limit", type=int, default=50)

    p_dump = sub.add_parser("dump", help="Download all pages from namespaces (default: 0+10)")
    p_dump.add_argument("source", choices=sorted(SOURCES))
    p_dump.add_argument(
        "--ns",
        nargs="+",
        type=int,
        default=[0, 10],
        help="MediaWiki namespaces (0=main, 10=Template)",
    )
    p_dump.add_argument("--limit", type=int, default=None, help="Cap number of titles")

    p_apply = sub.add_parser("apply", help="Push content/import/*.wiki into local MediaWiki")
    p_apply.add_argument("--source", default=None, help="Only apply one source folder")

    p_images = sub.add_parser("images", help="Upload data/remote_images into local MW")
    p_images.add_argument("source", nargs="?", default="remote", choices=sorted(SOURCES))

    args = parser.parse_args(argv)
    try:
        if args.cmd == "seed":
            cmd_seed(args.sources or None)
        elif args.cmd == "fetch":
            cmd_fetch(args.source, args.titles, args.category, args.limit)
        elif args.cmd == "dump":
            cmd_dump(args.source, args.ns, args.limit)
        elif args.cmd == "apply":
            cmd_apply(args.source)
        elif args.cmd == "images":
            cmd_images(args.source)
        else:
            parser.print_help()
            return 2
    except urllib.error.HTTPError as e:
        print(f"HTTP error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
