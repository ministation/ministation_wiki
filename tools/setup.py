from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from tools.config import (
    CUSTOM_SETTINGS,
    EXT_SRC,
    MW_ADMIN,
    MW_ADMIN_PASS,
    MW_DIR,
    MW_LANG,
    MW_SCRIPT_PATH,
    MW_VERSION,
    PGHOST,
    PGPORT,
    PGUSER,
    PGPASSWORD,
    PHP_BIN,
    SITE_NAME,
    SITE_PUBLIC_URL,
    SKINS_SRC,
    SPRITE_PUBLIC_URL,
    WIKI_DB,
    WIKI_DB_PASS,
    WIKI_DB_SCHEMA,
    WIKI_DB_USER,
)
from tools.db import ensure_database

REQUIRED_PHP_EXTS = ("pdo_pgsql", "pgsql", "intl", "mbstring", "xml", "curl", "json")


def _run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    print("+", " ".join(cmd))
    return subprocess.run(cmd, cwd=cwd, check=check)


def check_php() -> None:
    try:
        ver = subprocess.check_output([PHP_BIN, "-v"], text=True, stderr=subprocess.STDOUT)
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        raise SystemExit(
            f"PHP not found ({PHP_BIN}). Install PHP 8.1+ with pdo_pgsql/intl/mbstring/xml.\n{e}"
        ) from e
    print(ver.splitlines()[0])
    mods = subprocess.check_output([PHP_BIN, "-m"], text=True).lower().splitlines()
    missing = [m for m in REQUIRED_PHP_EXTS if m not in mods]
    if missing:
        raise SystemExit(f"Missing PHP extensions: {', '.join(missing)}")


def download_mediawiki() -> None:
    marker = MW_DIR / "includes" / "MediaWiki.php"
    if marker.is_file():
        print(f"MediaWiki already present at {MW_DIR}")
        return

    major = ".".join(MW_VERSION.split(".")[:2])
    url = f"https://releases.wikimedia.org/mediawiki/{major}/mediawiki-{MW_VERSION}.tar.gz"
    print(f"Downloading {url}…")
    MW_DIR.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tgz = Path(tmp) / "mw.tar.gz"
        urllib.request.urlretrieve(url, tgz)
        with tarfile.open(tgz, "r:gz") as tf:
            tf.extractall(tmp)
        extracted = next(Path(tmp).glob("mediawiki-*"))
        if MW_DIR.exists():
            shutil.rmtree(MW_DIR)
        shutil.move(str(extracted), str(MW_DIR))
    print(f"Extracted MediaWiki {MW_VERSION} → {MW_DIR}")


def link_path(src: Path, dst: Path) -> None:
    src = src.resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not src.is_dir():
        raise SystemExit(f"Missing custom path: {src}")

    if dst.exists() or dst.is_symlink():
        try:
            if dst.resolve() == src:
                print(f"OK link {dst} → {src}")
                return
        except OSError:
            pass
        if dst.is_symlink() or getattr(dst, "is_junction", lambda: False)():
            dst.unlink(missing_ok=True)
        elif dst.is_dir():
            if any(dst.iterdir()):
                raise SystemExit(f"Refusing to replace non-empty directory: {dst}")
            dst.rmdir()
        else:
            dst.unlink()

    try:
        os.symlink(src, dst, target_is_directory=True)
        print(f"Symlink {dst} → {src}")
        return
    except OSError:
        pass

    if sys.platform == "win32":
        _run(["cmd", "/c", "mklink", "/J", str(dst), str(src)])
        print(f"Junction {dst} → {src}")
        return

    raise SystemExit(f"Could not link {dst} → {src}")


def link_custom_components() -> None:
    link_path(SKINS_SRC, MW_DIR / "skins" / "MiniStation")
    link_path(EXT_SRC, MW_DIR / "extensions" / "SS14Sprites")


