#!/bin/bash
set -euo pipefail
ROOT=/home/ss14_user/ministation_wiki

cp /tmp/items-tables.css "$ROOT/skins/MiniStation/resources/items-tables.css"
cp /tmp/mainpage-widgets.css "$ROOT/skins/MiniStation/resources/mainpage-widgets.css"
cp /tmp/setup.py "$ROOT/tools/setup.py"
sed -i 's/\r$//' \
  "$ROOT/skins/MiniStation/resources/items-tables.css" \
  "$ROOT/skins/MiniStation/resources/mainpage-widgets.css" \
  "$ROOT/tools/setup.py"
chown -R ss14_user:ss14_user "$ROOT/skins/MiniStation/resources" "$ROOT/tools/setup.py"

sudo -u ss14_user -H bash <<'EOS'
set -euo pipefail
cd /home/ss14_user/ministation_wiki
source .venv/bin/activate
set -a; . ./.env; set +a

python3 <<'PY'
from tools.setup import write_custom_settings_snippet
from tools.migrate import edit_page

write_custom_settings_snippet()
print("custom settings refreshed")

css = open("skins/MiniStation/resources/items-tables.css", encoding="utf-8").read()
edit_page("MediaWiki:Common.css", css, summary="item/dept colored tables")
print("Common.css written", len(css))
PY

python3 <<'PY'
import json, urllib.parse, urllib.request
LOCAL = "http://127.0.0.1:3000/api.php"
req = urllib.request.Request(
    LOCAL,
    data=urllib.parse.urlencode({
        "action": "purge",
        "titles": "Руководство по строительству|MediaWiki:Common.css",
        "format": "json",
    }).encode(),
    headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "ms"},
)
print(urllib.request.urlopen(req, timeout=30).read().decode()[:240])

d = json.loads(
    urllib.request.urlopen(
        LOCAL
        + "?"
        + urllib.parse.urlencode({
            "action": "parse",
            "page": "Руководство по строительству",
            "prop": "headhtml|text",
            "disablelimitreport": 1,
            "format": "json",
        }),
        timeout=60,
    ).read().decode()
)
head = d["parse"].get("headhtml", "")
html = d["parse"]["text"]["*"]
print("items-tables.css linked?", "items-tables.css" in head)
print("inline .items-table?", ".items-table" in head)
print("inline .colors-engine?", ".colors-engine" in head)
print("table class present?", "colors-engine" in html)
# Common.css via RL
print("site.styles?", "site.styles" in head or "ext.gadget" in head)
PY
EOS
