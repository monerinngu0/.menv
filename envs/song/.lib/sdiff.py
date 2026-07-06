#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path


MENV_ROOT = Path(os.environ.get("MENV_ROOT", Path.home() / ".menv"))
SONG_ROOT = MENV_ROOT / "envs" / "song"

sys.path.insert(0, str(MENV_ROOT / ".lib"))
sys.path.insert(0, str(SONG_ROOT / ".lib"))

from common import ok, ng, info  # noqa: E402
from song import category_dir, read_json, require_workspace, validate_category_name, write_json  # noqa: E402


def fail(message: str) -> None:
    ng(message)
    raise SystemExit(1)


def song_id(song: dict) -> str:
    value = song.get("id")

    if not isinstance(value, str) or not value:
        fail(f"sdiff: song entry without id: {song!r}")

    return value


def song_file(song: dict) -> str:
    value = song.get("file")

    if not isinstance(value, str) or not value:
        fail(f"sdiff: song entry without file: {song!r}")

    path = Path(value)

    if path.is_absolute() or ".." in path.parts:
        fail(f"sdiff: unsafe song file path: {value}")

    # "song/xxx.mp3" 形式なら "xxx.mp3" に正規化する
    if path.parts and path.parts[0] == "song":
        rest = path.parts[1:]

        if not rest:
            fail(f"sdiff: invalid song file path: {value}")

        return Path(*rest).as_posix()

    # "xxx.mp3" 形式ならそのまま
    return path.as_posix()


def create_diff(root: Path, client_path: Path) -> tuple[Path, int, int]:
    if not client_path.is_file():
        fail(f"song.json not found: {client_path}")

    client = read_json(client_path, {})

    if client.get("version") != 1:
        fail("sdiff: unsupported client song.json version")

    category = client.get("category")

    if not isinstance(category, str) or not category:
        fail("sdiff: category not found in client song.json")

    validate_category_name(category)

    cat = category_dir(root, category)
    server_path = cat / ".config" / "song.json"

    if not server_path.is_file():
        fail(f"sdiff: server song.json not found: {server_path}")

    server = read_json(server_path, {})

    if server.get("version") != 1:
        fail("sdiff: unsupported server song.json version")

    server_category = server.get("category")

    if server_category != category:
        fail(f"sdiff: category mismatch: client={category}, server={server_category}")

    server_songs = {song_id(song): song for song in server.get("songs", [])}
    client_songs = {song_id(song): song for song in client.get("songs", [])}

    download = []
    delete = []

    for sid in sorted(server_songs):
        if sid not in client_songs:
            song = server_songs[sid]
            download.append(
                {
                    "id": sid,
                    "path": "song/" + song_file(song),
                }
            )

    for sid in sorted(client_songs):
        if sid not in server_songs:
            song = client_songs[sid]
            delete.append(
                {
                    "id": sid,
                    "path": "song/" + song_file(song),
                }
            )

    diff = {
        "version": 1,
        "generated": int(time.time()),
        "categories": [
            {
                "name": category,
                "download": download,
                "delete": delete,
            }
        ],
    }

    temp_dir = root / ".temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    diff_path = temp_dir / "diff.json"
    write_json(diff_path, diff)

    return diff_path, len(download), len(delete)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sdiff",
        usage="sdiff SONG_JSON_PATH",
        description="Create .temp/diff.json from a client song.json.",
    )

    parser.add_argument("song_json_path", type=Path)

    args = parser.parse_args()

    root = require_workspace()
    client_path = args.song_json_path.expanduser().resolve()

    diff_path, download_count, delete_count = create_diff(root, client_path)

    ok("diff created")
    info(f"download: {download_count}")
    info(f"delete: {delete_count}")
    info(f"path: {diff_path}")


if __name__ == "__main__":
    main()