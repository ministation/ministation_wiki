import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SITE_NAME = os.getenv("SITE_NAME", "Вики Мини-станции")
SITE_PUBLIC_URL = os.getenv("SITE_PUBLIC_URL", "https://wiki.ministation.ru").rstrip("/")
MAIN_SITE_URL = os.getenv("MAIN_SITE_URL", "https://ministation.ru").rstrip("/")

CONTENT_DIR = Path(os.getenv("CONTENT_DIR", str(BASE_DIR / "content" / "ru")))
DEFAULT_PAGE = os.getenv("DEFAULT_PAGE", "Main_Page")

# Path to SS14 Resources (contains Textures/, Prototypes/, …)
# Example: /home/ss14_user/mini-station-goob/Resources
SS14_RESOURCES = Path(
    os.getenv(
        "SS14_RESOURCES",
        os.getenv("SS14_RESOURCES_PATH", ""),
    )
).expanduser() if os.getenv("SS14_RESOURCES") or os.getenv("SS14_RESOURCES_PATH") else Path("")

SPRITE_CACHE_DIR = Path(os.getenv("SPRITE_CACHE_DIR", str(BASE_DIR / "data" / "sprite_cache")))
SPRITE_SCALE = int(os.getenv("SPRITE_SCALE", "2"))  # pixel-art upscale

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "3000"))

CONTENT_DIR.mkdir(parents=True, exist_ok=True)
SPRITE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
