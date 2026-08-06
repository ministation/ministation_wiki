#!/bin/bash
set -euo pipefail
python3 <<'PY'
import json, urllib.parse, urllib.request, re

LOCAL = "http://127.0.0.1:3000/api.php"
REMOTE = "https://wiki.ss220.club/api.php"

def get(api, **kw):
    req = urllib.request.Request(
        api + "?" + urllib.parse.urlencode(kw),
        headers={"User-Agent": "ministation"},
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode())

for api, name in [(REMOTE, "remote"), (LOCAL, "local")]:
    p = list(get(api, action="query", titles="MediaWiki:Common.css", prop="revisions", rvprop="content|size", rvslots="main", format="json")["query"]["pages"].values())[0]
    if "missing" in p:
        print(name, "Common.css MISSING")
        continue
    css = p["revisions"][0]["slots"]["main"]["*"]
    print(name, "Common.css bytes", len(css))
    for pat in ["items-table", "colors-engine", "weapon-table", ".capital", "colors-medik", "colors-science"]:
        print(" ", pat, css.count(pat))
    # dump items-table related blocks
    if name == "remote":
        # extract chunks mentioning items-table
        idxs = [m.start() for m in re.finditer(r"items-table", css)]
        print(" occurrences", len(idxs))
        # save full remote common.css
        open("/tmp/remote_Common.css", "w", encoding="utf-8").write(css)
        # also try Common.js / gadgets
    else:
        open("/tmp/local_Common.css", "w", encoding="utf-8").write(css)

# remote skin CSS?
for t in ["MediaWiki:Common.css", "MediaWiki:Vector.css", "MediaWiki:Vector-2022.css", "MediaWiki:Citizen.css", "MediaWiki:Fandomdesktop.css", "MediaWiki:Theme-dark.css"]:
    p = list(get(REMOTE, action="query", titles=t, format="json")["query"]["pages"].values())[0]
    print("remote", t, "MISS" if "missing" in p else "ok")

# check local skin resources for items-table
import pathlib
root = pathlib.Path("/home/ss14_user/ministation_wiki/skins/MiniStation/resources")
for f in root.glob("*.css"):
    txt = f.read_text(encoding="utf-8", errors="replace")
    if "items-table" in txt or "colors-engine" in txt:
        print("skin has", f.name)
print("skin files", [p.name for p in root.glob("*.css")])
PY
# show a slice of remote items-table CSS
python3 - <<'PY'
from pathlib import Path
css = Path('/tmp/remote_Common.css').read_text(encoding='utf-8')
# find first items-table rule block - print 200 lines around
lines = css.splitlines()
for i,l in enumerate(lines):
    if 'items-table' in l:
        start=max(0,i-2); end=min(len(lines), i+80)
        print('\n'.join(f'{n+1}:{lines[n]}' for n in range(start,end)))
        print('---')
        if i>2000: break
        # print a few more clusters
PY
