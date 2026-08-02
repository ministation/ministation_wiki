from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from tools.config import (
    BASE_DIR,
    MW_DIR,
    MW_SERVER,
    PHP_BIN,
    SITE_PUBLIC_URL,
    SPRITE_HOST,
    SPRITE_PORT,
    SPRITE_PUBLIC_URL,
    WIKI_HOST,
    WIKI_PORT,
)

ROUTER = BASE_DIR / "tools" / "php_router.php"


def _child_env() -> dict[str, str]:
    """Pass wiki public URLs into PHP (LocalSettings uses getenv)."""
    env = os.environ.copy()
    env["MW_SERVER"] = MW_SERVER or SITE_PUBLIC_URL
    env["SPRITE_PUBLIC_URL"] = SPRITE_PUBLIC_URL
    # Ensure PHP cwd-related tools see project .env values consistently
    env["SITE_PUBLIC_URL"] = SITE_PUBLIC_URL
    return env


def _refresh_local_settings() -> None:
    """Rewrite config snippet so pulls take effect without a full reinstall."""
    try:
        from tools.setup import write_custom_settings_snippet

        write_custom_settings_snippet()
    except Exception as e:  # noqa: BLE001
        print(f"WARNING: could not refresh LocalSettings.custom.php: {e}", file=sys.stderr)


def _probe_wiki(port: int) -> None:
    import urllib.error
    import urllib.request
    import re

    url = f"http://127.0.0.1:{port}/"
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            print(f"Local probe {url} → HTTP {resp.status}")
            return
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"Local probe failed: HTTP Error {e.code}: {e.reason}")
        # Strip tags lightly and show the exception text MediaWiki prints
        text = re.sub(r"<script[\s\S]*?</script>", " ", body, flags=re.I)
        text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            print("--- MediaWiki response (excerpt) ---")
            print(text[:1200])
            print("---")
        print(
            "Tip: ensure LocalSettings.custom.php was regenerated "
            "(tools start does this now). For a full stack: "
            "$wgShowExceptionDetails = true;"
        )
    except Exception as e:  # noqa: BLE001
        print(f"Local probe failed: {e}")
        print("If this fails, MediaWiki/PHP is not serving — check logs above.")


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if argv and argv[0] in ("-h", "--help"):
        print("Usage: python -m tools start\nStart MediaWiki (php -S) + sprite uvicorn.")
        return 0

    if not (MW_DIR / "index.php").is_file():
        print("MediaWiki missing. Run: python -m tools setup", file=sys.stderr)
        return 1
    if not ROUTER.is_file():
        print(f"Router missing: {ROUTER}", file=sys.stderr)
        return 1

    _refresh_local_settings()

    procs: list[subprocess.Popen] = []
    def shutdown(*_args) -> None:
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()

    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)

    env = _child_env()

    wiki_cmd = [
        PHP_BIN,
        "-S",
        f"{WIKI_HOST}:{WIKI_PORT}",
        str(ROUTER),
    ]
    sprite_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        SPRITE_HOST,
        "--port",
        str(SPRITE_PORT),
    ]

    public = (MW_SERVER or SITE_PUBLIC_URL).rstrip("/") or f"http://127.0.0.1:{WIKI_PORT}"
    if WIKI_HOST in ("127.0.0.1", "localhost"):
        print(
            "WARNING: WIKI_HOST is localhost — not reachable from the internet.\n"
            "         Use WIKI_HOST=0.0.0.0 and SITE_PUBLIC_URL=http://YOUR_IP:3000\n"
        )
    if "0.0.0.0" in public:
        print(
            "WARNING: SITE_PUBLIC_URL/MW_SERVER contains 0.0.0.0 — browsers cannot open that.\n"
            "         Set SITE_PUBLIC_URL=http://144.31.0.187:3000\n"
        )

    print(f"Bind       {WIKI_HOST}:{WIKI_PORT} (php) + {SPRITE_HOST}:{SPRITE_PORT} (sprites)")
    print(f"Open       {public}/")
    print(f"Sprites    {SPRITE_PUBLIC_URL}/sprite/…")
    print("Ctrl+C to stop.\n")

    procs.append(subprocess.Popen(wiki_cmd, cwd=str(BASE_DIR), env=env))
    procs.append(subprocess.Popen(sprite_cmd, cwd=str(BASE_DIR), env=env))

    time.sleep(0.8)
    _probe_wiki(WIKI_PORT)

    try:
        while True:
            for p in procs:
                code = p.poll()
                if code is not None:
                    shutdown()
                    return code or 1
            time.sleep(0.4)
    except KeyboardInterrupt:
        shutdown()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
