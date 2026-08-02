from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.config import CONTENT_DIR, DEFAULT_PAGE


@dataclass
class WikiPage:
    slug: str
    title: str
    body: str
    categories: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    path: Path | None = None

    @property
    def url(self) -> str:
        return f"/wiki/{self.slug}"


def slugify(name: str) -> str:
    s = name.strip().replace(" ", "_")
    s = re.sub(r"[^\w.\-/]+", "", s, flags=re.UNICODE)
    return s or "Untitled"


def slug_to_path(slug: str) -> Path:
    slug = slug.strip().strip("/")
    if ".." in slug or slug.startswith("/"):
        raise ValueError("bad slug")
    if not slug:
        slug = DEFAULT_PAGE
    # allow nested: Jobs/Security_Officer.md
    return CONTENT_DIR / f"{slug}.md"


def list_pages() -> list[WikiPage]:
    pages: list[WikiPage] = []
    if not CONTENT_DIR.exists():
        return pages
    for path in sorted(CONTENT_DIR.rglob("*.md")):
        rel = path.relative_to(CONTENT_DIR).with_suffix("")
        slug = rel.as_posix()
        pages.append(load_page(slug))
    return [p for p in pages if p is not None]


def load_page(slug: str) -> WikiPage | None:
    try:
        path = slug_to_path(slug)
    except ValueError:
        return None
    if not path.is_file():
        # try Main_Page style fallbacks
        alt = CONTENT_DIR / f"{slug.replace(' ', '_')}.md"
        if alt.is_file():
            path = alt
        else:
            return None
    text = path.read_text(encoding="utf-8")
    meta: dict = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            meta = yaml.safe_load(parts[1]) or {}
            body = parts[2].lstrip("\n")
    title = meta.get("title") or slug.replace("_", " ").split("/")[-1]
    cats = meta.get("categories") or meta.get("category") or []
    if isinstance(cats, str):
        cats = [cats]
    return WikiPage(
        slug=path.relative_to(CONTENT_DIR).with_suffix("").as_posix(),
        title=str(title),
        body=body,
        categories=[str(c) for c in cats],
        meta=meta,
        path=path,
    )


def save_page(slug: str, title: str, body: str, categories: list[str] | None = None) -> WikiPage:
    path = slug_to_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "title": title,
        "categories": categories or [],
    }
    front = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()
    path.write_text(f"---\n{front}\n---\n\n{body.rstrip()}\n", encoding="utf-8")
    return load_page(slug)  # type: ignore[return-value]


def pages_by_category(category: str) -> list[WikiPage]:
    cat = category.strip().lower()
    return [p for p in list_pages() if any(c.lower() == cat for c in p.categories)]


def search_pages(query: str, limit: int = 40) -> list[tuple[WikiPage, str]]:
    q = query.strip().lower()
    if not q:
        return []
    hits: list[tuple[WikiPage, str]] = []
    for page in list_pages():
        blob = f"{page.title}\n{page.body}\n{' '.join(page.categories)}".lower()
        if q not in blob:
            continue
        # snippet
        idx = blob.find(q)
        start = max(0, idx - 60)
        snippet = page.body[start : start + 160].replace("\n", " ")
        hits.append((page, snippet))
        if len(hits) >= limit:
            break
    return hits
