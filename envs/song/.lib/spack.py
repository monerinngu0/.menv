#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import zipfile
from pathlib import Path


MENV_ROOT = Path(os.environ.get("MENV_ROOT", Path.home() / ".menv"))
SONG_ROOT = MENV_ROOT / "envs" / "song"

sys.path.insert(0, str(MENV_ROOT / ".lib"))
sys.path.insert(0, str(SONG_ROOT / ".lib"))

from common import ok, ng, info, run_quiet_func  # noqa: E402
from song import find_workspace, read_json, write_json, song_id_from_rel  # noqa: E402


def fail(message: str) -> None:
    ng(message)
    raise SystemExit(1)


def load_json_required(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        fail(f"failed to read json: {path}: {e}")

    if not isinstance(data, dict):
        fail(f"json root must be object: {path}")

    return data


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)

    return h.hexdigest()


def validate_category(name: object) -> str:
    if not isinstance(name, str):
        fail(f"invalid category: {name}")

    if not name or name.startswith(".") or "/" in name or "\\" in name:
        fail(f"invalid category: {name}")

    return name


def normalize_song_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        fail(f"invalid song path: {value}")

    rel = Path(value.replace("\\", "/"))

    if rel.is_absolute() or ".." in rel.parts:
        fail(f"unsafe song path: {value}")

    if not rel.parts:
        fail(f"invalid song path: {value}")

    if rel.parts[0] == "song":
        return rel.as_posix()

    return (Path("song") / rel).as_posix()


def safe_song_rel(value: object) -> Path:
    rel = Path(normalize_song_path(value))

    if not rel.parts or rel.parts[0] != "song":
        fail(f"unsafe song path: {value}")

    return rel


def song_id(song: dict) -> str:
    value = song.get("id")

    if isinstance(value, str) and value:
        return value

    file_value = song.get("file")
    if isinstance(file_value, str) and file_value:
        rel = Path(normalize_song_path(file_value))
        return song_id_from_rel(rel)

    fail(f"song entry without id: {song!r}")


def song_file(song: dict) -> str:
    return normalize_song_path(song.get("file"))


def load_server_songs(root: Path, category: str) -> dict[str, dict]:
    path = root / category / ".config" / "song.json"

    if not path.is_file():
        fail(f"server song.json not found: {path}")

    data = load_json_required(path)

    if data.get("version") != 1:
        fail(f"unsupported song.json version: {path}")

    if data.get("category") != category:
        fail(f"category mismatch in song.json: {path}")

    return {
        song_id(song): song
        for song in data.get("songs", [])
        if isinstance(song, dict)
    }


def diff_from_snapshot(root: Path, snapshot_path: Path) -> dict:
    snapshot = load_json_required(snapshot_path)

    if snapshot.get("version") != 1:
        fail("unsupported snapshot song.json version")

    category = validate_category(snapshot.get("category"))

    server_songs = load_server_songs(root, category)
    snapshot_songs = {
        song_id(song): song
        for song in snapshot.get("songs", [])
        if isinstance(song, dict)
    }

    download = []
    delete = []

    for sid in sorted(server_songs):
        if sid not in snapshot_songs:
            song = server_songs[sid]
            download.append(
                {
                    "id": sid,
                    "path": song_file(song),
                }
            )

    for sid in sorted(snapshot_songs):
        if sid not in server_songs:
            song = snapshot_songs[sid]
            delete.append(
                {
                    "id": sid,
                    "path": song_file(song),
                }
            )

    return {
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


def normalize_diff(root: Path, input_path: Path, temp_dir: Path) -> dict:
    data = load_json_required(input_path)

    if "categories" in data:
        if data.get("version") != 1:
            fail("unsupported diff.json version")

        return data

    diff = diff_from_snapshot(root, input_path)
    write_json(temp_dir / "diff.json", diff)

    return diff


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)

    path.mkdir(parents=True, exist_ok=True)


def copy_download_files(root: Path, package_dir: Path, diff: dict) -> list[dict]:
    files: list[dict] = []

    for category in diff.get("categories", []):
        name = validate_category(category.get("name"))
        server_songs = load_server_songs(root, name)

        downloads = category.get("download", [])
        deletes = category.get("delete", [])

        info(f"category: {name}")
        info(f"add: {len(downloads)}")
        info(f"delete: {len(deletes)}")
        print()

        for item in downloads:
            sid = item.get("id")

            if not isinstance(sid, str) or not sid:
                fail(f"download entry without id: {item!r}")

            if sid not in server_songs:
                fail(f"download id not found in server song.json: {sid}")

            rel = safe_song_rel(item.get("path"))
            expected = Path(song_file(server_songs[sid]))

            if rel != expected:
                fail(f"path mismatch for id {sid}: {rel} != {expected}")

            src = root / name / rel
            dst = package_dir / name / rel

            if not src.is_file():
                fail(f"download file not found: {src}")

            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

            arcname = (Path(name) / rel).as_posix()
            files.append(
                {
                    "path": arcname,
                    "size": dst.stat().st_size,
                    "sha256": sha256_file(dst),
                }
            )

        for item in deletes:
            safe_song_rel(item.get("path"))

        latest_json = root / name / ".config" / "song.json"
        if latest_json.is_file():
            dst = package_dir / name / ".config" / "song.json"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(latest_json, dst)

            arcname = (Path(name) / ".config" / "song.json").as_posix()
            files.append(
                {
                    "path": arcname,
                    "size": dst.stat().st_size,
                    "sha256": sha256_file(dst),
                }
            )

    return files


