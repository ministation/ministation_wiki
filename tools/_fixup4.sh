#!/bin/bash
set -euo pipefail
ROOT=/home/ss14_user/ministation_wiki
cp /tmp/rsi.py "$ROOT/app/sprites/rsi.py"
sed -i 's/\r$//' "$ROOT/app/sprites/rsi.py"
chown ss14_user:ss14_user "$ROOT/app/sprites/rsi.py"

sudo -u ss14_user -H bash <<'EOS'
set -euo pipefail
cd /home/ss14_user/ministation_wiki
source .venv/bin/activate
set -a; . ./.env; set +a
python3 <<'PY'
from app.sprites.rsi import extract_frame, _load_meta, resolve_rsi
from tools.migrate import edit_page

d, s = resolve_rsi("Objects/Tools/crowbar.rsi/icon")
print("meta", _load_meta(d).get("size"), "states", len(_load_meta(d).get("states") or []))
p = extract_frame("Objects/Tools/crowbar.rsi/icon")
print("png", p, p.stat().st_size)

edit_page(
    "Шаблон:DepartmentTabs/styles",
    "#REDIRECT [[Шаблон:DepartmentTabs/styles.css]]",
    summary="styles alias",
)
print("redir ok")
PY
EOS

systemctl restart ministation-wiki-sprites
sleep 2
curl -s http://127.0.0.1:3001/health; echo
curl -s -o /tmp/crowbar.png -w 'crowbar http:%{http_code} size:%{size_download}\n' \
  'http://127.0.0.1:3001/sprite/Objects/Tools/crowbar.rsi/icon'
file /tmp/crowbar.png

# also try a few more sprites
for path in \
  'Objects/Weapons/Melee/knife.rsi/icon' \
  'Interface/Actions/actions_melee.rsi/wide-attack' \
  'Mobs/Species/Human/parts.rsi/full'
do
  curl -s -o /tmp/s.png -w "$path -> %{http_code} %{size_download}\n" \
    "http://127.0.0.1:3001/sprite/$path" || true
done
