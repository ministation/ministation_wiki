#!/bin/bash
set -euo pipefail
python3 <<'PY'
import json, re, urllib.parse, urllib.request
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 ministation"}

def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read()

def fetch_text(url):
    return fetch(url).decode("utf-8", "replace")

def api(base, **kw):
    return json.loads(fetch_text(base + "?" + urllib.parse.urlencode(kw)))

# 1) Extract TGUI palette variables into a usable file
css = Path("/tmp/remote_skin_styles.css").read_text(encoding="utf-8")
# The RL CSS is minified. Pull blocks that define palette vars.
# Strategy: find --palette-saturation and expand around color token definitions.
# Simpler: rewrite our :root to closer TGUI values + outset borders for items-table.

palette = '''/* Closer to SS220 TGUI palette for item tables */
:root,
html[data-theme="light"] {
  --palette-saturation: 50%;
  --palette-lightness: 50%;
  --color-primal-fill: #e8eef7;
  --color-primal: #17222f;
  --color-primal-immutable: #3d6ea8;
  --color-primary: #3d6ea8;
  --color-primary-light: #4f82c0;
  --color-second: color-mix(in srgb, hsla(0, 0%, 100%, 0.55), var(--color-primal-fill) 40%);
  --color-second-fill: color-mix(in srgb, var(--color-primal-fill), white 3%);
  --color-border: color-mix(in srgb, var(--color-primal), transparent 78%);
  --color-text: #17222f;
  --color-text-darker: #0f1620;
  --color-white: #ffffff;
  --color-red: #c43c3c;
  --border-classic: 1px outset var(--color-border);
  --border-radius-large: 12px;
  --border-radius-medium: 8px;
  --border-radius-small: 6px;

  --civilian-opaque: hsl(140, calc(var(--palette-saturation) + 20%), calc(var(--palette-lightness) - 15%));
  --civilian-primary: hsla(141, calc(var(--palette-saturation) + 20%), calc(var(--palette-lightness) - 15%), 0.75);
  --civilian-secondary: hsla(142, calc(var(--palette-saturation) + 20%), calc(var(--palette-lightness) - 15%), 0.5);
  --civilian-light: hsla(143, calc(var(--palette-saturation) + 20%), calc(var(--palette-lightness) - 15%), 0.25);
  --civilian-transparent: hsla(144, calc(var(--palette-saturation) + 20%), calc(var(--palette-lightness) - 15%), 0.1);

  --medical-opaque: hsl(195, calc(var(--palette-saturation) + 25%), calc(var(--palette-lightness) - 10%));
  --medical-primary: hsla(194, calc(var(--palette-saturation) + 25%), calc(var(--palette-lightness) - 10%), 0.75);
  --medical-secondary: hsla(193, calc(var(--palette-saturation) + 25%), calc(var(--palette-lightness) - 10%), 0.5);
  --medical-light: hsla(192, calc(var(--palette-saturation) + 25%), calc(var(--palette-lightness) - 10%), 0.25);
  --medical-transparent: hsla(191, calc(var(--palette-saturation) + 25%), calc(var(--palette-lightness) - 10%), 0.1);

  --science-opaque: hsl(273, calc(var(--palette-saturation) + 40%), calc(var(--palette-lightness) - 15%));
  --science-primary: hsla(274, calc(var(--palette-saturation) + 40%), calc(var(--palette-lightness) - 15%), 0.75);
  --science-secondary: hsla(273, calc(var(--palette-saturation) + 40%), calc(var(--palette-lightness) - 15%), 0.5);
  --science-light: hsla(272, calc(var(--palette-saturation) + 40%), calc(var(--palette-lightness) - 15%), 0.25);
  --science-transparent: hsla(270, calc(var(--palette-saturation) + 40%), calc(var(--palette-lightness) - 15%), 0.1);

  --engineer-opaque: hsl(40, calc(var(--palette-saturation) + 50%), calc(var(--palette-lightness) - 15%));
  --engineer-primary: hsla(39, calc(var(--palette-saturation) + 50%), calc(var(--palette-lightness) - 15%), 0.75);
  --engineer-secondary: hsla(38, calc(var(--palette-saturation) + 50%), calc(var(--palette-lightness) - 15%), 0.5);
  --engineer-light: hsla(37, calc(var(--palette-saturation) + 50%), calc(var(--palette-lightness) - 15%), 0.25);
  --engineer-transparent: hsla(36, calc(var(--palette-saturation) + 50%), calc(var(--palette-lightness) - 15%), 0.1);

  --security-opaque: hsl(0, calc(var(--palette-saturation) + 15%), calc(var(--palette-lightness) - 8%));
  --security-primary: hsla(0, calc(var(--palette-saturation) + 15%), calc(var(--palette-lightness) - 8%), 0.75);
  --security-secondary: hsla(0, calc(var(--palette-saturation) + 15%), calc(var(--palette-lightness) - 8%), 0.5);
  --security-light: hsla(0, calc(var(--palette-saturation) + 15%), calc(var(--palette-lightness) - 8%), 0.25);
  --security-transparent: hsla(0, calc(var(--palette-saturation) + 15%), calc(var(--palette-lightness) - 8%), 0.1);

  --supply-opaque: hsl(25, calc(var(--palette-saturation) + 20%), calc(var(--palette-lightness) - 10%));
  --supply-primary: hsla(24, calc(var(--palette-saturation) + 20%), calc(var(--palette-lightness) - 10%), 0.75);
  --supply-secondary: hsla(23, calc(var(--palette-saturation) + 20%), calc(var(--palette-lightness) - 10%), 0.5);
  --supply-light: hsla(22, calc(var(--palette-saturation) + 20%), calc(var(--palette-lightness) - 10%), 0.25);
  --supply-transparent: hsla(21, calc(var(--palette-saturation) + 20%), calc(var(--palette-lightness) - 10%), 0.1);

  --command-opaque: hsl(210, calc(var(--palette-saturation) + 5%), calc(var(--palette-lightness) - 10%));
  --command-primary: hsla(209, calc(var(--palette-saturation) + 5%), calc(var(--palette-lightness) - 10%), 0.75);
  --command-secondary: hsla(208, calc(var(--palette-saturation) + 5%), calc(var(--palette-lightness) - 10%), 0.5);
  --command-light: hsla(207, calc(var(--palette-saturation) + 5%), calc(var(--palette-lightness) - 10%), 0.25);
  --command-transparent: hsla(206, calc(var(--palette-saturation) + 5%), calc(var(--palette-lightness) - 10%), 0.1);

  --antag-opaque: hsl(345, calc(var(--palette-saturation) + 10%), calc(var(--palette-lightness) - 12%));
  --antag-primary: hsla(344, calc(var(--palette-saturation) + 10%), calc(var(--palette-lightness) - 12%), 0.75);
  --antag-secondary: hsla(343, calc(var(--palette-saturation) + 10%), calc(var(--palette-lightness) - 12%), 0.5);
  --antag-light: hsla(342, calc(var(--palette-saturation) + 10%), calc(var(--palette-lightness) - 12%), 0.25);
  --antag-transparent: hsla(341, calc(var(--palette-saturation) + 10%), calc(var(--palette-lightness) - 12%), 0.1);
}

html[data-theme="dark"] {
  --palette-saturation: 45%;
  --palette-lightness: 45%;
  --color-primal-fill: #1a2230;
  --color-primal: #e8eef6;
  --color-primary: #4f82c0;
  --color-primary-light: #6a9ad0;
  --color-second: color-mix(in srgb, hsla(0, 0%, 0%, 0.07), var(--color-primal-fill) 33%);
  --color-second-fill: color-mix(in srgb, var(--color-primal-fill), black 4.5%);
  --color-border: color-mix(in srgb, var(--color-primal), transparent 82%);
  --color-text: #e8eef6;
  --color-text-darker: #c5d0de;
  --color-red: #e85a5a;
  --border-classic: 1px outset var(--color-border);

  --engineer-opaque: hsl(40, calc(var(--palette-saturation) + 25%), calc(var(--palette-lightness) + 5%));
  --engineer-primary: hsla(39, calc(var(--palette-saturation) + 25%), calc(var(--palette-lightness) + 5%), 0.75);
  --engineer-secondary: hsla(38, calc(var(--palette-saturation) + 25%), calc(var(--palette-lightness) + 5%), 0.5);
  --engineer-light: hsla(37, calc(var(--palette-saturation) + 25%), calc(var(--palette-lightness) + 5%), 0.25);
  --engineer-transparent: hsla(36, calc(var(--palette-saturation) + 25%), calc(var(--palette-lightness) + 5%), 0.1);
}

/* Item tables: closer to TGUI look */
.items-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0.15em;
  border: var(--border-classic);
  border-radius: var(--border-radius-medium);
  background-color: var(--color-second-fill);
  overflow: hidden;
}
.items-table th {
  border: 0.2em double var(--color-border);
  border-radius: var(--border-radius-small);
  background-color: var(--color-second);
  color: var(--color-text);
  padding: 0.35em 0.4em;
  font-weight: 700;
}
.items-table td {
  background-color: var(--color-second);
  color: var(--color-text);
  padding: 0.4em 0.45em;
  vertical-align: middle;
}
.items-table img,
.items-table .mw-file-element {
  max-height: 64px;
  width: auto;
  image-rendering: pixelated;
}
.items-table .mw-broken-media {
  opacity: 0.55;
  font-size: 0.85em;
}
'''

