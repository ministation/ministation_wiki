from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from PIL import Image

from app.config import SPRITE_CACHE_DIR, SPRITE_SCALE, SS14_RESOURCES

_SAFE = re.compile(r"^[\w./\-]+$", re.UNICODE)


def _textures_root() -> Path | None:
    if not SS14_RESOURCES or not str(SS14_RESOURCES):
        return None
    root = Path(SS14_RESOURCES)
    # accept Resources/ or Resources/Textures/
    if (root / "Textures").is_dir():
        return root / "Textures"
    if root.name.lower() == "textures" and root.is_dir():
        return root
    if (root / "Resources" / "Textures").is_dir():
        return root / "Resources" / "Textures"
    return None if not root.exists() else root


def resolve_rsi(target: str) -> tuple[Path, str]:
    """
    target examples:
      Objects/Weapons/Melee/knife.rsi/icon
      Objects/Weapons/Melee/knife.rsi
      Mobs/Species/Human/parts.rsi/head_m
    Returns (rsi_dir, state_name)
    """
    target = target.strip().lstrip("/")
    if ".." in target or not target:
        raise ValueError("invalid sprite path")
    if target.lower().endswith(".rsi"):
        rsi_rel, state = target, "icon"
    elif ".rsi/" in target.lower():
        rsi_rel, state = target.rsplit("/", 1)
    else:
        # assume .rsi missing
        if "/" in target:
            rsi_rel, state = target.rsplit("/", 1)
            if not rsi_rel.lower().endswith(".rsi"):
                rsi_rel = rsi_rel + ".rsi"
        else:
            raise ValueError("sprite path must include .rsi")

    textures = _textures_root()
    if textures is None:
        raise FileNotFoundError(
            "SS14_RESOURCES not set or Textures/ not found. "
            "Point env SS14_RESOURCES at your build Resources folder."
        )
    rsi_dir = textures / rsi_rel
    if not rsi_dir.is_dir():
        # try without duplicate Textures
        alt = textures / rsi_rel.replace("Textures/", "")
        if alt.is_dir():
            rsi_dir = alt
        else:
            raise FileNotFoundError(f"RSI not found: {rsi_dir}")
    return rsi_dir, state


def _load_meta(rsi_dir: Path) -> dict:
    meta_path = rsi_dir / "meta.json"
    raw = meta_path.read_text(encoding="utf-8-sig")
    # strip // comments sometimes present
    raw = re.sub(r"//.*?$", "", raw, flags=re.M)
    return json.loads(raw)


def extract_frame(
    target: str,
    *,
    frame: int = 0,
    direction: int = 0,
    scale: int | None = None,
) -> Path:
    """
    Cut one frame from RSI sheet and cache as PNG.
    Returns path to cached PNG.
    """
    scale = scale or SPRITE_SCALE
    rsi_dir, state_name = resolve_rsi(target)
    meta = _load_meta(rsi_dir)
    size = meta.get("size") or {}
    fw, fh = int(size.get("x", 32)), int(size.get("y", 32))

    states = meta.get("states") or []
    state = next((s for s in states if s.get("name") == state_name), None)
    if state is None:
        # fallback first state
        if not states:
            raise FileNotFoundError(f"no states in {rsi_dir}")
        state = states[0]
        state_name = state.get("name", state_name)

    dirs = int(state.get("directions", 1) or 1)
    # find sheet png — usually same name as folder
    sheet = rsi_dir / f"{rsi_dir.name.replace('.rsi', '')}.png"
    if not sheet.is_file():
        pngs = list(rsi_dir.glob("*.png"))
        if not pngs:
            raise FileNotFoundError(f"no PNG in {rsi_dir}")
        sheet = pngs[0]

    img = Image.open(sheet).convert("RGBA")
    cols = max(1, img.width // fw)

    # RSI layout: each state occupies consecutive frames; directions interleaved
    # Simplified: find state index offset by summing previous state frames
    offset = 0
    for s in states:
        if s.get("name") == state_name:
            break
        s_dirs = int(s.get("directions", 1) or 1)
        delays = s.get("delays")
        if delays:
            frames_per_dir = len(delays[0]) if delays else 1
        else:
            frames_per_dir = 1
        offset += s_dirs * frames_per_dir

    delays = state.get("delays")
    frames_per_dir = len(delays[0]) if delays else 1
    direction = max(0, min(direction, dirs - 1))
    frame = max(0, min(frame, frames_per_dir - 1))
    index = offset + direction * frames_per_dir + frame

    col = index % cols
    row = index // cols
    box = (col * fw, row * fh, col * fw + fw, row * fh + fh)
    crop = img.crop(box)

    if scale and scale != 1:
        crop = crop.resize((fw * scale, fh * scale), Image.Resampling.NEAREST)

    key = hashlib.sha1(
        f"{rsi_dir}:{state_name}:{frame}:{direction}:{scale}:{sheet.stat().st_mtime_ns}".encode()
    ).hexdigest()[:20]
    out = SPRITE_CACHE_DIR / f"{key}.png"
    if not out.is_file():
        SPRITE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        crop.save(out, format="PNG", optimize=True)
    return out


def list_rsi_states(rsi_rel: str) -> list[str]:
    rsi_dir, _ = resolve_rsi(rsi_rel if rsi_rel.lower().endswith(".rsi") else rsi_rel + "/icon")
    # if we passed .../icon, resolve_rsi gave state; re-resolve dir only
    if not rsi_rel.lower().endswith(".rsi"):
        if ".rsi/" in rsi_rel.lower():
            rsi_rel = rsi_rel.rsplit("/", 1)[0]
        elif not rsi_rel.lower().endswith(".rsi"):
            rsi_rel = rsi_rel + ".rsi"
    textures = _textures_root()
    assert textures
    rsi_dir = textures / rsi_rel
    meta = _load_meta(rsi_dir)
    return [s.get("name", "") for s in meta.get("states") or []]
