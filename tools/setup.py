from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
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
    MW_TARBALL,
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

REQUIRED_PHP_EXTS = (
    "ctype",
    "curl",
    "dom",
    "fileinfo",
    "intl",
    "json",
    "mbstring",
    "openssl",
    "pdo_pgsql",
    "pgsql",
    "xml",
)
MIN_PHP = (8, 4, 0)


def _run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    print("+", " ".join(cmd))
    return subprocess.run(cmd, cwd=cwd, check=check)


def _php_version_tuple() -> tuple[int, int, int]:
    raw = subprocess.check_output(
        [PHP_BIN, "-r", "echo PHP_MAJOR_VERSION,'.',PHP_MINOR_VERSION,'.',PHP_RELEASE_VERSION;"],
        text=True,
    ).strip()
    parts = [int(x) for x in raw.split(".")[:3]]
    while len(parts) < 3:
        parts.append(0)
    return parts[0], parts[1], parts[2]


def check_php() -> None:
    try:
        ver = subprocess.check_output([PHP_BIN, "-v"], text=True, stderr=subprocess.STDOUT)
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        raise SystemExit(
            f"PHP not found ({PHP_BIN}). Install PHP 8.4+ "
            f"(Ubuntu: php8.4-cli + php8.4-pgsql/intl/…; Windows: winget install PHP.PHP.8.4) "
            f"with pdo_pgsql/intl/mbstring/xml/openssl.\n{e}"
        ) from e
    print(ver.splitlines()[0])
    try:
        current = _php_version_tuple()
    except (subprocess.CalledProcessError, ValueError) as e:
        raise SystemExit(f"Could not parse PHP version: {e}") from e
    if current < MIN_PHP:
        raise SystemExit(
            f"PHP {'.'.join(map(str, current))} is too old. "
            f"Need PHP {'.'.join(map(str, MIN_PHP))}+ (8.4.x on Ubuntu Questing is fine)."
        )
    mods = subprocess.check_output([PHP_BIN, "-m"], text=True).lower().splitlines()
    missing = [m for m in REQUIRED_PHP_EXTS if m not in mods]
    if missing:
        raise SystemExit(
            f"Missing PHP extensions: {', '.join(missing)}\n"
            f"Enable them in php.ini next to php.exe (extension=…)."
        )


UA = (
    "ministation_wiki-setup/1.0 "
    "(+https://wiki.ministation.ru; MediaWiki installer)"
)

# curl: 18 partial, 28 timeout, 56 recv failure, 92 HTTP/2 cancel
_CURL_RETRYABLE = {18, 28, 56, 92}
# Real release tarball is ~20–30MB; larger usually means bad Content-Length + appended junk
_MAX_TARBALL_BYTES = 35_000_000


def _which(cmd: str) -> str | None:
    return shutil.which(cmd)


def _tar_ok(path: Path) -> bool:
    try:
        size = path.stat().st_size
        if size < 5_000_000 or size > _MAX_TARBALL_BYTES:
            return False
        with tarfile.open(path, "r:gz") as tf:
            members = tf.getmembers()
        return len(members) > 100
    except (OSError, tarfile.TarError, EOFError):
        return False


def _download_with_curl(url: str, dest: Path) -> None:
    """Fresh downloads only (no -C resume). Wrong Content-Length + resume corrupts the file."""
    attempts = 12
    for i in range(1, attempts + 1):
        dest.unlink(missing_ok=True)
        cmd = [
            "curl",
            "-fL",
            "--http1.1",
            "-4",
            "--connect-timeout",
            "30",
            "--max-time",
            "600",
            "-A",
            UA,
            "-H",
            "Accept-Encoding: identity",
            "--progress-bar",
            "-o",
            str(dest),
            url,
        ]
        print(f"curl attempt {i}/{attempts} (no resume)…")
        proc = subprocess.run(cmd)
        if dest.exists() and _tar_ok(dest):
            print(f"  valid archive ({dest.stat().st_size} bytes)")
            return
        size = dest.stat().st_size if dest.exists() else 0
        if proc.returncode in _CURL_RETRYABLE or proc.returncode == 0:
            print(f"  incomplete (code={proc.returncode}, size={size}), retry fresh…")
            dest.unlink(missing_ok=True)
            continue
        raise subprocess.CalledProcessError(proc.returncode, cmd)
    raise IOError(f"curl failed after {attempts} fresh attempts")


