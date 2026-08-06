#!/bin/bash
set -euo pipefail
sudo -u ss14_user -H bash <<'EOS'
set -euo pipefail
cd /home/ss14_user/ministation_wiki
source .venv/bin/activate
set -a; . ./.env; set +a
python3 <<'PY'
from tools.migrate import edit_page
pairs = [
    ("Шаблон:RecursiveChem/FluoroSulphuric Acid", "Шаблон:RecursiveChem/FluoroSulfuric Acid"),
    ("Шаблон:RecursiveChem/Sulphuric Acid", "Шаблон:RecursiveChem/Sulfuric Acid"),
    ("Шаблон:RecursiveCult/Cult Door", "Шаблон:RecursiveCult/Cult Airlock"),
]
for src, dst in pairs:
    edit_page(src, f"#REDIRECT [[{dst}]]", summary="spelling alias redirect")
    print("redir", src, "→", dst)
PY
EOS
