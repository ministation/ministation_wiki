#!/bin/bash
set -euo pipefail
python3 <<'PY'
import re, urllib.request
html = urllib.request.urlopen(
    'http://127.0.0.1:3000/index.php/%D0%A0%D1%83%D0%BA%D0%BE%D0%B2%D0%BE%D0%B4%D1%81%D1%82%D0%B2%D0%BE_%D0%BF%D0%BE_%D1%81%D1%82%D1%80%D0%BE%D0%B8%D1%82%D0%B5%D0%BB%D1%8C%D1%81%D1%82%D0%B2%D1%83',
    timeout=60,
).read().decode('utf-8','replace')
# find Crowbar image context
i = html.find('Crowbar')
print(html[max(0,i-400):i+350].replace('\n',' ')[:700])
print('---')
# theme
print('data-theme', re.search(r'data-theme="([^"]+)"', html))
# relevant CSS rules present
for pat in ['mw-file-element','items-table td','color-second','engineer-transparent','img {']:
    print(pat, html.count(pat))
PY
