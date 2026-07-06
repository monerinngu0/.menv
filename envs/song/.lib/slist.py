#!/usr/bin/env python3

from __future__ import annotations

import os
import sys
from pathlib import Path


MENV_ROOT = Path(os.environ.get("MENV_ROOT", Path.home() / ".menv"))
SONG_ROOT = MENV_ROOT / "envs" / "song"

sys.path.insert(0, str(MENV_ROOT / ".lib"))
sys.path.insert(0, str(SONG_ROOT / ".lib"))

from common import ok, ng, info  # noqa: E402
from song import (  # noqa: E402
    category_dir,
    file_info,
    iter_audio_files,
    iter_categories,
    require_workspace,
    validate_category_name,
    write_json,
)


def update_one(category: str) -> int:
    validate_category_name(category)

    root = require_workspace()
    cat = category_dir(root, category)
    song_dir = cat / "song"
    song_json = cat / ".config" / "song.json"

    if not cat.exists():
        ng(f"category not found: {category}")
        sys.exit(1)

    if not song_dir.exists():
        ng(f"song directory not found: {song_dir}")
        sys.exit(1)

    files = iter_audio_files(song_dir)

    cat = category_dir(root, category)
    song_dir = cat / "song"

    songs = [
        file_info(path, cat)
        for path in iter_audio_files(song_dir)
    ]   

    data = {
        "version": 1,
        "category": category,
        "count": len(songs),
        "songs": songs,
    }

    write_json(song_json, data)

    ok(f"updated: {category} ({len(files)} songs)")

    return len(files)


def update_all() -> None:
    root = require_workspace()
    cats = iter_categories(root)

    if not cats:
        info("no categories")
        return

    total = 0

    for cat in cats:
        total += update_one(cat.name)

    ok(f"updated all ({len(cats)} categories, {total} songs)")


def main() -> None:
    if len(sys.argv) == 1:
        update_all()
        return

    if len(sys.argv) == 2:
        update_one(sys.argv[1])
        return

    print("usage: slist [category]")
    sys.exit(1)


if __name__ == "__main__":
    main()