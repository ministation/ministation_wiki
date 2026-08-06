#!/bin/bash
set -euo pipefail
ROOT=/home/ss14_user/ministation_wiki
# bump cache buster in custom settings via setup
sed -i 's/items-tables\.css?v=[^'\''"]*/items-tables.css?v=20260802b/' \
  "$ROOT/config/LocalSettings.custom.php" || true
sed -i 's/mainpage-widgets\.css?v=[^'\''"]*/mainpage-widgets.css?v=20260802n/' \
  "$ROOT/config/LocalSettings.custom.php" || true

sudo -u ss14_user -H bash <<'EOS'
set -euo pipefail
cd /home/ss14_user/ministation_wiki
source .venv/bin/activate
set -a; . ./.env; set +a

# refresh custom settings from tools/setup.py (includes items-tables)
python3 - <<'PY'
from tools.setup import write_custom_settings_snippet
from tools.migrate import edit_page
from pathlib import Path
write_custom_settings_snippet()
css = Path("skins/MiniStation/resources/items-tables.css").read_text(encoding="utf-8")
edit_page("MediaWiki:Common.css", css, summary="TGUI-like item tables + palette")
print("Common.css", len(css))
PY

# import downloaded images
php mediawiki/maintenance/run.php importImages.php \
  /home/ss14_user/ministation_wiki/data/remote_images \
  --overwrite \
  --user=Admin \
  --comment="import construction guide sprites" \
  2>&1 | tail -30

python3 - <<'PY'
import json, urllib.parse, urllib.request
LOCAL = "http://127.0.0.1:3000/api.php"

def post(**kw):
    req = urllib.request.Request(
        LOCAL,
        data=urllib.parse.urlencode(kw).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "ms"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode())

# null-edit construction page to bust parser cache for images
d = json.loads(
    urllib.request.urlopen(
        LOCAL
        + "?"
        + urllib.parse.urlencode({
            "action": "query",
            "titles": "Руководство по строительству",
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
            "format": "json",
        }),
        timeout=60,
    ).read().decode()
)
body = list(d["query"]["pages"].values())[0]["revisions"][0]["slots"]["main"]["*"]
from tools.migrate import edit_page
edit_page("Руководство по строительству", body, summary="null edit: refresh table images/styles")
post(action="purge", titles="Руководство по строительству|MediaWiki:Common.css", format="json")

# verify
for t in ["Файл:Crowbar.png", "Файл:JawsLife.png", "Файл:Welder.png", "Файл:Wirecutters.png"]:
    d = json.loads(
        urllib.request.urlopen(
            LOCAL + "?" + urllib.parse.urlencode({"action": "query", "titles": t, "format": "json"}),
            timeout=30,
        ).read().decode()
    )
    p = list(d["query"]["pages"].values())[0]
    print(t, "MISS" if "missing" in p else "ok")

html = urllib.request.urlopen(
    "http://127.0.0.1:3000/index.php/%D0%A0%D1%83%D0%BA%D0%BE%D0%B2%D0%BE%D0%B4%D1%81%D1%82%D0%B2%D0%BE_%D0%BF%D0%BE_%D1%81%D1%82%D1%80%D0%BE%D0%B8%D1%82%D0%B5%D0%BB%D1%8C%D1%81%D1%82%D0%B2%D1%83",
    timeout=60,
).read().decode("utf-8", "replace")
print("broken-media", html.count("mw-broken-media"))
print("img tags", html.count("<img"))
print("outset border in css?", "outset" in html)
print("color-mix in css?", "color-mix" in html)
print("items-tables v?", "items-tables.css?v=" in html)
PY
EOS
