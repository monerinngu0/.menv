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

from common import ok, ng, info, run_quiet  # noqa: E402
from song import category_dir, iter_audio_files, require_workspace  # noqa: E402
import slist  # noqa: E402


def pack_category_impl(root: Path, category: str, zip_path: Path) -> None:
    cat = category_dir(root, category)
    song_dir = cat / "song"

    if not cat.exists():
        print(f"category not found: {category}", file=sys.stderr)
        sys.exit(1)

    if not song_dir.is_dir():
        print(f"song directory not found: {song_dir}", file=sys.stderr)
        sys.exit(1)

    slist.update_one(category)

    files = iter_audio_files(song_dir)
    metadata = cat / ".config" / "song.json"

    zip_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, path.relative_to(cat))

        if metadata.exists():
            zf.write(metadata, metadata.relative_to(cat))


def pack_category(category: str, out: Path | None) -> None:
    root = require_workspace()
    cat = category_dir(root, category)
    song_dir = cat / "song"

    if not cat.exists():
        ng(f"category not found: {category}")
        sys.exit(1)

    if not song_dir.is_dir():
        ng(f"song directory not found: {song_dir}")
        sys.exit(1)

    pack_dir = root / ".pack"
    pack_dir.mkdir(parents=True, exist_ok=True)

    zip_path = out.expanduser().resolve() if out else pack_dir / f"{category}.zip"

    success = run_quiet(
        "packing",
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "__pack__",
            str(root),
            category,
            str(zip_path),
        ],
        cwd=root,
    )

    if not success:
        ng("pack failed")
        sys.exit(1)

    files = iter_audio_files(song_dir)

    ok(f"packed: {zip_path}")
    info(f"files: {len(files)}")


def handle_internal_command() -> bool:
    if len(sys.argv) >= 2 and sys.argv[1] == "__pack__":
        if len(sys.argv) != 5:
            print("usage: spack __pack__ ROOT CATEGORY ZIP_PATH", file=sys.stderr)
            sys.exit(1)

        root = Path(sys.argv[2])
        category = sys.argv[3]
        zip_path = Path(sys.argv[4])

        pack_category_impl(root, category, zip_path)
        return True

    return False


def main() -> None:
    if handle_internal_command():
        return

    parser = argparse.ArgumentParser(prog="spack")

    parser.add_argument("category")
    parser.add_argument("-o", "--out", type=Path)

    args = parser.parse_args()

    pack_category(args.category, args.out)


if __name__ == "__main__":
    main()