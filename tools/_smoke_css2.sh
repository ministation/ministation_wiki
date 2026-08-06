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

sudo -u ss14_user -H bash <<'EOS'
set -euo pipefail
cd /home/ss14_user/ministation_wiki
source .venv/bin/activate
set -a; . ./.env; set +a
python3 <<'PY'
from pathlib import Path
from tools._finish_templates_sprites import sanitize_css_for_templatestyles, save_styles_css
raw = Path("content/import/remote/Шаблон_Pageframe__styles.css.wiki").read_text(encoding="utf-8")
body = raw[raw.find("-->")+3:].strip()
css = sanitize_css_for_templatestyles(body)
print("SANITIZED:")
print(css)
print("----")
print("ok", save_styles_css("Шаблон:Pageframe/styles.css", body))
PY
EOS
