from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from tools.config import BASE_DIR, SS14_RESOURCES

# Mini-Station Goob textures (override with SS14_RESOURCES_GIT if needed)
DEFAULT_GIT = "https://github.com/ministation/mini-station-goob.git"
SS14_RESOURCES_GIT = os.getenv("SS14_RESOURCES_GIT", DEFAULT_GIT).strip()
SS14_RESOURCES_REF = os.getenv("SS14_RESOURCES_REF", "master").strip()
SS14_REPO_DIR = Path(
    os.getenv("SS14_REPO_DIR", str(BASE_DIR / "data" / "ss14_repo"))
).expanduser()


def _which(cmd: str) -> str | None:
    return shutil.which(cmd)


def resources_path() -> Path:
    """Resolved Resources dir (contains Textures/)."""
    if SS14_RESOURCES:
        p = Path(SS14_RESOURCES).expanduser()
        if (p / "Textures").is_dir():
            return p
        if (p / "Resources" / "Textures").is_dir():
            return p / "Resources"
        if p.name.lower() == "textures" and p.is_dir():
            return p.parent
    # default after git clone
    candidate = SS14_REPO_DIR / "Resources"
    return candidate


def ensure_sprites_from_git(*, update: bool = False) -> Path:
    """
    Sparse-clone Resources/Textures from SS14 git so {{#sprite:}} works.
    Uses partial clone to avoid downloading the whole C# codebase.
    """
    if not _which("git"):
        raise SystemExit("git required: apt install git")

    textures = resources_path() / "Textures"
    if textures.is_dir() and not update and any(textures.iterdir()):
        print(f"Textures already present: {textures}")
        return resources_path()

    SS14_REPO_DIR.parent.mkdir(parents=True, exist_ok=True)
    git_dir = SS14_REPO_DIR / ".git"

    if not git_dir.exists():
        if SS14_REPO_DIR.exists():
            shutil.rmtree(SS14_REPO_DIR)
        print(f"Sparse-cloning {SS14_RESOURCES_GIT} ({SS14_RESOURCES_REF})…")
        print("  (only Resources/Textures — this can still take a while)")
        subprocess.run(
            [
                "git",
                "clone",
                "--filter=blob:none",
                "--sparse",
                "--depth",
                "1",
                "--branch",
                SS14_RESOURCES_REF,
                SS14_RESOURCES_GIT,
                str(SS14_REPO_DIR),
            ],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(SS14_REPO_DIR),
                "sparse-checkout",
                "set",
                "Resources/Textures",
            ],
            check=True,
        )
    else:
        print(f"Updating textures in {SS14_REPO_DIR}…")
        subprocess.run(
            ["git", "-C", str(SS14_REPO_DIR), "fetch", "--depth", "1", "origin", SS14_RESOURCES_REF],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(SS14_REPO_DIR), "checkout", "-f", "FETCH_HEAD"],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(SS14_REPO_DIR),
                "sparse-checkout",
                "set",
                "Resources/Textures",
            ],
            check=False,
        )

    root = resources_path()
    tex = root / "Textures"
    if not tex.is_dir():
        raise SystemExit(
            f"Textures not found at {tex}. Check SS14_RESOURCES_GIT / branch."
        )
    count = sum(1 for _ in tex.rglob("*.rsi"))
    print(f"OK: {tex} ({count} .rsi folders)")
    print(f"Set in .env: SS14_RESOURCES={root}")
    env_hint = BASE_DIR / ".env"
    if env_hint.is_file():
        text = env_hint.read_text(encoding="utf-8")
        line = f"SS14_RESOURCES={root.as_posix()}"
        if "SS14_RESOURCES=" in text:
            lines = []
            for ln in text.splitlines():
                if ln.startswith("SS14_RESOURCES=") or ln.startswith("# SS14_RESOURCES="):
                    lines.append(line)
                else:
                    lines.append(ln)
            env_hint.write_text("\n".join(lines) + "\n", encoding="utf-8")
        else:
            env_hint.write_text(text.rstrip() + f"\n{line}\n", encoding="utf-8")
        print(f"Updated {env_hint}")
    return root


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("-h", "--help"):
        print(
            "Usage: python -m tools sprites [--update]\n\n"
            "Sparse-clone SS14 Resources/Textures from git for {{#sprite:}}.\n"
            f"Repo: {SS14_RESOURCES_GIT}\n"
            f"Ref:  {SS14_RESOURCES_REF}\n"
            "Override with SS14_RESOURCES_GIT / SS14_RESOURCES_REF / SS14_REPO_DIR."
        )
        return 0
    update = "--update" in argv or "-u" in argv
    try:
        ensure_sprites_from_git(update=update)
    except subprocess.CalledProcessError as e:
        print(f"git failed: {e}", file=sys.stderr)
        return e.returncode or 1
    except SystemExit as e:
        if e.args:
            print(e.args[0], file=sys.stderr)
        return int(e.code) if isinstance(e.code, int) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
