#!/bin/bash
set -euo pipefail
ROOT=/home/ss14_user/ministation_wiki
cp /tmp/mediawiki_ministationSetSanitizedCss.php "$ROOT/mediawiki/maintenance/ministationSetSanitizedCss.php"
cp /tmp/_finish_templates_sprites.py "$ROOT/tools/_finish_templates_sprites.py"
chown ss14_user:ss14_user \
  "$ROOT/mediawiki/maintenance/ministationSetSanitizedCss.php" \
  "$ROOT/tools/_finish_templates_sprites.py"

python3 <<'PY'
from pathlib import Path
p = Path('/home/ss14_user/ministation_wiki/content/import/remote')
cands = list(p.glob('*Pageframe*styles*'))
print('cands', cands)
raw = cands[0].read_text(encoding='utf-8')
body = raw[raw.find('-->')+3:].strip() if raw.startswith('<!--') else raw.strip()
Path('/tmp/pageframe.css').write_text(body, encoding='utf-8')
print('bytes', len(body))
PY

sudo -u ss14_user -H bash <<'EOS'
set -e
cd /home/ss14_user/ministation_wiki
source .venv/bin/activate
set -a; . ./.env; set +a
php mediawiki/maintenance/run.php ministationSetSanitizedCss.php "Шаблон:Pageframe/styles.css" < /tmp/pageframe.css
EOS

python3 <<'PY'
import json, urllib.parse, urllib.request
q = urllib.parse.urlencode({
    'action': 'query',
    'titles': 'Шаблон:Pageframe/styles.css',
    'prop': 'revisions',
    'rvprop': 'size|contentmodel|content',
    'rvslots': 'main',
    'format': 'json',
})
d = json.loads(urllib.request.urlopen('http://127.0.0.1:3000/api.php?' + q, timeout=30).read().decode())
page = list(d['query']['pages'].values())[0]
print(json.dumps({
    'missing': 'missing' in page,
    'pageid': page.get('pageid'),
    'title': page.get('title'),
    'revisions': page.get('revisions'),
}, ensure_ascii=False)[:800])
PY

echo "=== resources / baby ==="
ls -d "$ROOT/data/ss14_repo/Resources" 2>/dev/null || true
find "$ROOT/data/ss14_repo" -maxdepth 4 -type d -name Textures 2>/dev/null | head
ls "$ROOT/data/mini_images" 2>/dev/null | head -40
ls "$ROOT/data/mini_images"/Baby* "$ROOT/data/mini_images"/baby* 2>/dev/null || true
