#!/bin/bash
set -euo pipefail
python3 <<'PY'
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 ministation"}

def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode("utf-8", "replace")

def api(base: str, **kw):
    return json.loads(fetch(base + "?" + urllib.parse.urlencode(kw)))

html = fetch(
    "https://wiki.ss220.club/index.php/"
    "%D0%A0%D1%83%D0%BA%D0%BE%D0%B2%D0%BE%D0%B4%D1%81%D1%82%D0%B2%D0%BE_"
    "%D0%BF%D0%BE_%D1%81%D1%82%D1%80%D0%BE%D0%B8%D1%82%D0%B5%D0%BB%D1%8C%D1%81%D1%82%D0%B2%D1%83"
)
urls = []
for m in re.findall(r'(?:src|href)="([^"]+)"', html):
    if "load.php" in m and "only=styles" in m:
        u = m.replace("&amp;", "&")
        if u.startswith("/"):
            u = "https://wiki.ss220.club" + u
        urls.append(u)
print("style modules", len(urls))
for u in urls:
    print("URL", u[:220])
    try:
        css = fetch(u)
    except Exception as e:
        print(" fail", e)
        continue
    interesting = any(
        x in css
        for x in ("--engineer-opaque", "--color-second-fill", "--border-classic")
    )
    print(" len", len(css), "interesting", interesting)
    if not interesting:
        continue
    Path("/tmp/remote_skin_styles.css").write_text(css, encoding="utf-8")
    for pat in ("--engineer-opaque", "--color-second-fill", "--color-second", "--border-classic"):
        for m in re.finditer(rf"{re.escape(pat)}\s*:\s*[^;]+;", css):
            print(" DEF", m.group(0)[:120])
    i = css.find("--engineer-opaque")
    print("CTX", css[max(0, i - 400) : i + 120])

info = api(
    "https://wiki.ss220.club/api.php",
    action="query",
    meta="siteinfo",
    siprop="skins|general",
    format="json",
)
print("remote skins", [s["code"] for s in info["query"].get("skins", [])])
print("default skin", info["query"]["general"].get("skin"))

# Missing images sample from construction page local
d = api(
    "http://127.0.0.1:3000/api.php",
    action="query",
    titles="Руководство по строительству",
    prop="images",
    imlimit=50,
    format="json",
)
imgs = list(d["query"]["pages"].values())[0].get("images", [])
print("local page images listed", len(imgs))
missing = 0
for im in imgs[:30]:
    title = im["title"]
    p = list(
        api(
            "http://127.0.0.1:3000/api.php",
            action="query",
            titles=title,
            format="json",
        )["query"]["pages"].values()
    )[0]
    if "missing" in p:
        missing += 1
        if missing <= 10:
            print(" MISS", title)
print("missing among first 30:", missing)
PY
