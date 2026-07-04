#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any


MENV_ROOT = Path(os.environ.get("MENV_ROOT", Path.home() / ".menv"))
SONG_ROOT = MENV_ROOT / "envs" / "song"
VENV = SONG_ROOT / ".venv"

WORKSPACE_MARKER = "song-workspace"

AUDIO_EXTS = {
    ".mp3",
    ".m4a",
    ".wav",
    ".flac",
    ".ogg",
    ".opus",
}


def song_python() -> Path:
    return VENV / "bin" / "python"


def song_ytdlp() -> str | None:
    local = VENV / "bin" / "yt-dlp"

    if local.exists() and os.access(local, os.X_OK):
        return str(local)

    return shutil.which("yt-dlp")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def find_workspace(start: Path | None = None) -> Path | None:
    cur = (start or Path.cwd()).resolve()

    while True:
        marker = cur / ".config" / "workspace"

        if marker.exists():
            text = marker.read_text(encoding="utf-8", errors="replace").strip()
            if text == WORKSPACE_MARKER:
                return cur

        if cur.parent == cur:
            return None

        cur = cur.parent


def require_workspace() -> Path:
    from common import ng, info

    root = find_workspace()

    if root is None:
        ng("song workspace not found")
        info("run: sinit")
        sys.exit(1)

    return root


def validate_category_name(name: str) -> None:
    from common import ng

    if not name:
        ng("category is empty")
        sys.exit(1)

    if name in {".", ".."}:
        ng("invalid category name")
        sys.exit(1)

    if name.startswith("."):
        ng("category cannot start with dot")
        sys.exit(1)

    if "/" in name or "\\" in name:
        ng("category cannot contain slash")
        sys.exit(1)


def category_dir(workspace: Path, category: str) -> Path:
    validate_category_name(category)
    return workspace / category


def create_category(workspace: Path, category: str) -> Path:
    validate_category_name(category)

    cat = category_dir(workspace, category)
    song_dir = cat / "song"
    config_dir = cat / ".config"
    song_json = config_dir / "song.json"

    song_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)

    if not song_json.exists():
        write_json(
            song_json,
            {
                "category": category,
                "count": 0,
                "songs": [],
            },
        )

    root_config = workspace / ".config" / "config.json"
    config = read_json(
        root_config,
        {
            "type": WORKSPACE_MARKER,
            "version": 1,
            "categories": [],
        },
    )

    categories = config.get("categories", [])

    if category not in categories:
        categories.append(category)
        categories.sort()
        config["categories"] = categories
        write_json(root_config, config)

    return cat


def is_category_dir(path: Path) -> bool:
    return (
        path.is_dir()
        and (path / "song").is_dir()
        and (path / ".config" / "song.json").exists()
    )


def iter_categories(workspace: Path) -> list[Path]:
    result: list[Path] = []

    for path in sorted(workspace.iterdir()):
        if path.name.startswith("."):
            continue

        if is_category_dir(path):
            result.append(path)

    return result


def iter_audio_files(song_dir: Path) -> list[Path]:
    if not song_dir.exists():
        return []

    result: list[Path] = []

    for path in sorted(song_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in AUDIO_EXTS:
            result.append(path)

    return result


def file_info(path: Path, base: Path) -> dict[str, Any]:
    st = path.stat()

    return {
        "file": str(path.relative_to(base)),
        "name": path.stem,
        "ext": path.suffix.lower().lstrip("."),
        "size": st.st_size,
        "mtime": int(st.st_mtime),
    }