#!/bin/bash
set -euo pipefail
python3 <<'PY'
import json, re, urllib.parse, urllib.request
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 ministation-compare"}

def api(base, **kw):
    req = urllib.request.Request(base + "?" + urllib.parse.urlencode(kw), headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode())

def head_str(h):
    if isinstance(h, dict):
        return h.get("*") or h.get("headhtml") or json.dumps(h)[:500]
    return h or ""

LOCAL = "http://127.0.0.1:3000"
REMOTE = "https://wiki.ss220.club"

for name, base, title in [
    ("local", LOCAL + "/api.php", "Руководство по строительству"),
    ("remote", REMOTE + "/api.php", "Руководство по строительству"),
]:
    d = api(base, action="parse", page=title, prop="text|headhtml", disablelimitreport=1, format="json")
    html = d["parse"]["text"]["*"] if isinstance(d["parse"]["text"], dict) else d["parse"]["text"]
    if isinstance(html, dict):
        html = html.get("*", "")
    head = head_str(d["parse"].get("headhtml", ""))
    m = re.search(r"<table[^>]*items-table[^>]*>", html)
    print(f"=== {name} table tag ===")
    print(m.group(0) if m else "NONE")
    m2 = re.search(r"<table[^>]*items-table[\s\S]{0,3000}</tr>", html)
    frag = m2.group(0) if m2 else ""
    print("classes:", sorted(set(re.findall(r'class="([^"]+)"', frag)))[:25])
    print("broken media count in page", html.count("mw-broken-media"))
    print("file img count", html.count("<img"))
    css_hrefs = re.findall(r'href="([^"]+\.css[^"]*)"', head)
    print("css hrefs from parse head", len(css_hrefs))
    Path(f"/tmp/{name}_table_frag.html").write_text(frag[:5000], encoding="utf-8")

# Full page HTML comparison for stylesheets + CSS variables
for name, url in [
    ("local", "http://127.0.0.1:3000/index.php/%D0%A0%D1%83%D0%BA%D0%BE%D0%B2%D0%BE%D0%B4%D1%81%D1%82%D0%B2%D0%BE_%D0%BF%D0%BE_%D1%81%D1%82%D1%80%D0%BE%D0%B8%D1%82%D0%B5%D0%BB%D1%8C%D1%81%D1%82%D0%B2%D1%83"),
    ("remote", "https://wiki.ss220.club/index.php/%D0%A0%D1%83%D0%BA%D0%BE%D0%B2%D0%BE%D0%B4%D1%81%D1%82%D0%B2%D0%BE_%D0%BF%D0%BE_%D1%81%D1%82%D1%80%D0%BE%D0%B8%D1%82%D0%B5%D0%BB%D1%8C%D1%81%D1%82%D0%B2%D1%83"),
]:
    req = urllib.request.Request(url, headers=UA)
    html = urllib.request.urlopen(req, timeout=90).read().decode("utf-8", "replace")
    print(f"\n=== {name} full page ===")
    skin = re.search(r'class="[^"]*\b(skin-\w+)[^"]*"', html)
    print("skin", skin.group(1) if skin else None)
    theme = re.search(r'data-theme="([^"]+)"', html)
    print("theme", theme.group(1) if theme else None)
    print("--engineer-opaque defs", len(re.findall(r"--engineer-opaque\s*:", html)))
    print(".items-table defs", len(re.findall(r"\.items-table\s*\{", html)))
    print(".colors-engine defs", len(re.findall(r"\.colors-engine", html)))
    # collect RL style modules
    for m in re.findall(r"modules=([^&\"']+)", html):
        mods = urllib.parse.unquote(m.replace("&amp;", "&"))
        if "site" in mods or "gadget" in mods or "theme" in mods or "citizen" in mods or "cosmos" in mods:
            print(" RL", mods[:160])
    # gadget / theme css urls
    for h in re.findall(r'href="([^"]+)"', html):
        hl = h.lower()
        if any(x in hl for x in ["gadget", "theme", "common.css", "citizen", "vector", "site.styles"]):
            if ".css" in hl or "only=styles" in hl:
                print(" STY", h[:180])

# Find where remote defines CSS variables - search all CSS pages
print("\n=== remote CSS var sources ===")
d = api(REMOTE + "/api.php", action="query", list="allpages", apnamespace=8, apprefix="", aplimit=200, format="json")
css_pages = [p["title"] for p in d["query"]["allpages"] if p["title"].endswith(".css")]
print("css pages", css_pages[:40], "total", len(css_pages))
# check which contain engineer-opaque
for title in css_pages:
    p = list(api(REMOTE+"/api.php", action="query", titles=title, prop="revisions", rvprop="content", rvslots="main", format="json")["query"]["pages"].values())[0]
    if "missing" in p:
        continue
    body = p["revisions"][0]["slots"]["main"]["*"]
    if "engineer-opaque" in body or "items-table" in body:
        print(title, "len", len(body), "engineer" , "engineer-opaque" in body, "items-table", "items-table" in body)
PY
