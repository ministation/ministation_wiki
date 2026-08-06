#!/bin/bash
set -euo pipefail
python3 <<'PY'
import re, urllib.request
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 ministation"}

def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode("utf-8", "replace")

html = fetch("https://wiki.ss220.club/index.php/%D0%A0%D1%83%D0%BA%D0%BE%D0%B2%D0%BE%D0%B4%D1%81%D1%82%D0%B2%D0%BE_%D0%BF%D0%BE_%D1%81%D1%82%D1%80%D0%BE%D0%B8%D1%82%D0%B5%D0%BB%D1%8C%D1%81%D1%82%D0%B2%D1%83")
Path("/tmp/remote_page.html").write_text(html, encoding="utf-8")

# page action / tabs HTML
for key in ["ca-edit", "ca-view", "ca-history", "ca-viewsource", "p-views", "p-cactions", "vector-menu", "tgui-tabs", "cdx-button", "mw-portlet"]:
    print(key, html.lower().count(key.lower()))

# extract namespaces around ca-edit
i = html.find('id="ca-edit"')
if i < 0:
    i = html.find("ca-edit")
print("EDIT CTX:\n", html[max(0, i - 200) : i + 500].replace("\n", " ")[:800])

i = html.find('id="p-views"')
print("PVIEWS CTX:\n", html[max(0, i - 100) : i + 900].replace("\n", " ")[:1000])

# TGUI styles
urls = []
for m in re.findall(r'(?:href|src)="([^"]+)"', html):
    if "load.php" in m and "only=styles" in m and "tgui" in m.lower():
        u = m.replace("&amp;", "&")
        if u.startswith("/"):
            u = "https://wiki.ss220.club" + u
        urls.append(u)
print("tgui style urls", urls)
for u in urls:
    css = fetch(u)
    Path("/tmp/remote_tgui_full.css").write_text(css, encoding="utf-8")
    print("css", len(css))
    for key in ["ca-edit", "vector-tab", "tgui-button", "cdx-button", "mw-portlet", "page-actions", "tabs", "toolbar", "button"]:
        print(" ", key, css.count(key))

css = Path("/tmp/remote_tgui_full.css").read_text(encoding="utf-8")
# find button-ish rules
for key in [".cdx-button", ".tgui-button", "#p-views", ".vector-menu-tabs", ".mw-portlet-views", "ca-edit", ".mw-ui-button"]:
    i = css.find(key)
    print("---", key, "at", i, "---")
    if i >= 0:
        print(css[i : i + 500])

# MediaWiki:Tgui.css
import json, urllib.parse
q = urllib.parse.urlencode({
    "action": "query",
    "titles": "MediaWiki:Tgui.css",
    "prop": "revisions",
    "rvprop": "content",
    "rvslots": "main",
    "format": "json",
})
d = json.loads(fetch("https://wiki.ss220.club/api.php?" + q))
body = list(d["query"]["pages"].values())[0]["revisions"][0]["slots"]["main"]["*"]
Path("/tmp/MediaWiki_Tgui.css").write_text(body, encoding="utf-8")
print("Tgui.css", len(body))
print(body[:1500])
PY

# local page actions HTML
python3 <<'PY'
import re, urllib.request
from pathlib import Path
html = urllib.request.urlopen('http://127.0.0.1:3000/index.php/%D0%A0%D1%83%D0%BA%D0%BE%D0%B2%D0%BE%D0%B4%D1%81%D1%82%D0%B2%D0%BE_%D0%BF%D0%BE_%D1%81%D1%82%D1%80%D0%BE%D0%B8%D1%82%D0%B5%D0%BB%D1%8C%D1%81%D1%82%D0%B2%D1%83', timeout=60).read().decode('utf-8','replace')
Path('/tmp/local_page.html').write_text(html, encoding='utf-8')
for key in ['ca-edit','ca-view','ca-viewsource','ca-history','p-views','p-cactions','page-actions','ms-']:
    print('local', key, html.lower().count(key.lower()))
i = html.find('ca-edit')
print('LOCAL EDIT', html[max(0,i-300):i+600].replace('\n',' ')[:900])
i = html.find('p-views')
print('LOCAL PVIEWS', html[max(0,i-100):i+700].replace('\n',' ')[:900])
PY
