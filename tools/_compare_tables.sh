#!/bin/bash
set -euo pipefail
python3 <<'PY'
import json, re, urllib.parse, urllib.request
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 ministation-compare"}

def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode("utf-8", "replace")

def api(base, **kw):
    req = urllib.request.Request(base + "?" + urllib.parse.urlencode(kw), headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode())

LOCAL = "http://127.0.0.1:3000"
REMOTE = "https://wiki.ss220.club"

# Parse construction page on both
for name, base, title in [
    ("local", LOCAL + "/api.php", "Руководство по строительству"),
    ("remote", REMOTE + "/api.php", "Руководство по строительству"),
]:
    d = api(base, action="parse", page=title, prop="text|headhtml", disablelimitreport=1, format="json")
    html = d["parse"]["text"]["*"]
    head = d["parse"].get("headhtml", "")
    # first items-table opening tag
    m = re.search(r'<table[^>]*items-table[^>]*>', html)
    print(f"=== {name} table tag ===")
    print(m.group(0) if m else "NONE")
    # first row cells classes/styles
    m2 = re.search(r'<table[^>]*items-table[\s\S]{0,2500}</tr>', html)
    frag = m2.group(0) if m2 else ""
    print("fragment classes:", sorted(set(re.findall(r'class="([^"]+)"', frag)))[:20])
    # CSS files / modules
    css_hrefs = re.findall(r'href="([^"]+\.css[^"]*)"', head)
    print("css hrefs", len(css_hrefs))
    for h in css_hrefs[:15]:
        print(" ", h[:120])
    # load.php modules
    mods = re.findall(r'modules=([^&\"\']+)', head)
    print("modules sample", [urllib.parse.unquote(m)[:100] for m in mods[:6]])
    Path(f"/tmp/{name}_table_frag.html").write_text(frag[:4000], encoding="utf-8")
    Path(f"/tmp/{name}_head.html").write_text(head[:15000], encoding="utf-8")

# Remote Common.css - check :root vars for department colors (might be elsewhere)
for title in ["MediaWiki:Common.css", "MediaWiki:Vector.css", "MediaWiki:Citizen.css", "MediaWiki:Theme.css", "MediaWiki:Gadget-site.css"]:
    p = list(api(REMOTE+"/api.php", action="query", titles=title, format="json")["query"]["pages"].values())[0]
    print("remote page", title, "MISS" if "missing" in p else "ok")

# Fetch remote homepage head for CSS var definitions - Theme or skin
# Search remote for --engineer-opaque definition location via API search
d = api(REMOTE+"/api.php", action="query", list="search", srsearch="engineer-opaque", srnamespace="8|10", srlimit=10, format="json")
print("search engineer-opaque", [x["title"] for x in d.get("query", {}).get("search", [])])

d = api(REMOTE+"/api.php", action="query", list="search", srsearch="items-table", srnamespace="8", srlimit=10, format="json")
print("search items-table ns8", [x["title"] for x in d.get("query", {}).get("search", [])])
PY

# dump remote Common.css size of color vars section vs our items-tables
wc -c /home/ss14_user/ministation_wiki/skins/MiniStation/resources/items-tables.css /tmp/remote_Common.css 2>/dev/null || true
# show remote skin name from parse
python3 - <<'PY'
import json,urllib.parse,urllib.request,re
UA={"User-Agent":"ms"}
html=urllib.request.urlopen(urllib.request.Request('https://wiki.ss220.club/index.php/%D0%A0%D1%83%D0%BA%D0%BE%D0%B2%D0%BE%D0%B4%D1%81%D1%82%D0%B2%D0%BE_%D0%BF%D0%BE_%D1%81%D1%82%D1%80%D0%BE%D0%B8%D1%82%D0%B5%D0%BB%D1%8C%D1%81%D1%82%D0%B2%D1%83', headers=UA), timeout=60).read().decode('utf-8','replace')
print('remote skin class', re.search(r'class=\"([^\"]*skin-[^\"]*)\"', html))
print('data-theme', re.search(r'data-theme=\"([^\"]+)\"', html))
# extract :root or --engineer from inline/style
for pat in ['--engineer-opaque', '--color-second-fill', 'items-tables', 'Theme', 'citizen', 'cosmos', 'timeless']:
    print(pat, html.lower().count(pat.lower()))
# list stylesheet urls containing theme/common/gadget
for h in re.findall(r'href=\"(/[^\"]+\.css[^\"]*|https://[^\"]+\.css[^\"]*)\"', html):
    if any(x in h.lower() for x in ['common','theme','gadget','citizen','vector','site','skin']):
        print('STY', h[:160])
PY
