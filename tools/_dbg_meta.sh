#!/bin/bash
set -euo pipefail
META=/home/ss14_user/ministation_wiki/data/ss14_repo/Resources/Textures/Objects/Tools/crowbar.rsi/meta.json
python3 - <<'PY'
from pathlib import Path
p = Path('/home/ss14_user/ministation_wiki/data/ss14_repo/Resources/Textures/Objects/Tools/crowbar.rsi/meta.json')
raw = p.read_bytes()
print('len', len(raw))
print(raw[:250])
for i,b in enumerate(raw):
    if b < 32 and b not in (9, 10, 13):
        print('ctrl at', i, b, repr(raw[max(0,i-20):i+20]))
PY
# show line 4
sed -n '1,8p' "$META" | cat -A
