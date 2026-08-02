from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from tools.config import CUSTOM_SETTINGS, MW_DIR, MW_VERSION

UA = "ministation_wiki-extensions/1.0 (+https://wiki.ministation.ru)"
BUNDLED_MARKER_BEGIN = "# BEGIN ministation_bundled"
BUNDLED_MARKER_END = "# END ministation_bundled"


@dataclass(frozen=True)
class Submodule:
    path: str  # extensions/Cite
    branch: str
    gerrit_url: str

    @property
    def kind(self) -> str:
        return self.path.split("/", 1)[0]

    @property
    def name(self) -> str:
        return self.path.split("/", 1)[1]

    @property
    def github_url(self) -> str:
        if self.kind == "extensions":
            return f"https://github.com/wikimedia/mediawiki-extensions-{self.name}.git"
        if self.kind == "skins":
            return f"https://github.com/wikimedia/mediawiki-skins-{self.name}.git"
        return self.gerrit_url


def _rel_branch(version: str) -> str:
    parts = version.split(".")
    return f"REL{parts[0]}_{parts[1]}"


def _fetch_gitmodules(branch: str) -> str:
    url = f"https://raw.githubusercontent.com/wikimedia/mediawiki/{branch}/.gitmodules"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8")


def parse_gitmodules(text: str) -> list[Submodule]:
    blocks = re.split(r"\n(?=\[submodule )", text.strip())
    out: list[Submodule] = []
    for block in blocks:
        path_m = re.search(r"^\s*path\s*=\s*(\S+)", block, re.M)
        url_m = re.search(r"^\s*url\s*=\s*(\S+)", block, re.M)
        branch_m = re.search(r"^\s*branch\s*=\s*(\S+)", block, re.M)
        if not path_m or not url_m:
            continue
        path = path_m.group(1)
        if path == "vendor" or not (
            path.startswith("extensions/") or path.startswith("skins/")
        ):
            continue
        out.append(
            Submodule(
                path=path,
                branch=(branch_m.group(1) if branch_m else _rel_branch(MW_VERSION)),
                gerrit_url=url_m.group(1),
            )
        )
    return out


def _git_clone(url: str, dest: Path, branch: str) -> None:
    if dest.exists() and (dest / ".git").exists():
        print(f"  update {dest.name}…")
        subprocess.run(["git", "-C", str(dest), "fetch", "--depth", "1", "origin", branch], check=False)
        subprocess.run(["git", "-C", str(dest), "checkout", "-f", "FETCH_HEAD"], check=False)
        return
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  clone {dest.name} ({branch})…")
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", branch, url, str(dest)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        # fallback without branch tip name (some repos use different default)
        subprocess.run(
            ["git", "clone", "--depth", "1", url, str(dest)],
            check=True,
        )
        subprocess.run(["git", "-C", str(dest), "checkout", branch], check=False)


def clone_bundled(modules: list[Submodule]) -> tuple[list[str], list[str]]:
    if not shutil.which("git"):
        raise SystemExit("git is required: apt install git")
    if not (MW_DIR / "includes" / "MediaWiki.php").is_file():
        raise SystemExit(f"MediaWiki not found at {MW_DIR}. Run: python -m tools setup")

    ext_names: list[str] = []
    skin_names: list[str] = []
    failed: list[str] = []

    for mod in modules:
        dest = MW_DIR / mod.path
        try:
            _git_clone(mod.github_url, dest, mod.branch)
            if mod.kind == "extensions":
                if not (dest / "extension.json").is_file():
                    raise RuntimeError("extension.json missing")
                ext_names.append(mod.name)
            else:
                if not (dest / "skin.json").is_file():
                    raise RuntimeError("skin.json missing")
                skin_names.append(mod.name)
        except (subprocess.CalledProcessError, RuntimeError, OSError) as e:
            print(f"  FAILED {mod.path}: {e}")
            failed.append(mod.path)

    if failed:
        print(f"Warning: {len(failed)} module(s) failed: {', '.join(failed)}")
    return sorted(ext_names), sorted(skin_names)


def _composer_update() -> None:
    composer = shutil.which("composer")
    if not composer:
        print("composer not found — skip dependency update (apt install composer recommended)")
        return
    print("+ composer update --no-dev")
    subprocess.run(
        [composer, "update", "--no-dev", "--prefer-dist", "--no-interaction"],
        cwd=MW_DIR,
        check=False,
    )


