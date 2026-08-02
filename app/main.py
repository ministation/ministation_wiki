from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from app.config import SITE_NAME, SS14_RESOURCES
from app.sprites.rsi import extract_frame

app = FastAPI(title=f"{SITE_NAME} sprites", docs_url=None, redoc_url=None)


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
    return FileResponse(
        out,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/health")
async def health():
    return {
        "ok": True,
        "sprites": bool(SS14_RESOURCES and Path(SS14_RESOURCES).exists()),
        "resources": str(SS14_RESOURCES) if SS14_RESOURCES else None,
    }
