"""
Import wikitext from remote SS14 MediaWikis (Corvax / Мёртвый Космос).

Examples:
  python -m tools import_remote seed          # download curated seeds
  python -m tools import_remote fetch corvax --category Руководства --limit 40
  python -m tools import_remote fetch mk --titles Руководство для новичков Медицина
  python -m tools import_remote apply         # push content/import → local MW
"""

from __future__ import annotations

import argparse
import json
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

# Content feeds for MiniStation pages (no public source labels on-wiki).
SOURCES: dict[str, dict] = {
    "corvax": {
        "name": "Space Station 14 Вики (Corvax)",
        "api": "https://station14.ru/api.php",
        "view": "https://station14.ru/wiki/",
        "license": "CC-BY-NC-SA",
        "seed_titles": [
            "Офицер СБ",
            "Офицер службы безопасности",
            "Капитан",
            "Глава персонала",
            "Глава службы безопасности",
            "Старший инженер",
            "Научный руководитель",
            "Главный врач",
            "Квартирмейстер",
            "Атмосферный техник",
            "Инженер",
            "Учёный",
            "Врач",
            "Парамедик",
            "Химик",
            "Карготехник",
            "Утилизатор",
            "Повар",
            "Ботаник",
            "Бармен",
            "Клоун",
            "Мим",
            "Священник",
            "Библиотекарь",
            "Ассистент",
            "Технический ассистент",
            "Научный ассистент",
            "Химия",
            "Аномалистика",
            "Аплинк",
            "Газы",
            "Выносливость",
            "Научный отдел",
        ],
        "seed_categories": [
            ("Руководства", 35),
            ("Роли (Corvax)", 40),
            ("Отделы (Corvax)", 20),
        ],
    },
    "mk": {
        "name": "МК14 — Мёртвый Космос",
        "api": "https://wiki.deadspace14.net/api.php",
        "view": "https://wiki.deadspace14.net/",
        "license": "см. исходную вики",
        "seed_titles": [
            "Руководство для новичков",
            "Роли",
            "Стандартные Рабочие Процедуры",
            "Корпоративный Закон",
            "Контрабанда",
            "NanoTrasen",
            "Аплинк",
            "Бумажная работа",
            "Вооружение",
            "Газодинамика",
            "Гости станции",
            "Десятичные коды",
            "Законы синтетиков",
            "Инструменты",
            "Медицина",
            "Особо ценные предметы",
            "Психические заболевания",
            "Химия",
            "Ассистент",
            "Технический ассистент",
        ],
        "seed_categories": [
            ("Стандартные Рабочие Процедуры", 30),
            ("Оружие", 25),
            ("Основная информация", 25),
            ("Лор", 15),
        ],
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
        print(f"  missing/skipped ({len(missing)}): {', '.join(missing[:12])}"
              + ("…" if len(missing) > 12 else ""))
    return pages


def safe_filename(title: str) -> str:
    name = title.replace("/", "__").replace(":", "_").replace("\\", "_")
    name = re.sub(r"[<>\"|?*]", "_", name)
    return name.strip() or "page"


def adapt_wikitext(text: str, source_key: str, title: str) -> str:
    """Normalize remote wikitext for MiniStation (no source attribution)."""
    text = text.strip()
    # Drop footers from earlier import runs
    text = re.sub(
        r"\n*----\s*\n+\s*<small>Источник:[\s\S]*?</small>\s*$",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\n*\[\[Category:Импорт(?:/[^\]]+)?\]\]\s*", "\n", text)
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
    # YAML-ish header for apply step
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
    # unique, preserve order
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
    # unique
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
    for path in files:
        title, body = parse_import_file(path)
        if not body.strip():
            continue
        edit_page(title, body, summary="обновление контента вики Мини-станции")
        n += 1
    print(f"Applied {n} page(s) into MediaWiki.")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        prog="python -m tools import_remote",
        description="Import pages from Corvax (station14.ru) and МК (deadspace14.net).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_seed = sub.add_parser("seed", help="Download curated seed sets from both wikis")
    p_seed.add_argument("sources", nargs="*", help="corvax and/or mk (default: both)")

    p_fetch = sub.add_parser("fetch", help="Fetch specific titles or a category")
    p_fetch.add_argument("source", choices=sorted(SOURCES))
    p_fetch.add_argument("--titles", nargs="*", default=[])
    p_fetch.add_argument("--category", default=None)
    p_fetch.add_argument("--limit", type=int, default=50)

    p_apply = sub.add_parser("apply", help="Push content/import/*.wiki into local MediaWiki")
    p_apply.add_argument("--source", default=None, help="Only apply one source folder")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "seed":
            cmd_seed(args.sources or None)
        elif args.cmd == "fetch":
            cmd_fetch(args.source, args.titles, args.category, args.limit)
        elif args.cmd == "apply":
            cmd_apply(args.source)
        else:
            parser.print_help()
            return 2
    except urllib.error.HTTPError as e:
        print(f"HTTP error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
