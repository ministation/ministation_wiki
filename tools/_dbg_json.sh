#!/bin/bash
python3 - <<'PY'
from pathlib import Path
raw = Path('/home/ss14_user/ministation_wiki/data/ss14_repo/Resources/Textures/Objects/Tools/crowbar.rsi/meta.json').read_bytes()
print('byte 90-100', raw[90:100], list(raw[90:100]))
# decode and show around 93
text = raw.decode('utf-8')
print('repr around', repr(text[80:110]))
for i,ch in enumerate(text):
    o = ord(ch)
    if o < 32 and ch not in '\n\r\t':
        print('c0', i, o)
    if o in (0x85, 0xA0) or (0x00 <= o < 0x20):
        print('special', i, o, repr(ch))
# Maybe the file has UTF-16 or the copyright has a literal backslash-x?
import re, json
# Try demjson-style: replace problematic chars in strings by escaping
fixed = text
# escape unescaped controls inside strings — simpler: use regex to remove non-printable from string values
def clean(s):
    s = re.sub(r'//.*?$', '', s, flags=re.M)
    out=[]
    in_str=False
    esc=False
    for ch in s:
        if in_str:
            if esc:
                out.append(ch); esc=False; continue
            if ch=='\\':
                out.append(ch); esc=True; continue
            if ch=='"':
                in_str=False; out.append(ch); continue
            if ord(ch) < 32:
                continue  # drop
            out.append(ch)
        else:
            if ch=='"':
                in_str=True
            if ord(ch) >= 32 or ch in '\n\r\t':
                out.append(ch)
    return ''.join(out)
c = clean(text)
print('cleaned parse', json.loads(c).get('size'))
PY
