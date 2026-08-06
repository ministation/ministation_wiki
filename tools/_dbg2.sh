#!/bin/bash
set -euo pipefail
ROOT=/home/ss14_user/ministation_wiki
cp /tmp/rsi.py "$ROOT/app/sprites/rsi.py"
cp /tmp/_finish_templates_sprites.py "$ROOT/tools/_finish_templates_sprites.py"
sed -i 's/\r$//' "$ROOT/app/sprites/rsi.py" "$ROOT/tools/_finish_templates_sprites.py"
chown ss14_user:ss14_user "$ROOT/app/sprites/rsi.py" "$ROOT/tools/_finish_templates_sprites.py"

# show exact bad bytes around copyright
python3 - <<'PY'
from pathlib import Path
raw = Path('/home/ss14_user/ministation_wiki/data/ss14_repo/Resources/Textures/Objects/Tools/crowbar.rsi/meta.json').read_bytes()
# find line 4
lines = raw.split(b'\n')
print('nlines', len(lines))
L = lines[3]
print('line4 len', len(L))
print(L)
for i,b in enumerate(L):
    if b < 32:
        print('bad', i, b)
# try json after strip all <32
import json,re
text = raw.decode('utf-8-sig')
text = re.sub(r'//.*?$', '', text, flags=re.M)
text2 = ''.join(ch for ch in text if ord(ch) >= 32)
try:
    json.loads(text)
    print('raw json OK')
except Exception as e:
    print('raw json FAIL', e)
try:
    json.loads(text2)
    print('stripped json OK', list(json.loads(text2).get('size').items()))
except Exception as e:
    print('stripped FAIL', e)
PY

# test module directly
sudo -u ss14_user -H bash <<'EOS'
cd /home/ss14_user/ministation_wiki
source .venv/bin/activate
set -a; . ./.env; set +a
python3 - <<'PY'
from app.sprites.rsi import extract_frame, _load_meta, resolve_rsi
from pathlib import Path
print('SS14', __import__('app.config', fromlist=['SS14_RESOURCES']).SS14_RESOURCES)
try:
    d,s = resolve_rsi('Objects/Tools/crowbar.rsi/icon')
    print('resolved', d, s)
    print(_load_meta(d).get('size'))
    out = extract_frame('Objects/Tools/crowbar.rsi/icon')
    print('out', out, out.stat().st_size)
except Exception as e:
    print('ERR', type(e), e)
PY
EOS

# dump sanitized failing CSS
sudo -u ss14_user -H bash <<'EOS'
cd /home/ss14_user/ministation_wiki
source .venv/bin/activate
set -a; . ./.env; set +a
python3 - <<'PY'
from pathlib import Path
from tools._finish_templates_sprites import sanitize_css_for_templatestyles, save_styles_css, _read_import_body
for name in ['Шаблон_DepartmentTabs__styles.css.wiki','Шаблон_PageButton__styles.css.wiki','Шаблон_JobPageHeader__styles.css.wiki']:
    title, body = _read_import_body(Path('content/import/remote')/name)
    css = sanitize_css_for_templatestyles(body)
    print('====', title, '====')
    print(css)
    print('SAVE', save_styles_css(title, body))
    print()
PY
EOS