def create_manifest(package_dir: Path, diff_path: Path, files: list[dict]) -> None:
    manifest = {
        "version": 1,
        "generated": int(time.time()),
        "diff": {
            "path": "diff.json",
            "size": diff_path.stat().st_size,
            "sha256": sha256_file(diff_path),
        },
        "files": files,
    }

    write_json(package_dir / "manifest.json", manifest)


def create_zip(package_dir: Path, output: Path) -> None:
    if output.exists():
        output.unlink()

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(package_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(package_dir).as_posix())


def category_dirs(root: Path) -> list[Path]:
    out = []

    for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if child.is_dir() and not child.name.startswith(".") and (child / "song").is_dir():
            out.append(child)

    return out


def resolve_output(root: Path, raw: str | None, default_name: str) -> Path:
    if raw:
        return Path(raw).expanduser().resolve()

    return root / ".temp" / default_name


def create_music_zip(root: Path, categories: list[Path], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)

    if output.exists():
        output.unlink()

    total = 0
    entries: list[tuple[Path, str]] = []

    for category in categories:
        song_dir = category / "song"
        music_files = sorted(path for path in song_dir.rglob("*") if path.is_file())

        info(f"category: {category.name}")
        info(f"add: {len(music_files)}")
        print()

        for path in music_files:
            entries.append((path, path.relative_to(root).as_posix()))
            total += 1

    def write_zip() -> None:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path, arcname in entries:
                zf.write(path, arcname)

    run_quiet_func("compressing", write_zip)

    ok("create zip")
    info(f"add: {total}")

    try:
        display = output.relative_to(root)
    except ValueError:
        display = output

    info(f"output: {display}")

    return output


def validate_selected_file(song_dir: Path, value: str) -> Path:
    if not value or "\\" in value or ":" in value:
        fail(f"invalid file path: {value}")

    rel = Path(value)

    if rel.is_absolute() or ".." in rel.parts:
        fail(f"unsafe file path: {value}")

    if rel.parts and rel.parts[0] == "song":
        rel = Path(*rel.parts[1:])

    if not rel.parts:
        fail(f"invalid file path: {value}")

    target = (song_dir / rel).resolve()
    song_root = song_dir.resolve()

    try:
        target.relative_to(song_root)
    except ValueError:
        fail(f"file is outside category: {value}")

    if not target.is_file():
        fail(f"file not found: {value}")

    return target


def category_song_files(root: Path, category_name: str) -> tuple[Path, list[str]]:
    category = root / validate_category(category_name)
    song_dir = category / "song"

    if not song_dir.is_dir():
        fail(f"category not found or broken: {category_name}")

    files = sorted(
        path.relative_to(song_dir).as_posix()
        for path in song_dir.rglob("*")
        if path.is_file()
    )

    return song_dir, files


def print_select_list(files: list[str]) -> None:
    for index, file_name in enumerate(files, 1):
        print(f"[{index}] {file_name}")


def print_selected(selected: set[int]) -> None:
    if not selected:
        info("selected: none")
        return

    info("selected: " + ", ".join(str(i) for i in sorted(selected)))


class SelectionError(Exception):
    pass


def apply_selection_token(token: str, files: list[str], selected: set[int]) -> None:
    mode = "add"

    if token.startswith("+"):
        token = token[1:]
    elif token.startswith("-"):
        mode = "remove"
        token = token[1:]

    if not token:
        raise SelectionError("invalid selection")

    if "-" in token:
        left, right = token.split("-", 1)

        if not left.isdigit() or not right.isdigit():
            raise SelectionError(f"invalid range: {token}")

        start = int(left)
        end = int(right)

        if start > end:
            start, end = end, start

        values = range(start, end + 1)
    else:
        if not token.isdigit():
            raise SelectionError(f"invalid selection: {token}")

        values = [int(token)]

    for value in values:
        if value < 1 or value > len(files):
            raise SelectionError(f"number out of range: {value}")

        if mode == "remove":
            selected.discard(value)
        else:
            selected.add(value)


