#!/bin/bash
set -euo pipefail
echo "=== custom.php css hooks ==="
grep -n 'items-tables\|mainpage-widgets\|cssFiles\|addStyle\|addInlineStyle' \
  /home/ss14_user/ministation_wiki/config/LocalSettings.custom.php | head -50
ls -la /home/ss14_user/ministation_wiki/skins/MiniStation/resources/items-tables.css

python3 <<'PY'
import re
import urllib.request

url = "http://127.0.0.1:3000/index.php/%D0%A0%D1%83%D0%BA%D0%BE%D0%B2%D0%BE%D0%B4%D1%81%D1%82%D0%B2%D0%BE_%D0%BF%D0%BE_%D1%81%D1%82%D1%80%D0%BE%D0%B8%D1%82%D0%B5%D0%BB%D1%8C%D1%81%D1%82%D0%B2%D1%83"
html = urllib.request.urlopen(url, timeout=60).read().decode("utf-8", "replace")
print("items-tables.css?", "items-tables.css" in html)
print(".items-table rule?", ".items-table" in html)
print(".colors-engine rule?", ".colors-engine {" in html or ".colors-engine," in html)
print("style tags", html.count("<style"))
print("link stylesheets:")
for m in re.findall(r'href="([^"]+\.css[^"]*)"', html)[:20]:
    print(" ", m)
for m in re.findall(r"load\.php[^\"']+", html)[:10]:
    print(" load", m[:140])
# MediaWiki:Common.css usually via modules=site.styles
print("site.styles?", "site.styles" in html)
PY
