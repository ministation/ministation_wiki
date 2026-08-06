# -*- coding: utf-8 -*-
"""Re-apply branding scrub to imported .wiki pages already in MediaWiki."""
from __future__ import annotations

import argparse
from pathlib import Path

from tools.import_remote import IMPORT_DIR, parse_import_file
from tools.migrate import edit_page


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="Max pages (0 = all)")
    ap.add_argument("--source", default="remote")
    ap.add_argument(
        "--only",
        nargs="*",
        default=None,
        help="Optional exact titles to scrub",
    )
    args = ap.parse_args()

    root = IMPORT_DIR / args.source
    files = sorted(root.rglob("*.wiki")) if root.is_dir() else []
    if args.only:
        want = set(args.only)
        selected = []
        for path in files:
            title, _ = parse_import_file(path)
            if title in want:
                selected.append(path)
        files = selected

    if args.limit and args.limit > 0:
        files = files[: args.limit]

    print(f"Scrubbing {len(files)} page(s)…")
    for path in files:
        title, body = parse_import_file(path)
        # rewrite file on disk with scrubbed body for future applies
        raw = path.read_text(encoding="utf-8")
        if raw.startswith("<!-- ministation-import"):
            end = raw.find("-->")
            header = raw[: end + 3] + "\n"
        else:
            header = ""
        path.write_text(header + body, encoding="utf-8")
        edit_page(title, body, summary="scrub third-party branding")
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
