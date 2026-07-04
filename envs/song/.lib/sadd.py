#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


MENV_ROOT = Path(os.environ.get("MENV_ROOT", Path.home() / ".menv"))
SONG_ROOT = MENV_ROOT / "envs" / "song"

sys.path.insert(0, str(MENV_ROOT / ".lib"))
sys.path.insert(0, str(SONG_ROOT / ".lib"))

from common import ok, ng, info  # noqa: E402
from song import create_category, require_workspace, song_ytdlp  # noqa: E402
import slist  # noqa: E402


def run_download(url: str, out_dir: Path, *, playlist: bool) -> None:
    ytdlp = song_ytdlp()

    if ytdlp is None:
        ng("yt-dlp not found")
        info("run: scheck --install")
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        ytdlp,
        "--extract-audio",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "0",
        "--embed-thumbnail",
        "--add-metadata",
        "-o",
        str(out_dir / "%(title)s.%(ext)s"),
    ]

    if not playlist:
        cmd.append("--no-playlist")

    cmd.append(url)

    status = subprocess.run(cmd).returncode

    if status != 0:
        ng("download failed")
        sys.exit(status)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sadd",
        description="Add authorized audio to a song category.",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-c", "--category", help="category name")
    group.add_argument("-d", "--dir", help="output directory")

    parser.add_argument("--playlist", action="store_true", help="download playlist")
    parser.add_argument("url")

    args = parser.parse_args()

    if args.category:
        root = require_workspace()
        cat = create_category(root, args.category)
        out_dir = cat / "song"

        info(f"category: {args.category}")

        run_download(args.url, out_dir, playlist=args.playlist)

        slist.update_one(args.category)

        ok(f"added: {args.category}")
        return

    out_dir = Path(args.dir).expanduser().resolve()

    run_download(args.url, out_dir, playlist=args.playlist)

    ok(f"added: {out_dir}")


if __name__ == "__main__":
    main()