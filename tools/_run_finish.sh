#!/bin/bash
set -euo pipefail
ROOT=/home/ss14_user/ministation_wiki
cp /tmp/mediawiki_ministationSetSanitizedCss.php "$ROOT/mediawiki/maintenance/ministationSetSanitizedCss.php"
cp /tmp/_finish_templates_sprites.py "$ROOT/tools/_finish_templates_sprites.py"
chown ss14_user:ss14_user \
  "$ROOT/mediawiki/maintenance/ministationSetSanitizedCss.php" \
  "$ROOT/tools/_finish_templates_sprites.py"
sed -i 's/\r$//' "$ROOT/tools/_finish_templates_sprites.py" \
  "$ROOT/mediawiki/maintenance/ministationSetSanitizedCss.php"

# Ensure SS14_RESOURCES before finish (finish also tries)
RES="$ROOT/data/ss14_repo/Resources"
if [ -d "$RES/Textures" ]; then
  if grep -q '^SS14_RESOURCES=' "$ROOT/.env" 2>/dev/null; then
    sed -i "s|^SS14_RESOURCES=.*|SS14_RESOURCES=$RES|" "$ROOT/.env"
  else
    echo "SS14_RESOURCES=$RES" >> "$ROOT/.env"
  fi
  echo "SS14_RESOURCES set to $RES"
fi

sudo -u ss14_user -H bash <<'EOS'
set -euo pipefail
cd /home/ss14_user/ministation_wiki
source .venv/bin/activate
set -a; . ./.env; set +a
python3 -m tools._finish_templates_sprites
EOS

systemctl restart ministation-wiki-sprites
sleep 2
curl -s http://127.0.0.1:3001/health
echo
curl -s -o /tmp/crowbar.png -w "crowbar:%{http_code} size:%{size_download}\n" \
  "http://127.0.0.1:3001/sprite/Objects/Tools/crowbar.rsi/icon"
file /tmp/crowbar.png 2>/dev/null || true
