#!/bin/bash
set -euo pipefail
ROOT=/home/ss14_user/ministation_wiki
# sync templates from /tmp/mainpage
for f in Antags Jobs Lore Guides Items Baby; do
  src="/tmp/Шаблон_MainPage__${f}.wiki"
  dst="$ROOT/content/import/remote/Шаблон_MainPage__${f}.wiki"
  if [ -f "$src" ]; then
    cp "$src" "$dst"
    sed -i 's/\r$//' "$dst"
    chown ss14_user:ss14_user "$dst"
  fi
done

sudo -u ss14_user -H bash <<'EOS'
set -euo pipefail
cd /home/ss14_user/ministation_wiki
source .venv/bin/activate
set -a; . ./.env; set +a
python3 <<'PY'
from pathlib import Path
from tools.migrate import edit_page

ROOT = Path("content/import/remote")
mapping = {
    "Шаблон_MainPage__Antags.wiki": "Шаблон:MainPage/Antags",
    "Шаблон_MainPage__Jobs.wiki": "Шаблон:MainPage/Jobs",
    "Шаблон_MainPage__Lore.wiki": "Шаблон:MainPage/Lore",
    "Шаблон_MainPage__Guides.wiki": "Шаблон:MainPage/Guides",
    "Шаблон_MainPage__Items.wiki": "Шаблон:MainPage/Items",
    "Шаблон_MainPage__Baby.wiki": "Шаблон:MainPage/Baby",
}
for fname, title in mapping.items():
    path = ROOT / fname
    body = path.read_text(encoding="utf-8")
    if body.startswith("<!--"):
        end = body.find("-->")
        if end > 0:
            body = body[end + 3 :].lstrip("\n")
    edit_page(title, body, summary="MiniStation mainpage widgets")
    print("OK", title)

# alias Агент → Предатель
edit_page("Агент", "#REDIRECT [[Предатель]]", summary="alias for MiniStation agent antag")
print("OK Агент redirect")

# lightweight MiniStation lore page
lore = """Мини-станция — русскоязычный сервер Space Station 14 на базе сборки mini-station-goob.

== Фракции ==
* [[NanoTrasen]] — корпорация, владеющая станцией.
* [[Синдикат]] — противник NT; аплинк и оперативники.
* ЦентКом / ERT — ответ на крупные кризисы (см. [[Jobs]]).

== Расы ==
В билде доступны, среди прочих: человек, унатх, слайм, ниан, дионея, вокс, вульпканин, таяран, КПБ, плазмамен и другие из сборки.

== Антагонисты ==
Список актуальных ролей — в каталоге антаг-токенов и на [[Заглавная страница|заглавной]].

== См. также ==
* [[Правила Сервера]]
* [[Руководство для новичков]]
* [[Jobs]]
"""
edit_page("Лор", lore, summary="MiniStation lore hub")
print("OK Лор")
PY
EOS

# purge main page
python3 <<'PY'
import json,urllib.parse,urllib.request
LOCAL='http://127.0.0.1:3000/api.php'
# login not needed for purge via API sometimes; try
data=urllib.parse.urlencode({'action':'purge','titles':'Заглавная страница','format':'json'}).encode()
req=urllib.request.Request(LOCAL, data=data, headers={'User-Agent':'ministation','Content-Type':'application/x-www-form-urlencoded'})
print(urllib.request.urlopen(req, timeout=30).read().decode()[:300])
# verify antags no longer paradise
q=urllib.parse.urlencode({'action':'query','titles':'Шаблон:MainPage/Antags','prop':'revisions','rvprop':'content','rvslots':'main','format':'json'})
d=json.loads(urllib.request.urlopen(LOCAL+'?'+q,timeout=30).read().decode())
body=list(d['query']['pages'].values())[0]['revisions'][0]['slots']['main']['*']
for bad in ['Vampire','Вампир','Blood_Brothers','Контрактник','Братья по крови','Agent.png']:
    print(bad, 'FOUND' if bad in body else 'gone')
for good in ['Mini_antag_thief','Mini_antag_traitor','Вор','Агент']:
    print(good, 'ok' if good in body else 'MISSING')
PY