def _download_with_wget(url: str, dest: Path) -> None:
    dest.unlink(missing_ok=True)
    cmd = [
        "wget",
        "--tries=8",
        "--timeout=30",
        "-4",
        f"--user-agent={UA}",
        "--header=Accept-Encoding: identity",
        "-O",
        str(dest),
        url,
    ]
    print("+", " ".join(cmd[:-1]), url)
    subprocess.run(cmd, check=True)
    if not _tar_ok(dest):
        raise IOError("wget finished but archive is corrupt/incomplete")


def _download_with_urllib(url: str, dest: Path) -> None:
    dest.unlink(missing_ok=True)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "*/*", "Accept-Encoding": "identity"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=600) as resp, dest.open("wb") as out:
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)
            if out.tell() > _MAX_TARBALL_BYTES:
                raise IOError("download exceeded expected mediawiki tarball size")
    if not _tar_ok(dest):
        raise IOError("urllib finished but archive is corrupt/incomplete")


def _download_file(url: str, dest: Path) -> None:
    errors: list[str] = []
    for name, fn in (
        ("curl", _download_with_curl if _which("curl") else None),
        ("wget", _download_with_wget if _which("wget") else None),
        ("urllib", _download_with_urllib),
    ):
        if fn is None:
            continue
        try:
            fn(url, dest)
            print(f"Downloaded via {name}: {dest.stat().st_size} bytes")
            return
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {e}")
            dest.unlink(missing_ok=True)
    raise SystemExit(
        "Failed to download MediaWiki tarball:\n  - "
        + "\n  - ".join(errors)
        + "\n\nPrefer git install on flaky links:\n"
        "  MW_FETCH=git python3 -m tools setup\n"
        "Or download elsewhere and:\n"
        "  MW_TARBALL=/path/to/mediawiki-1.45.1.tar.gz python3 -m tools setup"
    )


def _extract_mediawiki_tarball(tgz: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(tgz, "r:gz") as tf:
            try:
                tf.extractall(tmp, filter="data")
            except TypeError:
                tf.extractall(tmp)
        extracted = next(Path(tmp).glob("mediawiki-*"))
        if not (extracted / "includes" / "MediaWiki.php").is_file():
            raise SystemExit(f"Extracted archive looks invalid: {extracted}")
        if MW_DIR.exists():
            shutil.rmtree(MW_DIR)
        shutil.move(str(extracted), str(MW_DIR))


def _rel_branch(version: str) -> str:
    parts = version.split(".")
    return f"REL{parts[0]}_{parts[1]}"


def install_mediawiki_from_git() -> None:
    """Clone core + vendor via git (many small objects — more reliable than one huge tarball)."""
    if not _which("git"):
        raise SystemExit("git not found (needed for MW_FETCH=git)")

    if MW_DIR.exists():
        shutil.rmtree(MW_DIR)

    core_url = "https://github.com/wikimedia/mediawiki.git"
    print(f"git clone --depth 1 --branch {MW_VERSION} {core_url}")
    subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            MW_VERSION,
            core_url,
            str(MW_DIR),
        ],
        check=True,
    )

    vendor = MW_DIR / "vendor"
    if vendor.exists():
        shutil.rmtree(vendor)

    # Prefer composer when available; else clone mediawiki-vendor for the release branch
    composer = _which("composer")
    if composer:
        print("+ composer install --no-dev")
        subprocess.run(
            [composer, "install", "--no-dev", "--prefer-dist"],
            cwd=MW_DIR,
            check=True,
        )
    else:
        rel = _rel_branch(MW_VERSION)
        vendor_url = "https://github.com/wikimedia/mediawiki-vendor.git"
        print(f"git clone --depth 1 --branch {rel} {vendor_url} → vendor/")
        try:
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--branch",
                    rel,
                    vendor_url,
                    str(vendor),
                ],
                check=True,
            )
        except subprocess.CalledProcessError:
            print(f"Branch {rel} missing, trying default branch of mediawiki-vendor…")
            subprocess.run(
                ["git", "clone", "--depth", "1", vendor_url, str(vendor)],
                check=True,
            )

    if not (MW_DIR / "includes" / "MediaWiki.php").is_file():
        raise SystemExit("git install failed: MediaWiki.php missing")
    if not (MW_DIR / "vendor" / "autoload.php").is_file():
        raise SystemExit(
            "vendor/autoload.php missing. Install composer (`apt install composer`) "
            "or ensure mediawiki-vendor clone succeeded."
        )
    print(f"MediaWiki {MW_VERSION} installed from git → {MW_DIR}")