# Keep existing dept color rules from items-tables.css (from .colors-secure onward)
old = Path("/home/ss14_user/ministation_wiki/skins/MiniStation/resources/items-tables.css").read_text(encoding="utf-8")
# drop old .items-table base rules, keep color variants + weapon-table
idx = old.find("/* Цвета охранного отдела */")
if idx < 0:
    idx = old.find(".colors-secure")
rest = old[idx:] if idx >= 0 else old
out = palette + "\n" + rest
Path("/home/ss14_user/ministation_wiki/skins/MiniStation/resources/items-tables.css").write_text(out, encoding="utf-8")
print("wrote items-tables.css", len(out))

# 2) Download missing images used by construction page from remote
LOCAL = "http://127.0.0.1:3000/api.php"
REMOTE = "https://wiki.ss220.club/api.php"
page = "Руководство по строительству"

cont = {}
titles = []
while True:
    q = {
        "action": "query",
        "titles": page,
        "prop": "images",
        "imlimit": 500,
        "format": "json",
        **cont,
    }
    d = api(LOCAL, **q)
    p = list(d["query"]["pages"].values())[0]
    titles.extend(im["title"] for im in p.get("images", []))
    cont = d.get("continue") or {}
    if not cont:
        break
titles = sorted(set(titles))
print("images on page", len(titles))

