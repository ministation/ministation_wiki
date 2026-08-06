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

LOCAL = "http://127.0.0.1:3000/api.php"
UA = {"User-Agent": "ministation-purge", "Content-Type": "application/x-www-form-urlencoded"}


def get(**kw):
    q = urllib.parse.urlencode(kw)
    req = urllib.request.Request(LOCAL + "?" + q, headers={"User-Agent": "ministation-purge"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def post(**kw):
    req = urllib.request.Request(LOCAL, data=urllib.parse.urlencode(kw).encode(), headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode())


titles: list[str] = []
for eititle in ("Шаблон:Якорь", "Шаблон:Anchor"):
    cont: dict = {}
    while True:
        d = get(
            action="query",
            list="embeddedin",
            eititle=eititle,
            eilimit=500,
            format="json",
            **cont,
        )
        titles.extend(p["title"] for p in d.get("query", {}).get("embeddedin", []))
        cont = d.get("continue") or {}
        if not cont:
            break

titles = sorted(set(titles) | {"Руководство по строительству", "Заглавная страница"})
print("purging", len(titles), "pages")
for i in range(0, len(titles), 40):
    chunk = titles[i : i + 40]
    d = post(
        action="purge",
        titles="|".join(chunk),
        forcerecursivelinkupdate="1",
        format="json",
    )
    print(" chunk", i, "purged", len(d.get("purge", [])))
    time.sleep(0.05)

# also null-touch via maintenance if needed
d = post(
    action="parse",
    page="Руководство по строительству",
    prop="text",
    disablelimitreport="1",
    format="json",
)
html = d["parse"]["text"]["*"]
idx = html.find("Монтировка")
snip = html[max(0, idx - 250) : idx + 100].replace("\n", " ")
print("SNIP:", snip)
print("redlink still?", "страница не существует" in html and "Якорь" in html)
print("has Crowbar span?", 'id="Crowbar"' in html)
PY
EOS

# force DB touch + CDN purge for the construction page
sudo -u ss14_user -H bash <<'EOS'
cd /home/ss14_user/ministation_wiki
source .venv/bin/activate
set -a; . ./.env; set +a
echo 'Руководство по строительству' | php mediawiki/maintenance/run.php purgeList --db-touch --verbose
EOS
