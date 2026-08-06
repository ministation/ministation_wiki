#!/bin/bash
set -euo pipefail
ROOT=/home/ss14_user/ministation_wiki
cp /tmp/rsi.py "$ROOT/app/sprites/rsi.py"
cp /tmp/_finish_templates_sprites.py "$ROOT/tools/_finish_templates_sprites.py"
sed -i 's/\r$//' "$ROOT/app/sprites/rsi.py" "$ROOT/tools/_finish_templates_sprites.py"
chown ss14_user:ss14_user "$ROOT/app/sprites/rsi.py" "$ROOT/tools/_finish_templates_sprites.py"

sudo -u ss14_user -H bash <<'EOS'
set -euo pipefail
cd /home/ss14_user/ministation_wiki
source .venv/bin/activate
set -a; . ./.env; set +a
python3 <<'PY'
from pathlib import Path
from tools._finish_templates_sprites import save_styles_css, _read_import_body
from app.sprites.rsi import extract_frame, _load_meta, resolve_rsi

for name in [
    "Шаблон_PageButton__styles.css.wiki",
    "Шаблон_JobPageHeader__styles.css.wiki",
    "Шаблон_DepartmentTabs__styles.css.wiki",
]:
    title, body = _read_import_body(Path("content/import/remote") / name)
    print(title, save_styles_css(title, body))

d, s = resolve_rsi("Objects/Tools/crowbar.rsi/icon")
print("meta", _load_meta(d).get("size"))
out = extract_frame("Objects/Tools/crowbar.rsi/icon")
print("png", out, out.stat().st_size)

# DepartmentTabs/styles redirect
from tools.migrate import edit_page
edit_page(
    "Шаблон:DepartmentTabs/styles",
    "#REDIRECT [[Шаблон:DepartmentTabs/styles.css]]",
    summary="styles alias",
)
print("redir DepartmentTabs/styles")
PY
EOS

systemctl restart ministation-wiki-sprites
sleep 2
curl -s http://127.0.0.1:3001/health; echo
curl -s -o /tmp/crowbar.png -w 'crowbar http:%{http_code} size:%{size_download}\n' \
  'http://127.0.0.1:3001/sprite/Objects/Tools/crowbar.rsi/icon'
file /tmp/crowbar.png

python3 <<'PY'
import json, urllib.parse, urllib.request
def exists(t):
    d=json.loads(urllib.request.urlopen('http://127.0.0.1:3000/api.php?'+urllib.parse.urlencode({'action':'query','titles':t,'format':'json'}),timeout=20).read().decode())
    p=list(d['query']['pages'].values())[0]
    return 'missing' not in p
for t in [
 'Шаблон:PageButton/styles.css','Шаблон:JobPageHeader/styles.css',
 'Шаблон:DepartmentTabs/styles.css','Шаблон:DepartmentTabs/styles',
 'Шаблон:PageList/styles.css','Шаблон:Pageframe/styles.css']:
    print(t, 'ok' if exists(t) else 'MISSING')
PY