# which missing locally
missing = []
for i in range(0, len(titles), 40):
    chunk = titles[i : i + 40]
    d = api(LOCAL, action="query", titles="|".join(chunk), format="json")
    for p in d["query"]["pages"].values():
        if "missing" in p:
            missing.append(p["title"])
print("missing", len(missing))

img_dir = Path("/home/ss14_user/ministation_wiki/data/remote_images")
img_dir.mkdir(parents=True, exist_ok=True)
ok = fail = 0
for i in range(0, len(missing), 40):
    chunk = missing[i : i + 40]
    d = api(
        REMOTE,
        action="query",
        titles="|".join(chunk),
        prop="imageinfo",
        iiprop="url|mime|size",
        format="json",
    )
    for p in d["query"]["pages"].values():
        title = p.get("title", "")
        if "missing" in p or not p.get("imageinfo"):
            fail += 1
            continue
        url = p["imageinfo"][0]["url"]
        # File:Foo.png -> Foo.png
        name = title.split(":", 1)[-1].replace(" ", "_")
        # MediaWiki normalizes spaces; keep original filename from URL when possible
        from urllib.parse import unquote, urlparse
        url_name = unquote(urlparse(url).path.split("/")[-1])
        dest = img_dir / url_name
        try:
            data = fetch(url)
            dest.write_bytes(data)
            ok += 1
            if ok <= 5 or ok % 25 == 0:
                print(" got", dest.name, len(data))
        except Exception as e:
            fail += 1
            print(" fail", title, e)
print("downloaded", ok, "fail", fail)
PY
