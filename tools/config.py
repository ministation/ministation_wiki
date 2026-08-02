from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SITE_NAME = os.getenv("SITE_NAME", "Вики Мини-станции")
SITE_PUBLIC_URL = os.getenv("SITE_PUBLIC_URL", "https://wiki.ministation.ru").rstrip("/")
MAIN_SITE_URL = os.getenv("MAIN_SITE_URL", "https://ministation.ru").rstrip("/")

MW_VERSION = os.getenv("MW_VERSION", "1.45.1")
MW_DIR = Path(os.getenv("MW_DIR", str(BASE_DIR / "mediawiki")))
# Optional: path to an already-downloaded mediawiki-*.tar.gz (skips network)
MW_TARBALL = os.getenv("MW_TARBALL", "").strip()
MW_LANG = os.getenv("MW_LANG", "ru")
MW_ADMIN = os.getenv("MW_ADMIN", "Admin")
MW_ADMIN_PASS = os.getenv("MW_ADMIN_PASS", "changeme_admin")
MW_SCRIPT_PATH = os.getenv("MW_SCRIPT_PATH", "")

PGHOST = os.getenv("PGHOST", "127.0.0.1")
PGPORT = int(os.getenv("PGPORT", "5432"))
PGUSER = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "")
WIKI_DB = os.getenv("WIKI_DB", "ministation_wiki")
WIKI_DB_USER = os.getenv("WIKI_DB_USER", "wiki")
WIKI_DB_PASS = os.getenv("WIKI_DB_PASS", "wiki_pass")
WIKI_DB_SCHEMA = os.getenv("WIKI_DB_SCHEMA", "mediawiki")

WIKI_HOST = os.getenv("WIKI_HOST", os.getenv("HOST", "127.0.0.1"))
WIKI_PORT = int(os.getenv("WIKI_PORT", os.getenv("PORT", "3000")))
SPRITE_HOST = os.getenv("SPRITE_HOST", "127.0.0.1")
SPRITE_PORT = int(os.getenv("SPRITE_PORT", "3001"))
_sprite_public_default = (
    f"http://127.0.0.1:{SPRITE_PORT}"
    if SPRITE_HOST in ("0.0.0.0", "::", "")
    else f"http://{SPRITE_HOST}:{SPRITE_PORT}"
)
SPRITE_PUBLIC_URL = os.getenv("SPRITE_PUBLIC_URL", _sprite_public_default).rstrip("/")
MW_SERVER = os.getenv("MW_SERVER", SITE_PUBLIC_URL).rstrip("/")

PHP_BIN = os.getenv("PHP_BIN", "php")
CONTENT_DIR = Path(os.getenv("CONTENT_DIR", str(BASE_DIR / "content" / "ru")))
SKINS_SRC = BASE_DIR / "skins" / "MiniStation"
EXT_SRC = BASE_DIR / "extensions" / "SS14Sprites"
CUSTOM_SETTINGS = BASE_DIR / "config" / "LocalSettings.custom.php"

DEFAULT_PAGE = os.getenv("DEFAULT_PAGE", "Main_Page")
SS14_RESOURCES = os.getenv("SS14_RESOURCES", os.getenv("SS14_RESOURCES_PATH", ""))
