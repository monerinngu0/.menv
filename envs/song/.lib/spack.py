#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import sys
import zipfile
from pathlib import Path


MENV_ROOT = Path(os.environ.get("MENV_ROOT", Path.home() / ".menv"))
SONG_ROOT = MENV_ROOT / "envs" / "song"

sys.path.insert(0, str(MENV_ROOT / ".lib"))
sys.path.insert(0, str(SONG_ROOT / ".lib"))

from common import ok, ng, info  # noqa: E402
from song import category_dir, iter_audio_files, require_workspace  # noqa: E402
import slist  # noqa: E402


def pack_category(category: str, out: Path | None) -> None:
    root = require_workspace()
    cat = category_dir(root, category)
    song_dir = cat / "song"

    if not cat.exists():
        ng(f"category not found: {category}")
        sys.exit(1)

    slist.update_one(category)

    pack_dir = root / ".pack"
    pack_dir.mkdir(parents=True, exist_ok=True)

    zip_path = out or (pack_dir / f"{category}.zip")

    files = iter_audio_files(song_dir)
    metadata = cat / ".config" / "song.json"

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, path.relative_to(cat))

        if metadata.exists():
            zf.write(metadata, metadata.relative_to(cat))

    ok(f"packed: {zip_path}")
    info(f"files: {len(files)}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="spack")

    parser.add_argument("category")
    parser.add_argument("-o", "--out", type=Path)

    args = parser.parse_args()

    pack_category(args.category, args.out)


if __name__ == "__main__":
    main()