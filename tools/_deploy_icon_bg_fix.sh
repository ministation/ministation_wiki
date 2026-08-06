#!/bin/bash
set -euo pipefail
ROOT=/home/ss14_user/ministation_wiki
cp /tmp/skin.css "$ROOT/skins/MiniStation/resources/skin.css"
cp /tmp/setup.py "$ROOT/tools/setup.py"
sed -i 's/\r$//' "$ROOT/skins/MiniStation/resources/skin.css" "$ROOT/tools/setup.py"
chown ss14_user:ss14_user "$ROOT/skins/MiniStation/resources/skin.css" "$ROOT/tools/setup.py"

sudo -u ss14_user -H bash <<'EOS'
set -euo pipefail
cd /home/ss14_user/ministation_wiki
source .venv/bin/activate
set -a; . ./.env; set +a
python3 -c 'from tools.setup import write_custom_settings_snippet; write_custom_settings_snippet()'
EOS

grep -n 'skin.css?v=' "$ROOT/config/LocalSettings.custom.php"
grep -n 'transparent !important' "$ROOT/skins/MiniStation/resources/skin.css" | head
# quick check page has new css version
curl -s 'http://127.0.0.1:3000/index.php/%D0%A0%D1%83%D0%BA%D0%BE%D0%B2%D0%BE%D0%B4%D1%81%D1%82%D0%B2%D0%BE_%D0%BF%D0%BE_%D1%81%D1%82%D1%80%D0%BE%D0%B8%D1%82%D0%B5%D0%BB%D1%8C%D1%81%D1%82%D0%B2%D1%83' \
  | grep -o 'skin.css?v=[^\"'\'']*' | head -3
