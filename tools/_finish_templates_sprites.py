#!/usr/bin/env python3
"""Import missing remote templates (incl. styles.css) + reupload MiniStation images."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from tools.config import BASE_DIR, MW_ADMIN, MW_DIR, PHP_BIN
from tools.import_remote import adapt_wikitext, api as remote_api, fetch_revisions, save_page
from tools.migrate import edit_page

UA = "ministation_wiki-fix/1.0"
LOCAL = "http://127.0.0.1:3000/api.php"
REMOTE = os.environ.get("REMOTE_WIKI_API", "").strip()
IMPORT = BASE_DIR / "content" / "import" / "remote"


def local_get(**kw):
    q = urllib.parse.urlencode(kw)
    req = urllib.request.Request(LOCAL + "?" + q, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def allpages(api: str, ns: int) -> set[str]:
    out: set[str] = set()
    cont: dict = {}
    while True:
        q = {
            "action": "query",
            "list": "allpages",
            "apnamespace": ns,
            "aplimit": 500,
            "format": "json",
            **cont,
        }
        req = urllib.request.Request(
            api + "?" + urllib.parse.urlencode(q),
            headers={"User-Agent": UA},
        )
        data = json.loads(urllib.request.urlopen(req, timeout=90).read().decode())
        for p in data.get("query", {}).get("allpages", []):
            out.add(p["title"])
        cont = data.get("continue") or {}
        if not cont:
            break
    return out


def sanitize_css_for_templatestyles(css: str) -> str:
    """Flatten constructs TemplateStyles CSSSanitizer rejects."""
    # known design tokens → literals (typed props reject many var() values)
    repl = {
        "var(--border-radius-medium)": "8px",
        "var(--border-radius-small)": "6px",
        "var(--border-radius-large)": "12px",
        "var(--transition-time)": "0.15s",
        "var(--transition-delay)": "0s",
        "var(--pagebutton-transition)": "0.3s",
        "var(--blur-default)": "8px",
        "var(--shadow-template--small)": "0 2px 0 rgba(0,0,0,.12)",
        "var(--shadow-template--medium)": "0 3px 0 rgba(0,0,0,.14)",
        "var(--template-shadow--small)": "0 2px 0",
        "var(--template-shadow--medium)": "0 3px 0",
        "var(--index-base)": "1",
        "var(--index-fore)": "2",
        "var(--linear-bounce)": "ease",
        "var(--border-classic)": "1px solid #c9d4e4",
        "var(--tmp-img-size)": "32px",
        "var(--fa-font-solid)": 'normal 900 1em/1 "Font Awesome 6 Free"',
        "var(--color-white)": "#fff",
        "var(--color-black)": "#000",
        "var(--color-text)": "#1a1a1a",
        "var(--color-text-darker)": "#111",
        "var(--color-text-translucent)": "rgba(0,0,0,.55)",
        "var(--color-border)": "#c9d4e4",
        "var(--color-primal-immutable)": "#7a90b8",
        "var(--deptab)": "#d8dee8",
        "var(--deptab-hover)": "#9aa8bd",
        "var(--blur-default)": "blur(8px)",
    }
    for a, b in repl.items():
        css = css.replace(a, b)

    # relative color syntax hsl(from …) / hsla(from …)
    def _replace_func_from(text: str, prefix: str) -> str:
        out = []
        i = 0
        lower = text.lower()
        needle = prefix.lower() + "(from"
        while i < len(text):
            j = lower.find(needle, i)
            if j < 0:
                out.append(text[i:])
                break
            out.append(text[i:j])
            depth = 0
            k = j
            while k < len(text):
                if text[k] == "(":
                    depth += 1
                elif text[k] == ")":
                    depth -= 1
                    if depth == 0:
                        k += 1
                        break
                k += 1
            out.append("#666666")
            i = k
        return "".join(out)

    css = _replace_func_from(css, "hsl")
    css = _replace_func_from(css, "hsla")

    css = re.sub(r"calc\(\s*0\.15s\s*\*\s*2\s*\)", "0.3s", css)
    css = re.sub(r"calc\(\s*var\([^)]+\)\s*\*\s*\d+\s*\)", "0.3s", css)
    css = re.sub(r"\bborder-radius\s*:\s*inherit\s*;", "border-radius: 8px;", css)
    css = re.sub(r"\bunset\b", "none", css)
    css = re.sub(r"\bmax-content\b", "auto", css)
    css = re.sub(r"(?m)^\s*--tmp-img-size\s*:[^;]+;\s*$", "", css)
    css = re.sub(r"(?m)^\s*aspect-ratio\s*:[^;]+;\s*$", "", css)
    css = re.sub(r"(?m)^\s*mask-image\s*:[^;]+;\s*$", "", css)
    css = re.sub(r"(?m)^\s*pointer-events\s*:[^;]+;\s*$", "", css)
    css = re.sub(r"(?m)^\s*backdrop-filter\s*:[^;]+;\s*$", "", css)
    css = re.sub(r"(?m)^\s*user-select\s*:[^;]+;\s*$", "", css)
    css = re.sub(r"(?m)^\s*hyphens\s*:[^;]+;\s*$", "", css)
    css = re.sub(r"(?m)^\s*gap\s*:[^;]+;\s*$", "", css)
    css = re.sub(r"\binset\s*:\s*0\s*;", "top:0;right:0;bottom:0;left:0;", css)

    # Drop @media blocks — TemplateStyles support is limited / flaky
    while True:
        m = re.search(r"@media[^{]*\{", css)
        if not m:
            break
        start = m.start()
        i = m.end() - 1
        depth = 0
        while i < len(css):
            if css[i] == "{":
                depth += 1
            elif css[i] == "}":
                depth -= 1
                if depth == 0:
                    i += 1
                    break
            i += 1
        css = css[:start] + css[i:]

    # custom-prop fallbacks: var(--hover-x, var(--tmp-x)) → var(--tmp-x)
    css = re.sub(
        r"var\(\s*--hover-[^,)]+\s*,\s*(var\([^)]+\))\s*\)",
        r"\1",
        css,
    )

    css = re.sub(
        r"box-shadow\s*:\s*0\s+2px\s+0\s+-1px\s+[^;]+;",
        "box-shadow: 0 2px 0 rgba(0,0,0,.12);",
        css,
    )
    css = re.sub(
        r"box-shadow\s*:\s*0\s+0\s+0\.5rem\s+-0\.1rem\s*,\s*inset\s+0\s+0\s+0\.25rem\s+0rem\s*;",
        "box-shadow: 0 0 0.5rem rgba(0,0,0,.2), inset 0 0 0.25rem rgba(0,0,0,.08);",
        css,
    )
    css = re.sub(
        r"box-shadow\s*:\s*0\s+0\s+0\.75rem\s+0\s*,\s*inset\s+0\s+0\s+0\.25rem\s+0\.1rem\s*;",
        "box-shadow: 0 0 0.75rem rgba(0,0,0,.25), inset 0 0 0.25rem rgba(0,0,0,.1);",
        css,
    )

    css = re.sub(r"(?m)^\s*filter\s*:[^;]+;\s*$", "", css)
    css = re.sub(r"\s*filter\s*:[^;]+;", "", css)
    css = css.replace("outline: 1px outset", "outline: 1px solid")

    # TemplateStyles rejects border-color: var(--…) in some versions — fold into border
    css = re.sub(
        r"border\s*:\s*1px\s+solid\s*;\s*border-color\s*:\s*([^;]+);",
        r"border: 1px solid \1;",
        css,
        flags=re.I,
    )
    css = re.sub(
        r"border-bottom\s*:\s*2px\s+solid\s*;\s*border-color\s*:\s*([^;]+);",
        r"border-bottom: 2px solid \1;",
        css,
        flags=re.I,
    )
    # remaining border-color: var(...) → solid hex
    css = re.sub(r"border-color\s*:\s*var\([^)]+\)\s*;", "border-color: #c9d4e4;", css)

    # Drop custom-property declarations (redefines in :hover trip sanitizer)
    css = re.sub(r"(?m)^\s*--[A-Za-z0-9_-]+\s*:[^;]+;\s*$", "", css)
    # and remaining var(--color-tmp-*) / var(--tmp-*) → safe colors
    css = re.sub(r"var\(--(?:color-)?tmp-100\)", "#5a6a80", css)
    css = re.sub(r"var\(--(?:color-)?tmp-75\)", "#7a90b8", css)
    css = re.sub(r"var\(--(?:color-)?tmp-50\)", "#a0b0c8", css)
    css = re.sub(r"var\(--(?:color-)?tmp-25\)", "#c9d4e4", css)
    css = re.sub(r"var\(--(?:color-)?tmp-10\)", "#e8eef7", css)

    css = re.sub(r"transition-property\s*:\s*filter\s*;", "transition-property: opacity;", css)

    # last resort: typed time props must be literal
    css = re.sub(
        r"(transition-(?:delay|duration))\s*:\s*var\([^)]+\)\s*;",
        r"\1: 0.15s;",
        css,
    )

    return css.strip() + "\n"


def save_styles_css(title: str, css: str) -> bool:
    css = sanitize_css_for_templatestyles(css)
    helper = MW_DIR / "maintenance" / "ministationSetSanitizedCss.php"
    if not helper.is_file():
        print("no helper", title)
        return False
    proc = subprocess.run(
        [PHP_BIN, "maintenance/run.php", "ministationSetSanitizedCss.php", title],
        cwd=MW_DIR,
        input=css,
        text=True,
        capture_output=True,
    )
    ok = proc.returncode == 0 or "no change was made" in (proc.stderr or "") + (proc.stdout or "")
    # verify via API
    q = local_get(action="query", titles=title, prop="revisions", rvprop="size|contentmodel", format="json")
    page = list(q["query"]["pages"].values())[0]
    exists = "missing" not in page
    size = 0
    if exists and page.get("revisions"):
        size = page["revisions"][0].get("size") or 0
    print(
        f"CSS {title}: rc={proc.returncode} exists={exists} size={size}",
        (proc.stderr or proc.stdout or "")[-200:].replace("\n", " "),
    )
    return exists and size > 0


def fetch_missing_from_remote(missing: list[str]) -> None:
    if not REMOTE:
        raise SystemExit("REMOTE_WIKI_API not set")
    print(f"fetching {len(missing)} titles from remote…")
    # batch
    for i in range(0, len(missing), 40):
        chunk = missing[i : i + 40]
        pages = fetch_revisions("remote", chunk)
        for p in pages:
            path = save_page(p)
            print("  saved", p.title, "→", path.name)
        time.sleep(0.2)


REDIRECT_ALIASES = {
    "Шаблон:Species": "Шаблон:Расы",
    "Шаблон:TOC": "Шаблон:Содержание",
    "Шаблон:Obsolete": "Шаблон:Устаревший",
    "Шаблон:Reference": "Шаблон:Справочная страница",
    "Шаблон:Якорь": "Шаблон:Anchor",
    "Шаблон:Удалить": "Шаблон:Подлежащие удалению",
    "Шаблон:Отключено": "Шаблон:Ограничено",
    "Шаблон:Отключёно": "Шаблон:Ограничено",
    "Шаблон:Slated for removal": "Шаблон:Подлежащие удалению",
    "Шаблон:СРП МЩ": "Шаблон:СРП:МЩ",
    "Шаблон:СРП:Вспышки вируса": "Шаблон:СРП:Вспышка вируса",
    "Шаблон:СРП:Имплантов": "Шаблон:СРП:Импланты",
    "Шаблон:СРП:Найма": "Шаблон:СРП:Найм",
    "Шаблон:СРП:Стажер": "Шаблон:СРП:Стажёр",
    "Шаблон:НарушенияЗаключённых": "Шаблон:НарушенияЗаключённыхТаблица",
    "Шаблон:SecureAreaList v2": "Шаблон:SecureAreaList",
    "Шаблон:Список ЧСv2": "Шаблон:Список ЧС",
    "Шаблон:DepartmentTabs/styles": "Шаблон:DepartmentTabs/styles.css",
}


def _read_import_body(path: Path) -> tuple[str | None, str]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    title = None
    body = raw
    if raw.startswith("<!-- ministation-import"):
        end = raw.find("-->")
        if end > 0:
            try:
                meta = json.loads(raw[len("<!-- ministation-import") : end].strip())
                title = meta.get("title")
            except json.JSONDecodeError:
                pass
            body = raw[end + 3 :].lstrip("\n")
    return title, body


def apply_path(path: Path, title: str | None = None) -> None:
    meta_title, body = _read_import_body(path)
    title = title or meta_title
    if not title:
        print("NO TITLE", path.name)
        return
    body = adapt_wikitext(body, "remote", title)
    if title.endswith("/styles.css") or title.endswith("/styles"):
        css_title = title if title.endswith(".css") else f"{title}.css"
        save_styles_css(css_title, body)
        return
    try:
        edit_page(title, body, summary="import missing template")
        print("OK", title)
    except SystemExit as e:
        print("FAIL", title, e)


def apply_missing(missing: list[str]) -> None:
    by_title: dict[str, Path] = {}
    for path in IMPORT.glob("*.wiki"):
        title, _ = _read_import_body(path)
        if title:
            by_title[title] = path

    # Always (re)apply every styles.css dump we have
    for path in sorted(IMPORT.glob("*styles.css.wiki")):
        apply_path(path)

    for title in missing:
        if title.endswith("/styles.css") or title.endswith("/styles"):
            continue  # handled above
        target = REDIRECT_ALIASES.get(title, title)
        path = by_title.get(target) or by_title.get(title)
        if path and path.is_file():
            apply_path(path, target)
            if title != target:
                try:
                    edit_page(
                        title,
                        f"#REDIRECT [[{target}]]",
                        summary="alias redirect for renamed template",
                    )
                    print("REDIR", title, "→", target)
                except SystemExit as e:
                    print("REDIR FAIL", title, e)
            continue
        print("NO FILE", title)


def restore_parent_styles(parent: str, styles_title: str) -> None:
    """Ensure parent template has templatestyles tag (optional — CSS also in skin)."""
    # Keep stripped for stability; skin has fallback CSS.
    # Only re-add if page exists and CSS verified.
    q = local_get(action="query", titles=styles_title, prop="revisions", rvprop="size", format="json")
    page = list(q["query"]["pages"].values())[0]
    if "missing" in page:
        return
    # leave parent without tag — skin CSS covers main widgets
    return


def upload_images() -> None:
    from tools.config import PHP_BIN

    for folder in ("mini_images", "dept_images", "remote_images"):
        img_dir = BASE_DIR / "data" / folder
        if not img_dir.is_dir():
            continue
        files = [p for p in img_dir.iterdir() if p.is_file()]
        if not files:
            continue
        print(f"uploading {len(files)} from {folder}…")
        script = MW_DIR / "maintenance" / "importImages.php"
        subprocess.run(
            [PHP_BIN, str(script), str(img_dir), "--overwrite", f"--user={MW_ADMIN}"],
            cwd=str(MW_DIR),
            check=False,
        )


def ensure_sprite_env() -> None:
    # Prefer local ss14_repo textures if present
    candidates = [
        BASE_DIR / "data" / "ss14_repo" / "Resources",
        Path("/home/ss14_user/mini-station-goob/Resources"),
        Path("/home/ss14_user/ministation/Resources"),
    ]
    env_path = BASE_DIR / ".env"
    text = env_path.read_text(encoding="utf-8") if env_path.is_file() else ""
    chosen = None
    for c in candidates:
        if (c / "Textures").is_dir() or c.is_dir():
            # Resources folder
            if c.name == "Resources" and c.is_dir():
                chosen = c
                break
            if (c / "Textures").is_dir():
                chosen = c
                break
    # also search ss14_repo
    repo = BASE_DIR / "data" / "ss14_repo"
    if chosen is None and repo.is_dir():
        for p in repo.rglob("Textures"):
            if p.is_dir():
                chosen = p.parent
                break
    if chosen is None:
        print("WARN: no SS14 Resources found for sprite service")
        return
    print("SS14_RESOURCES =", chosen)
    lines = []
    found = False
    for line in text.splitlines():
        if line.startswith("SS14_RESOURCES="):
            lines.append(f"SS14_RESOURCES={chosen}")
            found = True
        else:
            lines.append(line)
    if not found:
        lines.append(f"SS14_RESOURCES={chosen}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify() -> None:
    remote = allpages(REMOTE, 10)
    local = allpages(LOCAL, 10)
    missing = sorted(remote - local)
    print(f"still missing: {len(missing)}")
    for t in missing[:40]:
        print(" -", t)
    # files
    for title in [
        "Файл:Baby.png",
        "Файл:Dept Command.png",
        "Файл:Mini antag thief.png",
        "Шаблон:Pageframe/styles.css",
        "Шаблон:Правило/styles.css",
    ]:
        q = local_get(action="query", titles=title, format="json")
        p = list(q["query"]["pages"].values())[0]
        print(title, "MISSING" if "missing" in p else "ok")


def main() -> int:
    if not REMOTE:
        print("REMOTE_WIKI_API required", file=sys.stderr)
        return 1
    remote = allpages(REMOTE, 10)
    local = allpages(LOCAL, 10)
    missing = sorted(remote - local)
    print(f"missing before: {len(missing)}")
    if missing:
        fetch_missing_from_remote(missing)
        # refresh missing after fetch (styles may have been saved to disk)
        apply_missing(missing)
    ensure_sprite_env()
    upload_images()
    # restart sprites picked up by caller
    verify()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
