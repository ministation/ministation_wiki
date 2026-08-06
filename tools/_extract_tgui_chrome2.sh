#!/bin/bash
set -euo pipefail
python3 <<'PY'
import re, urllib.request
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 ministation"}

def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read().decode("utf-8", "replace")

url = (
    "https://wiki.ss220.club/load.php?lang=ru"
    "&modules=skins.tgui.icons,styles"
    "&only=styles&skin=tgui"
)
css = fetch(url)
Path("/tmp/remote_tgui_skin.css").write_text(css, encoding="utf-8")
print("css bytes", len(css))
for key in [
    "page-actions",
    "cdx-button",
    "tgui-menu",
    "mw-portlet-views",
    "ca-viewsource",
    "sticky-header",
    "page-heading",
]:
    print(key, css.count(key))

# pretty-print a few key rule groups by regex on minified
# Extract selectors containing page-actions|cdx-button|tgui-menu

def extract_containing(css: str, needle: str, limit: int = 25):
    out = []
    start = 0
    while len(out) < limit:
        i = css.find(needle, start)
        if i < 0:
            break
        left = css.rfind("}", 0, i) + 1
        brace = css.find("{", left)
        if brace < 0:
            break
        depth = 0
        j = brace
        while j < len(css):
            ch = css[j]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        block = css[left:j].strip()
        if block and block not in out:
            out.append(block)
        start = i + len(needle)
    return out

blocks = []
for needle in ["page-actions", "cdx-button", "tgui-menu__content", "tgui-menu__heading", "mw-portlet-views"]:
    blocks.extend(extract_containing(css, needle, 40))

# dedupe preserve order
seen = set()
uniq = []
for b in blocks:
    if b not in seen:
        seen.add(b)
        uniq.append(b)

text = "/* TGUI chrome extract */\n\n" + "\n\n".join(uniq)
Path("/tmp/tgui_chrome_extract.css").write_text(text, encoding="utf-8")
print("extract blocks", len(uniq), "bytes", len(text))
print(text[:4000])
print("\n==== MID ====\n")
print(text[4000:8000])
print("\n==== MORE ====\n")
print(text[8000:12000])

# remote HTML structure for page-actions
html = Path("/tmp/remote_page.html").read_text(encoding="utf-8")
i = html.find("page-actions")
print("\nPAGE-ACTIONS HTML:\n", html[i : i + 1500].replace("\n", " "))
PY
