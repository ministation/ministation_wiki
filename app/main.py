from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import (
    BASE_DIR,
    DEFAULT_PAGE,
    MAIN_SITE_URL,
    SITE_NAME,
    SITE_PUBLIC_URL,
    SS14_RESOURCES,
)
from app.sprites.rsi import extract_frame
from app.wiki.renderer import render_markdown
from app.wiki.store import list_pages, load_page, pages_by_category, search_pages

app = FastAPI(title=SITE_NAME, docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def _ctx(request: Request, **extra):
    return {
        "request": request,
        "site_name": SITE_NAME,
        "site_url": SITE_PUBLIC_URL,
        "main_site_url": MAIN_SITE_URL,
        "has_sprites": bool(SS14_RESOURCES and Path(SS14_RESOURCES).exists()),
        **extra,
    }


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return RedirectResponse(f"/wiki/{DEFAULT_PAGE}", status_code=302)


@app.get("/wiki", response_class=HTMLResponse)
@app.get("/wiki/", response_class=HTMLResponse)
async def wiki_index(request: Request):
    return RedirectResponse(f"/wiki/{DEFAULT_PAGE}", status_code=302)


@app.get("/wiki/{slug:path}", response_class=HTMLResponse)
async def wiki_page(request: Request, slug: str):
    page = load_page(slug)
    if page is None:
        # try search-ish suggestions
        suggestions = search_pages(slug.replace("_", " "), limit=8)
        return templates.TemplateResponse(
            "missing.html",
            _ctx(
                request,
                slug=slug,
                suggestions=suggestions,
                status_code=404,
            ),
            status_code=404,
        )
    html = render_markdown(page.body)
    related = []
    for cat in page.categories[:2]:
        related.extend(pages_by_category(cat)[:6])
    # dedupe
    seen = {page.slug}
    related_unique = []
    for p in related:
        if p.slug not in seen:
            seen.add(p.slug)
            related_unique.append(p)
    return templates.TemplateResponse(
        "page.html",
        _ctx(
            request,
            page=page,
            content_html=html,
            related=related_unique[:8],
            all_categories=sorted({c for p in list_pages() for c in p.categories}),
        ),
    )


@app.get("/search", response_class=HTMLResponse)
async def search(request: Request, q: str = Query("")):
    hits = search_pages(q) if q.strip() else []
    return templates.TemplateResponse(
        "search.html",
        _ctx(request, query=q, hits=hits),
    )


@app.get("/category/{name}", response_class=HTMLResponse)
async def category(request: Request, name: str):
    pages = pages_by_category(name)
    return templates.TemplateResponse(
        "category.html",
        _ctx(request, category=name, pages=pages),
    )


@app.get("/special/all", response_class=HTMLResponse)
async def all_pages(request: Request):
    pages = list_pages()
    return templates.TemplateResponse(
        "all_pages.html",
        _ctx(request, pages=pages),
    )


@app.get("/sprite/{path:path}")
async def sprite(
    path: str,
    frame: int = Query(0, ge=0),
    direction: int = Query(0, ge=0, alias="dir"),
    scale: int | None = Query(None, ge=1, le=8),
):
    try:
        out = extract_frame(path, frame=frame, direction=direction, scale=scale)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return FileResponse(out, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/health")
async def health():
    return {
        "ok": True,
        "pages": len(list_pages()),
        "sprites": bool(SS14_RESOURCES and Path(SS14_RESOURCES).exists()),
        "resources": str(SS14_RESOURCES) if SS14_RESOURCES else None,
    }