def install_mediawiki() -> None:
    local_settings = MW_DIR / "LocalSettings.php"
    if local_settings.is_file():
        print("LocalSettings.php already exists — skip install.php")
        return

    server = SITE_PUBLIC_URL
    if "localhost" in server or "127.0.0.1" in server or not server.startswith("http"):
        # local default for first install
        from tools.config import WIKI_HOST, WIKI_PORT

        server = f"http://{WIKI_HOST}:{WIKI_PORT}"

    cmd = [
        PHP_BIN,
        "maintenance/run.php",
        "install",
        f"--dbname={WIKI_DB}",
        f"--dbserver={PGHOST}",
        f"--dbport={PGPORT}",
        "--dbtype=postgres",
        f"--dbuser={WIKI_DB_USER}",
        f"--dbpass={WIKI_DB_PASS}",
        f"--dbschema={WIKI_DB_SCHEMA}",
        f"--installdbuser={PGUSER}",
        f"--lang={MW_LANG}",
        f"--pass={MW_ADMIN_PASS}",
        f"--server={server}",
        f"--scriptpath={MW_SCRIPT_PATH}",
        "--skins=Vector,MonoBook,Timeless",
        SITE_NAME,
        MW_ADMIN,
    ]
    if PGPASSWORD:
        cmd.insert(-2, f"--installdbpass={PGPASSWORD}")

    env = os.environ.copy()
    if PGPASSWORD:
        env["PGPASSWORD"] = PGPASSWORD
    print("+", " ".join(c if "pass" not in c.lower() else c.split("=")[0] + "=***" for c in cmd))
    subprocess.run(cmd, cwd=MW_DIR, check=True, env=env)
    print("MediaWiki installed.")


CUSTOM_MARKER = "# BEGIN ministation_custom"


def write_custom_settings_snippet() -> None:
    """Ensure LocalSettings.php requires our custom overrides."""
    CUSTOM_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    from tools.config import MAIN_SITE_URL, WIKI_HOST, WIKI_PORT

    local_server = f"http://{WIKI_HOST}:{WIKI_PORT}"
    custom = f"""<?php
# Auto-generated / managed by `python -m tools setup`. Safe to edit values.
# Loaded from mediawiki/LocalSettings.php

$wgSitename = {SITE_NAME!r};
$wgLanguageCode = {MW_LANG!r};
$wgServer = getenv('MW_SERVER') ?: {SITE_PUBLIC_URL!r};
if (PHP_SAPI === 'cli-server' || (isset($_SERVER['HTTP_HOST']) && str_contains($_SERVER['HTTP_HOST'], '127.0.0.1'))) {{
    $wgServer = getenv('MW_SERVER') ?: {local_server!r};
}}

$wgScriptPath = {MW_SCRIPT_PATH!r};
$wgArticlePath = "/index.php?title=$1";
$wgDefaultSkin = 'ministation';
$wgDefaultUserOptions['skin'] = 'ministation';

wfLoadSkin('MiniStation');
wfLoadExtension('SS14Sprites');
wfLoadExtension('ParserFunctions');

$wgSS14SpriteServiceUrl = getenv('SPRITE_PUBLIC_URL') ?: {SPRITE_PUBLIC_URL!r};
$wgMainSiteUrl = {MAIN_SITE_URL!r};
$wgEnableUploads = true;
$wgUseInstantCommons = false;
$wgMainPage = 'Main Page';

# Prefer UTF-8 / Russian search niceties
$wgCapitalLinks = true;
"""
    CUSTOM_SETTINGS.write_text(custom, encoding="utf-8")
    print(f"Wrote {CUSTOM_SETTINGS}")

    ls = MW_DIR / "LocalSettings.php"
    if not ls.is_file():
        return
    text = ls.read_text(encoding="utf-8")
    # LocalSettings lives in mediawiki/; config/ is a sibling of mediawiki/
    require_line = (
        f"\n{CUSTOM_MARKER}\n"
        f"require_once dirname( __DIR__ ) . DIRECTORY_SEPARATOR . 'config' "
        f". DIRECTORY_SEPARATOR . 'LocalSettings.custom.php';\n"
        f"# END ministation_custom\n"
    )
    end_token = "# END ministation_custom"
    if CUSTOM_MARKER in text and end_token in text:
        start = text.index(CUSTOM_MARKER)
        end = text.index(end_token, start) + len(end_token)
        text = text[:start].rstrip() + require_line + text[end:]
    else:
        text = text.rstrip() + require_line
    ls.write_text(text, encoding="utf-8")
    print(f"Patched {ls}")


def run_setup() -> None:
    check_php()
    download_mediawiki()
    ensure_database()
    link_custom_components()
    install_mediawiki()
    write_custom_settings_snippet()
    print("\nSetup complete.")
    print("Next: python -m tools migrate")
    print("Then:  python -m tools start")


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if argv and argv[0] in ("-h", "--help"):
        print("Usage: python -m tools setup\nDownload MediaWiki, create DB, install, link skin/ext.")
        return 0
    try:
        run_setup()
    except subprocess.CalledProcessError as e:
        print(f"Command failed with {e.returncode}", file=sys.stderr)
        return e.returncode or 1
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
        if e.args:
            print(e.args[0], file=sys.stderr)
        return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