def download_mediawiki() -> None:
    marker = MW_DIR / "includes" / "MediaWiki.php"
    if marker.is_file():
        print(f"MediaWiki already present at {MW_DIR}")
        return

    if MW_TARBALL:
        tgz = Path(MW_TARBALL).expanduser().resolve()
        if not tgz.is_file():
            raise SystemExit(f"MW_TARBALL not found: {tgz}")
        if not _tar_ok(tgz):
            raise SystemExit(f"MW_TARBALL is not a valid mediawiki tar.gz: {tgz}")
        print(f"Using local tarball {tgz}")
        _extract_mediawiki_tarball(tgz)
        print(f"Extracted MediaWiki {MW_VERSION} → {MW_DIR}")
        return

    fetch = os.getenv("MW_FETCH", "git").strip().lower()  # git|tarball|auto
    MW_DIR.parent.mkdir(parents=True, exist_ok=True)

    if fetch in ("git", "auto"):
        try:
            install_mediawiki_from_git()
            return
        except (SystemExit, subprocess.CalledProcessError) as e:
            if fetch == "git":
                raise
            print(f"git install failed ({e}); falling back to tarball…")

    major = ".".join(MW_VERSION.split(".")[:2])
    url = f"https://releases.wikimedia.org/mediawiki/{major}/mediawiki-{MW_VERSION}.tar.gz"
    print(f"Downloading {url}…")

    cache = MW_DIR.parent / "data" / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    tgz = cache / f"mediawiki-{MW_VERSION}.tar.gz"
    if tgz.exists() and _tar_ok(tgz):
        print(f"Using cached tarball {tgz} ({tgz.stat().st_size} bytes)")
    else:
        tgz.unlink(missing_ok=True)
        _download_file(url, tgz)
    _extract_mediawiki_tarball(tgz)
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

    # Git installs don't ship Vector/etc.; MiniStation is linked just before this.
    skin_dir = MW_DIR / "skins" / "MiniStation"
    if not (skin_dir / "skin.json").is_file():
        raise SystemExit(
            f"Skin MiniStation missing at {skin_dir}. "
            "Expected symlink from repo skins/MiniStation."
        )

    server = SITE_PUBLIC_URL
    if "localhost" in server or "127.0.0.1" in server or not server.startswith("http"):
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
        # Use wiki role for install too — Ubuntu postgres often has no TCP password.
        f"--installdbuser={WIKI_DB_USER}",
        f"--installdbpass={WIKI_DB_PASS}",
        f"--lang={MW_LANG}",
        f"--pass={MW_ADMIN_PASS}",
        f"--server={server}",
        f"--scriptpath={MW_SCRIPT_PATH}",
        "--skins=MiniStation",
        SITE_NAME,
        MW_ADMIN,
    ]

    env = os.environ.copy()
    print("+", " ".join(c if "pass" not in c.lower() else c.split("=")[0] + "=***" for c in cmd))
    subprocess.run(cmd, cwd=MW_DIR, check=True, env=env)
    print("MediaWiki installed.")


CUSTOM_MARKER = "# BEGIN ministation_custom"