def select_files_repl(category_name: str, files: list[str]) -> list[str]:
    info(f"category: {category_name}")
    print()
    print_select_list(files)
    print()

    selected: set[int] = set()

    while True:
        try:
            line = input("spack> ").strip()
        except EOFError:
            print()
            raise SystemExit(0)

        if not line:
            continue

        if line == "exit":
            print("cancelled.")
            raise SystemExit(0)

        if line == "done":
            break

        if line == "all":
            selected = set(range(1, len(files) + 1))
            print_selected(selected)
            continue

        if line == "clear":
            selected.clear()
            print_selected(selected)
            continue

        if line == "show":
            print_selected(selected)
            continue

        if line == "list":
            print_select_list(files)
            continue

        before = set(selected)

        try:
            for token in line.split():
                apply_selection_token(token, files, selected)
        except SelectionError as e:
            selected = before
            ng(str(e))
            continue

        print_selected(selected)

    if not selected:
        fail("no files selected")

    return [files[i - 1] for i in sorted(selected)]


def create_select_zip(root: Path, category_name: str, files: list[str], output: Path) -> Path:
    song_dir, _ = category_song_files(root, category_name)
    output.parent.mkdir(parents=True, exist_ok=True)

    if output.exists():
        output.unlink()

    entries = []

    for file_name in files:
        target = validate_selected_file(song_dir, file_name)
        entries.append((target, target.relative_to(song_dir).as_posix()))

    info(f"category: {category_name}")
    info(f"add: {len(entries)}")
    print()

    def write_zip() -> None:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as zf:
            for path, arcname in entries:
                zf.write(path, arcname)

    run_quiet_func("compressing", write_zip)

    ok("create zip")

    try:
        display = output.relative_to(root)
    except ValueError:
        display = output

    info(f"output: {display}")

    return output


def create_diff_zip(root: Path, input_path: Path, output: Path, keep_temp: bool) -> None:
    temp_dir = root / ".temp"
    package_dir = temp_dir / "package"

    temp_dir.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)

    diff = normalize_diff(root, input_path, temp_dir)

    reset_dir(package_dir)

    diff_path = package_dir / "diff.json"
    write_json(diff_path, diff)

    files = copy_download_files(root, package_dir, diff)
    create_manifest(package_dir, diff_path, files)

    run_quiet_func("compressing", lambda: create_zip(package_dir, output))

    ok("create zip")

    if not keep_temp:
        shutil.rmtree(package_dir)

    try:
        display = output.relative_to(root)
    except ValueError:
        display = output

    info(f"output: {display}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="spack",
        usage="spack song.json [options]",
        description="Create .temp/diff.zip from diff.json or snapshot song.json.",
    )

    parser.add_argument("json_path", nargs="?")
    parser.add_argument("-o", "--output", metavar="FILE", help="output zip file")
    parser.add_argument("--all-music-no-json", action="store_true", help="create all.zip with only category/song files")
    parser.add_argument("-a", "--all", action="store_true", help="pack all workspace songs")
    parser.add_argument("-c", "--category", help="category name")
    parser.add_argument("--select", action="store_true", help="select category songs interactively")
    parser.add_argument("--keep-temp", action="store_true", help="keep package directory")

    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    root = find_workspace(Path.cwd())

    if root is None:
        fail("song workspace not found")

    if args.all_music_no_json:
        if args.json_path:
            fail("--all-music-no-json does not take JSON")

        if args.all and args.category:
            fail("-a and -c cannot be used together")

        if not args.all and not args.category:
            fail("--all-music-no-json requires -a or -c CATEGORY")

        if args.all:
            categories = category_dirs(root)
        else:
            name = validate_category(args.category)
            category = root / name

            if not (category / "song").is_dir():
                fail(f"category not found or broken: {name}")

            categories = [category]

        output = resolve_output(root, args.output, "all.zip")
        create_music_zip(root, categories, output)
        return 0

    if args.select:
        if args.json_path or args.all:
            fail("--select requires -c CATEGORY")

        if not args.category:
            fail("--select requires -c CATEGORY")

        _, files = category_song_files(root, args.category)

        if not files:
            fail("song is empty")

        selected = select_files_repl(args.category, files)
        output = resolve_output(root, args.output, f"{args.category}_select.zip")
        create_select_zip(root, args.category, selected, output)
        return 0

    if args.all or args.category:
        fail("-a/-c requires --all-music-no-json or --select")

    if not args.json_path:
        fail("json path is required")

    input_path = Path(args.json_path).expanduser().resolve()

    if not input_path.is_file():
        fail(f"json not found: {input_path}")

    output = resolve_output(root, args.output, "diff.zip")
    create_diff_zip(root, input_path, output, args.keep_temp)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
