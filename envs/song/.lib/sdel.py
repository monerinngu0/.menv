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
from song import category_dir, iter_audio_files, require_workspace  # noqa: E402
import slist  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: sdel <category>")
        sys.exit(1)

    category = sys.argv[1]

    root = require_workspace()
    cat = category_dir(root, category)
    song_dir = cat / "song"

    if not cat.exists():
        ng(f"category not found: {category}")
        sys.exit(1)

    files = iter_audio_files(song_dir)

    if not files:
        info("no songs")
        return

    for i, path in enumerate(files, 1):
        print(f"{i:3d}: {path.relative_to(song_dir)}")

    ans = input("Delete number? [empty to cancel] ").strip()

    if not ans:
        print("cancelled.")
        return

    if not ans.isdigit():
        ng("number required")
        sys.exit(1)

    idx = int(ans)

    if idx < 1 or idx > len(files):
        ng("number out of range")
        sys.exit(1)

    target = files[idx - 1]

    confirm = input(f"Delete '{target.name}'? [y/N] ").strip()

    if confirm not in {"y", "Y"}:
        print("cancelled.")
        return

    target.unlink()

    ok(f"deleted: {target.name}")

    slist.update_one(category)


if __name__ == "__main__":
    main()