def sanitize_bundled_loader() -> None:
    """Wrap bare wfLoad* calls; gate VisualEditor + DiscussionTools on VE assets."""
    bundled = CUSTOM_SETTINGS.parent / "LocalSettings.bundled.php"
    if not bundled.is_file():
        return
    text = bundled.read_text(encoding="utf-8")
    original = text

    ve_ready_block = (
        "# VisualEditor needs git submodules (lib/ve). Without them RL breaks;\n"
        "# DiscussionTools depends on VisualEditor — gate both the same way.\n"
        '$wgMiniStationVeReady = is_file( "$IP/extensions/VisualEditor/extension.json" )\n'
        '	&& is_file( "$IP/extensions/VisualEditor/lib/ve/build/modules.json" );\n'
    )
    if "$wgMiniStationVeReady" not in text:
        # Insert after opening php tag
        if text.lstrip().startswith("<?php"):
            idx = text.find("<?php") + len("<?php")
            text = text[:idx] + "\n" + ve_ready_block + text[idx:]
        else:
            text = "<?php\n" + ve_ready_block + text

    def gate_ve_family(name: str, body: str) -> str:
        return (
            "if ( !empty( $wgMiniStationVeReady ) ) {\n"
            f"\twfLoadExtension( '{name}' );\n"
            "}"
        )

    for name in ("VisualEditor", "DiscussionTools"):
        # Bare load
        text = re.sub(
            rf"^\s*wfLoadExtension\(\s*'{name}'\s*\)\s*;\s*$",
            lambda m, n=name: gate_ve_family(n, m.group(0)),
            text,
            flags=re.MULTILINE,
        )
        # extension.json-only guard
        text = re.sub(
            rf"if \(\s*is_file\(\s*\"\$IP/extensions/{name}/extension\.json\"\s*\)\s*\)\s*\{{\s*"
            rf"wfLoadExtension\(\s*'{name}'\s*\)\s*;\s*\}}",
            lambda m, n=name: gate_ve_family(n, m.group(0)),
            text,
            flags=re.MULTILINE | re.DOTALL,
        )
        # VE dual-file guard (old sanitize) — still leave DiscussionTools gated via VeReady
        if name == "VisualEditor":
            text = re.sub(
                r"if \(\s*is_file\(\s*\"\$IP/extensions/VisualEditor/extension\.json\"\s*\)\s*"
                r"&&\s*is_file\(\s*\"\$IP/extensions/VisualEditor/lib/ve/build/modules\.json\"\s*\)\s*\)\s*\{"
                r"\s*wfLoadExtension\(\s*'VisualEditor'\s*\)\s*;\s*\}",
                gate_ve_family("VisualEditor", ""),
                text,
                flags=re.MULTILINE | re.DOTALL,
            )

    # Wrap any remaining bare loads (skins / other exts) — do not touch already-guarded blocks.
    def wrap_skin(m: re.Match[str]) -> str:
        name = m.group(1)
        return (
            f'if ( is_file( "$IP/skins/{name}/skin.json" ) ) {{\n'
            f"\twfLoadSkin( '{name}' );\n"
            f"}}"
        )

    def wrap_ext(m: re.Match[str]) -> str:
        name = m.group(1)
        if name in ("VisualEditor", "DiscussionTools"):
            return gate_ve_family(name, "")
        return (
            f'if ( is_file( "$IP/extensions/{name}/extension.json" ) ) {{\n'
            f"\twfLoadExtension( '{name}' );\n"
            f"}}"
        )

    text = re.sub(
        r"^\s*wfLoadSkin\(\s*'([^']+)'\s*\)\s*;\s*$",
        wrap_skin,
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(
        r"^\s*wfLoadExtension\(\s*'([^']+)'\s*\)\s*;\s*$",
        wrap_ext,
        text,
        flags=re.MULTILINE,
    )

    if text != original:
        bundled.write_text(text, encoding="utf-8")
        print(f"Sanitized {bundled} (guard missing / incomplete packages)")


def write_custom_settings_snippet() -> None:
    """Ensure LocalSettings.php requires our custom overrides."""
    CUSTOM_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    from tools.config import MAIN_SITE_URL
    sanitize_bundled_loader()

    # Never put WIKI_HOST (e.g. 0.0.0.0) into $wgServer — browsers cannot use it.
    custom = f"""<?php
# Auto-generated / managed by `python -m tools setup`. Safe to edit values.
# Loaded from mediawiki/LocalSettings.php

$wgSitename = {SITE_NAME!r};
$wgLanguageCode = {MW_LANG!r};

# Public URL of the wiki (not the bind address). Override with env MW_SERVER.
$wgServer = getenv('MW_SERVER') ?: {SITE_PUBLIC_URL!r};
# When opened via php -S, prefer the Host the browser actually used.
if ( PHP_SAPI === 'cli-server' && !empty( $_SERVER['HTTP_HOST'] ) ) {{
	$scheme = ( !empty( $_SERVER['HTTPS'] ) && $_SERVER['HTTPS'] !== 'off' ) ? 'https' : 'http';
	$host = $_SERVER['HTTP_HOST'];
	// Reject bind-all hosts that break redirects/links
	if ( !str_starts_with( $host, '0.0.0.0' ) ) {{
		$wgServer = $scheme . '://' . $host;
	}}
}}

$wgScriptPath = {MW_SCRIPT_PATH!r};
$wgArticlePath = "/index.php?title=$1";
$wgDefaultSkin = 'ministation';
$wgDefaultUserOptions['skin'] = 'ministation';

# Debug (turn off later on production)
$wgShowExceptionDetails = true;
$wgShowDBErrorBacktrace = true;
$wgShowSQLErrors = true;

# Load only if present (bare git install has no ParserFunctions until `tools extensions`)
if ( is_file( "$IP/skins/MiniStation/skin.json" ) ) {{
	wfLoadSkin( 'MiniStation' );
}} else {{
	$wgDefaultSkin = 'fallback';
}}
if ( is_file( "$IP/extensions/SS14Sprites/extension.json" ) ) {{
	wfLoadExtension( 'SS14Sprites' );
}}
if ( is_file( "$IP/extensions/ParserFunctions/extension.json" ) ) {{
	wfLoadExtension( 'ParserFunctions' );
}}

$wgSS14SpriteServiceUrl = getenv('SPRITE_PUBLIC_URL') ?: {SPRITE_PUBLIC_URL!r};
$wgMainSiteUrl = {MAIN_SITE_URL!r};
$wgEnableUploads = true;
$wgUseInstantCommons = false;
$wgMainPage = 'Заглавная страница';

# Site logo — same asset as ministation.ru (/static/logo.png)
$wgLogos = [
	'1x' => "$wgScriptPath/skins/MiniStation/resources/logo.png",
	'icon' => "$wgScriptPath/skins/MiniStation/resources/logo.png",
];
$wgLogo = "$wgScriptPath/skins/MiniStation/resources/logo.png";
$wgFavicon = "$wgScriptPath/skins/MiniStation/resources/favicon.ico";

# Prefer UTF-8 / Russian search niceties
$wgCapitalLinks = true;

# --- Permissions: only granted editors (and staff) can write ---
# Anonymous
$wgGroupPermissions['*']['edit'] = false;
$wgGroupPermissions['*']['createpage'] = false;
$wgGroupPermissions['*']['createtalk'] = false;
$wgGroupPermissions['*']['upload'] = false;
$wgGroupPermissions['*']['writeapi'] = false;
$wgGroupPermissions['*']['createaccount'] = false; // accounts via staff only

# Registered users — read-only until added to «editor»
$wgGroupPermissions['user']['edit'] = false;
$wgGroupPermissions['user']['createpage'] = false;
$wgGroupPermissions['user']['createtalk'] = false;
$wgGroupPermissions['user']['upload'] = false;
$wgGroupPermissions['user']['reupload'] = false;
$wgGroupPermissions['user']['reupload-shared'] = false;
$wgGroupPermissions['user']['move'] = false;
$wgGroupPermissions['user']['move-subpages'] = false;
$wgGroupPermissions['user']['move-rootuserpages'] = false;
$wgGroupPermissions['user']['minoredit'] = false;
$wgGroupPermissions['user']['purge'] = false;
$wgGroupPermissions['user']['sendemail'] = false;

$wgGroupPermissions['autoconfirmed']['edit'] = false;
$wgGroupPermissions['autoconfirmed']['createpage'] = false;
$wgGroupPermissions['autoconfirmed']['upload'] = false;
$wgGroupPermissions['autoconfirmed']['move'] = false;

# Explicit editor role (assign via Special:UserRights)
$wgGroupPermissions['editor']['read'] = true;
$wgGroupPermissions['editor']['edit'] = true;
$wgGroupPermissions['editor']['createpage'] = true;
$wgGroupPermissions['editor']['createtalk'] = true;
$wgGroupPermissions['editor']['upload'] = true;
$wgGroupPermissions['editor']['reupload'] = true;
$wgGroupPermissions['editor']['move'] = true;
$wgGroupPermissions['editor']['move-subpages'] = true;
$wgGroupPermissions['editor']['minoredit'] = true;
$wgGroupPermissions['editor']['patrol'] = true;
$wgGroupPermissions['editor']['writeapi'] = true;
$wgGroupPermissions['editor']['editmyusercss'] = true;
$wgGroupPermissions['editor']['editmyuserjs'] = true;
$wgGroupPermissions['editor']['editmyuserjson'] = true;

# Staff can grant/revoke editor
$wgAddGroups['sysop'][] = 'editor';
$wgRemoveGroups['sysop'][] = 'editor';
$wgAddGroups['bureaucrat'][] = 'editor';
$wgRemoveGroups['bureaucrat'][] = 'editor';
$wgAddGroups['bureaucrat'][] = 'sysop';
$wgRemoveGroups['bureaucrat'][] = 'sysop';

# Styles: inline skin.css so php -S / RL cannot leave the wiki unstyled
$wgHooks['BeforePageDisplay'][] = static function ( $out, $skin ): void {{
	if ( $skin->getSkinName() !== 'ministation' ) {{
		return;
	}}
	global $IP, $wgScriptPath;
	$cssFiles = [
		'skin.css',
		'mainpage-widgets.css',
		'items-tables.css',
		'tgui-chrome.css',
	];
	foreach ( $cssFiles as $cssFile ) {{
		$cssPath = "$IP/skins/MiniStation/resources/" . $cssFile;
		if ( is_file( $cssPath ) ) {{
			$css = file_get_contents( $cssPath );
			if ( is_string( $css ) && $css !== '' ) {{
				$out->addInlineStyle( $css );
			}}
		}}
	}}
	$base = rtrim( (string)$wgScriptPath, '/' ) . '/skins/MiniStation/resources/';
	$out->addStyle( $base . 'skin.css?v=20260806a', 'screen' );
	$out->addStyle( $base . 'mainpage-widgets.css?v=20260806a', 'screen' );
	$out->addStyle( $base . 'items-tables.css?v=20260806a', 'screen' );
	$out->addStyle( $base . 'tgui-chrome.css?v=20260806a', 'screen' );
	// Pixel font like ministation.ru (do not rely only on skin.js)
	$out->addHeadItem(
		'ms-fonts',
		'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Exo+2:wght@400;600;700&family=Press+Start+2P&display=swap">'
	);
	$out->addHeadItem(
		'ms-favicon',
		'<link rel="icon" href="' . htmlspecialchars( $base . 'favicon.ico' ) . '">'
	);
}};

# Home hero (real HTML — never put <a> blocks in wikitext)
$wgHooks['OutputPageBeforeHTML'][] = static function ( $out, &$text ): void {{
	$title = $out->getTitle();
	if ( !$title || !$title->isMainPage() ) {{
		return;
	}}
	if ( str_contains( $text, 'id="ms-hero"' ) ) {{
		return;
	}}
	$hero = <<<'MS_HERO'
<div class="card hero-card hero-top ms-hero" id="ms-hero">
<h2 class="hero-brand">Мини<span>-</span>станция</h2>
<span class="tagline">Космическая станция 14</span>
<p class="description">Мини-станция - это некоммерческий, самый безбашенный проект в игре Космическая станция 14, где ты сможешь как вдоволь поучаствовать в эпичных баталиях, так и показать свой ролевой отыгрыш.</p>
<div class="social-links">
<a class="link-btn website" href="http://cdn.ministation.ru/" target="_blank" rel="noopener"><i class="fa-solid fa-cloud" aria-hidden="true"></i> CDN</a>
<a class="link-btn discord" href="https://discord.gg/mini-station" target="_blank" rel="noopener"><i class="fa-brands fa-discord" aria-hidden="true"></i> Discord</a>
<a class="link-btn telegram" href="https://t.me/mini_station" target="_blank" rel="noopener"><i class="fa-brands fa-telegram" aria-hidden="true"></i> Telegram</a>
<a class="link-btn wiki" href="https://ministation.ru" target="_blank" rel="noopener"><i class="fa-solid fa-globe" aria-hidden="true"></i> Сайт</a>
<a class="link-btn boosty" href="https://ministation.ru/donate" target="_blank" rel="noopener"><i class="fa-solid fa-heart" aria-hidden="true"></i> Донат</a>
<a class="link-btn github" href="https://github.com/ministation/mini-station-goob" target="_blank" rel="noopener"><i class="fa-brands fa-github" aria-hidden="true"></i> GitHub</a>
</div>
</div>
MS_HERO;
	$text = $hero . $text;
}};

# BEGIN ministation_bundled
if ( is_file( __DIR__ . '/LocalSettings.bundled.php' ) ) {{
    require_once __DIR__ . '/LocalSettings.bundled.php';
}}
# END ministation_bundled
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
    print("Optional: python -m tools extensions   # official bundled extensions/skins")
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
