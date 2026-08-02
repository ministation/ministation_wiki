from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(
            "Usage: python -m tools <command>\n\n"
            "Commands:\n"
            "  setup       Download MediaWiki, create Postgres DB, install, link skin/ext\n"
            "  db          Create wiki PostgreSQL role/database/schema only\n"
            "  extensions  Clone+enable official bundled extensions/skins for this MW version\n"
            "  migrate     Import content/ru Markdown into MediaWiki\n"
            "  start       Run MediaWiki (php -S) + sprite service (uvicorn)\n"
        )
        return 0

    cmd, rest = argv[0], argv[1:]
    if cmd == "setup":
        from tools.setup import main as setup_main

        return setup_main(rest)
    if cmd == "db":
        from tools.db import main as db_main

        return db_main(rest)
    if cmd == "extensions":
        from tools.extensions import main as extensions_main

        return extensions_main(rest)
    if cmd == "migrate":
        from tools.migrate import main as migrate_main

        return migrate_main(rest)
    if cmd == "start":
        from tools.start import main as start_main

        return start_main(rest)

    print(f"Unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
