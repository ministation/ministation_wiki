#!/bin/bash
set -euo pipefail
ROOT=/home/ss14_user/ministation_wiki
cp /tmp/_finish_templates_sprites.py "$ROOT/tools/_finish_templates_sprites.py"
cp /tmp/rsi.py "$ROOT/app/sprites/rsi.py"
chown ss14_user:ss14_user "$ROOT/tools/_finish_templates_sprites.py" "$ROOT/app/sprites/rsi.py"
sed -i 's/\r$//' "$ROOT/tools/_finish_templates_sprites.py" "$ROOT/app/sprites/rsi.py"

sudo -u ss14_user -H bash <<'EOS'
set -euo pipefail
cd /home/ss14_user/ministation_wiki
source .venv/bin/activate
set -a; . ./.env; set +a
python3 <<'PY'
import os, sys
from tools._finish_templates_sprites import (
    REMOTE, allpages, LOCAL, apply_missing, apply_path, IMPORT, REDIRECT_ALIASES, verify
)
from pathlib import Path

# re-apply all styles + missing aliases without remote refetch
remote = allpages(REMOTE, 10) if REMOTE else set()
local = allpages(LOCAL, 10)
missing = sorted(remote - local) if remote else []
print('missing before apply', len(missing))
# ensure renamed targets exist from disk
for path in IMPORT.glob('*.wiki'):
    name = path.name
    if 'styles.css' in name:
        continue
    # apply key renamed templates explicitly
apply_missing(missing)

# force-apply important renamed pages from disk
for title in sorted(set(REDIRECT_ALIASES.values())):
    # find by meta title
    for path in IMPORT.glob('*.wiki'):
        from tools._finish_templates_sprites import _read_import_body
        t, _ = _read_import_body(path)
        if t == title:
            apply_path(path, title)
            break

verify()
PY
EOS

systemctl restart ministation-wiki-sprites
sleep 2
echo '=== health ==='
curl -s http://127.0.0.1:3001/health; echo
echo '=== crowbar ==='
curl -s -o /tmp/crowbar.png -w 'http:%{http_code} bytes:%{size_download}\n' \
  'http://127.0.0.1:3001/sprite/Objects/Tools/crowbar.rsi/icon'
file /tmp/crowbar.png
