from __future__ import annotations

import signal
import subprocess
import sys
import time
from pathlib import Path

from tools.config import (
    BASE_DIR,
    MW_DIR,
    PHP_BIN,
    SPRITE_HOST,
    SPRITE_PORT,
    WIKI_HOST,
    WIKI_PORT,
)

ROUTER = BASE_DIR / "tools" / "php_router.php"


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

    print(f"MediaWiki  http://{WIKI_HOST}:{WIKI_PORT}/")
    print(f"Sprites    http://{SPRITE_HOST}:{SPRITE_PORT}/sprite/…")
    print("Ctrl+C to stop.\n")

    procs.append(subprocess.Popen(wiki_cmd, cwd=str(BASE_DIR)))
    procs.append(subprocess.Popen(sprite_cmd, cwd=str(BASE_DIR)))

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
