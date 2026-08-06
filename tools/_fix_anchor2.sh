#!/bin/bash
set -euo pipefail
cd /home/ss14_user/ministation_wiki
sudo -u ss14_user -H bash <<'EOS'
set -euo pipefail
cd /home/ss14_user/ministation_wiki
source .venv/bin/activate
set -a; . ./.env; set +a

python3 <<'PY'
import json
import time
import urllib.parse
import urllib.request
from tools.migrate import edit_page

LOCAL = "http://127.0.0.1:3000/api.php"


def get(**kw):
    q = urllib.parse.urlencode(kw)
    req = urllib.request.Request(LOCAL + "?" + q, headers={"User-Agent": "ms"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def post(**kw):
    req = urllib.request.Request(
        LOCAL,
        data=urllib.parse.urlencode(kw).encode(),
        headers={
            "User-Agent": "ms",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


# Ensure template content is correct (not redirect)
from pathlib import Path
raw = Path("content/import/remote/Шаблон_Якорь.wiki").read_text(encoding="utf-8")
if raw.startswith("<!--"):
    body = raw[raw.find("-->") + 3 :].lstrip("\n")
else:
    body = raw
edit_page("Шаблон:Якорь", body, summary="ensure Якорь template")
edit_page("Шаблон:Anchor", "#REDIRECT [[Шаблон:Якорь]]", summary="alias")

# Null-edit construction guide to bust parser cache
d = get(
    action="query",
    titles="Руководство по строительству",
    prop="revisions",
    rvprop="content",
    rvslots="main",
    format="json",
)
page_body = list(d["query"]["pages"].values())[0]["revisions"][0]["slots"]["main"]["*"]
edit_page("Руководство по строительству", page_body, summary="null edit: refresh Якорь")

# Purge one-by-one (avoid 500 on big batches)
titles = ["Руководство по строительству", "Шаблон:Якорь", "Шаблон:Anchor"]
cont: dict = {}
while True:
    d = get(
        action="query",
        list="embeddedin",
        eititle="Шаблон:Якорь",
        eilimit=100,
        format="json",
        **cont,
    )
    titles.extend(p["title"] for p in d.get("query", {}).get("embeddedin", []))
    cont = d.get("continue") or {}
    if not cont:
        break

titles = sorted(set(titles))
print("purge one-by-one", len(titles))
ok = fail = 0
for t in titles:
    try:
        post(action="purge", titles=t, format="json")
        ok += 1
    except Exception as e:
        fail += 1
        if fail < 5:
            print("fail", t, e)
    if ok % 50 == 0:
        print("…", ok)
print("purged", ok, "fail", fail)

d = post(
    action="parse",
    page="Руководство по строительству",
    prop="text",
    disablelimitreport="1",
    format="json",
)
html = d["parse"]["text"]["*"]
idx = html.find("Монтировка")
print("SNIP:", html[max(0, idx - 220) : idx + 80].replace("\n", " "))
print("redlink?", 'title="Шаблон:Якорь (страница не существует)"' in html)
print("Crowbar span?", 'id="Crowbar"' in html)
PY
EOS