def write_bundled_loader(ext_names: list[str], skin_names: list[str]) -> Path:
    CUSTOM_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    bundled = CUSTOM_SETTINGS.parent / "LocalSettings.bundled.php"
    lines = [
        "<?php",
        "# Auto-generated by `python -m tools extensions` — official bundled set.",
        "# Do not edit by hand; re-run the command to refresh.",
        "",
    ]
    for name in skin_names:
        lines.append(f"wfLoadSkin( '{name}' );")
    if skin_names:
        lines.append("")
    for name in ext_names:
        # ConfirmEdit ships as ConfirmEdit; SyntaxHighlight uses folder name
        lines.append(f"wfLoadExtension( '{name}' );")
    lines.append("")
    bundled.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {bundled} ({len(ext_names)} extensions, {len(skin_names)} skins)")
    return bundled


def patch_custom_settings() -> None:
    """Ensure LocalSettings.custom.php requires the bundled loader."""
    CUSTOM_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    if not CUSTOM_SETTINGS.is_file():
        # setup not finished yet — write a stub that setup will overwrite/extend
        CUSTOM_SETTINGS.write_text(
            "<?php\n"
            f"{BUNDLED_MARKER_BEGIN}\n"
            "require_once __DIR__ . '/LocalSettings.bundled.php';\n"
            f"{BUNDLED_MARKER_END}\n",
            encoding="utf-8",
        )
        print(f"Created stub {CUSTOM_SETTINGS}")
        return

    text = CUSTOM_SETTINGS.read_text(encoding="utf-8")
    block = (
        f"{BUNDLED_MARKER_BEGIN}\n"
        "require_once __DIR__ . '/LocalSettings.bundled.php';\n"
        f"{BUNDLED_MARKER_END}\n"
    )
    if BUNDLED_MARKER_BEGIN in text and BUNDLED_MARKER_END in text:
        start = text.index(BUNDLED_MARKER_BEGIN)
        end = text.index(BUNDLED_MARKER_END) + len(BUNDLED_MARKER_END)
        text = text[:start] + block.rstrip() + text[end:]
    else:
        if not text.endswith("\n"):
            text += "\n"
        text += "\n" + block
    CUSTOM_SETTINGS.write_text(text, encoding="utf-8")
    print(f"Patched {CUSTOM_SETTINGS}")


def run_update_php() -> None:
    ls = MW_DIR / "LocalSettings.php"
    if not ls.is_file():
        print("LocalSettings.php missing — skip maintenance/update.php")
        return
    php = os.getenv("PHP_BIN", "php")
    print("+ php maintenance/run.php update --quick")
    subprocess.run(
        [php, "maintenance/run.php", "update", "--quick"],
        cwd=MW_DIR,
        check=False,
    )


def install_bundled() -> None:
    branch = _rel_branch(MW_VERSION)
    print(f"Fetching bundled module list from mediawiki {branch}…")
    try:
        gitmodules = _fetch_gitmodules(branch)
    except Exception:
        # tag branch sometimes lacks .gitmodules tip; try release tag
        print(f"  {branch} failed, trying tag {MW_VERSION}…")
        gitmodules = _fetch_gitmodules(MW_VERSION)

    modules = parse_gitmodules(gitmodules)
    print(f"Found {len(modules)} bundled extensions/skins")
    ext_names, skin_names = clone_bundled(modules)
    _composer_update()
    write_bundled_loader(ext_names, skin_names)
    patch_custom_settings()
    # Ensure LocalSettings.php still requires custom (setup may have done this)
    from tools.setup import write_custom_settings_snippet

    write_custom_settings_snippet()
    run_update_php()
    print(
        f"\nDone: enabled {len(ext_names)} extensions and {len(skin_names)} skins.\n"
        "Note: this is the official MediaWiki release bundle, not every extension on mediawiki.org."
    )


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if argv and argv[0] in ("-h", "--help"):
        print(
            "Usage: python -m tools extensions\n"
            "Clone and enable all official bundled MediaWiki extensions/skins\n"
            f"for version {MW_VERSION} (from .gitmodules)."
        )
        return 0
    try:
        install_bundled()
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {e}", file=sys.stderr)
        return e.returncode or 1
    except SystemExit as e:
        if e.args:
            print(e.args[0], file=sys.stderr)
        return int(e.code) if isinstance(e.code, int) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
