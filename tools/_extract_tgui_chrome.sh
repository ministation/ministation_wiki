#!/bin/bash
set -euo pipefail
python3 <<'PY'
import re
from pathlib import Path

css = Path('/tmp/remote_tgui_full.css').read_text(encoding='utf-8')
print('total', len(css))

# Extract rules containing these selectors (minified CSS - split by })
needles = [
    'page-actions',
    'cdx-button',
    'tgui-menu',
    'mw-portlet-views',
    'ca-view',
    'ca-viewsource',
    'ca-history',
    'ca-talk',
    'ca-edit',
    'sticky-header',
    'page-heading',
    'tgui-page',
]
chunks = []
# crude: find each needle and take surrounding { } block by scanning back to previous } and forward
for needle in needles:
    start = 0
    while True:
        i = css.find(needle, start)
        if i < 0:
            break
        # go back to previous }
        left = css.rfind('}', 0, i)
        # also consider start
        left = left + 1 if left >= 0 else 0
        # find matching closing - from first { after left
        brace = css.find('{', left)
        if brace < 0 or brace > i + 50:
            start = i + len(needle)
            continue
        depth = 0
        j = brace
        while j < len(css):
            if css[j] == '{':
                depth += 1
            elif css[j] == '}':
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        block = css[left:j].strip()
        if block and block not in chunks and len(block) < 4000:
            chunks.append(block)
        start = i + len(needle)

print('extracted blocks', len(chunks))
out = '/* extracted TGUI chrome */\n' + '\n\n'.join(chunks[:80])
Path('/tmp/tgui_chrome_extract.css').write_text(out, encoding='utf-8')
print('out bytes', len(out))
print(out[:3000])
print('---TAIL---')
print(out[-2000:])

# also dump page-actions related denser
for n in ['page-actions', 'cdx-button--icon-only', 'tgui-menu__content-list', '.cdx-button{']:
    i = css.find(n)
    print('LOC', n, i)
    if i >= 0:
        print(css[max(0,i-80):i+600])
        print('====')
PY

# local toolbar styles
python3 <<'PY'
from pathlib import Path
css = Path('/home/ss14_user/ministation_wiki/skins/MiniStation/resources/skin.css').read_text(encoding='utf-8')
i = css.find('.page-toolbar')
print(css[i:i+900])
PY
