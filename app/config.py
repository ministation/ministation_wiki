from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SITE_NAME = os.getenv("SITE_NAME", "Вики Мини-станции")

SS14_RESOURCES = (
    Path(
        os.getenv(
            "SS14_RESOURCES",
            os.getenv("SS14_RESOURCES_PATH", ""),
        )
    ).expanduser()
    if os.getenv("SS14_RESOURCES") or os.getenv("SS14_RESOURCES_PATH")
    else Path("")
)

SPRITE_CACHE_DIR = Path(os.getenv("SPRITE_CACHE_DIR", str(BASE_DIR / "data" / "sprite_cache")))
SPRITE_SCALE = int(os.getenv("SPRITE_SCALE", "2"))

HOST = os.getenv("SPRITE_HOST", os.getenv("HOST", "127.0.0.1"))
PORT = int(os.getenv("SPRITE_PORT", "3001"))

SPRITE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
