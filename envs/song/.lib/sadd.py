#!/usr/bin/env python3

from __future__ import annotations

import argparse
import contextlib
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse


MENV_ROOT = Path(os.environ.get("MENV_ROOT", Path.home() / ".menv"))
SONG_ROOT = MENV_ROOT / "envs" / "song"

sys.path.insert(0, str(MENV_ROOT / ".lib"))
sys.path.insert(0, str(SONG_ROOT / ".lib"))

from common import ok, ng, info, warn, skip, run_quiet_capture  # noqa: E402
from song import (  # noqa: E402
    category_dir,
    require_workspace,
    song_deno,
    song_ffmpeg_bin_dir,
    song_ytdlp,
    validate_category_name,
)
import slist  # noqa: E402


def is_youtube_host(host: str) -> bool:
    host = host.lower()

    return (
        host == "youtube.com"
        or host == "www.youtube.com"
        or host == "m.youtube.com"
        or host == "music.youtube.com"
        or host == "youtu.be"
    )


def has_youtube_video_id(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    query = parse_qs(parsed.query)

    if not is_youtube_host(host):
        return False

    # https://www.youtube.com/watch?v=VIDEO_ID
    if parsed.path == "/watch" and query.get("v"):
        return True

    # https://youtu.be/VIDEO_ID
    if host == "youtu.be" and parsed.path.strip("/"):
        return True

    # https://www.youtube.com/shorts/VIDEO_ID
    if parsed.path.startswith("/shorts/") and parsed.path.strip("/").split("/")[1:]:
        return True

    return False


def has_playlist_marker(url: str) -> bool:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    path = parsed.path

    return (
        "list" in query
        or "/playlist" in path
        or "/playlists/" in path
        or "/sets/" in path
    )


def is_playlist_only_url(url: str) -> bool:
    # watch?v=...&list=... は単体動画として扱えるので playlist-only ではない
    if has_youtube_video_id(url):
        return False

    return has_playlist_marker(url)


def is_valid_playlist_url(url: str) -> bool:
    return has_playlist_marker(url)


def grep_errors(log: str) -> list[str]:
    lines = []

    for line in log.splitlines():
        if line.startswith("ERROR:") or line.startswith("WARNING:"):
            lines.append(line)

    return lines[-5:]


def extract_title(log: str) -> str | None:
    for line in log.splitlines():
        prefix = "[ExtractAudio] Destination: "

        if line.startswith(prefix):
            path = line[len(prefix):].strip()
            path = path.strip('"')
            return Path(path).stem

    for line in log.splitlines():
        if ".mp3 has already been downloaded" not in line:
            continue

        line = re.sub(r"^\[download\]\s+", "", line)
        line = re.sub(r"\s+has already been downloaded$", "", line)
        line = line.strip('"')
        return Path(line).stem

    return None


def expected_mp3_path(url: str, out_dir: Path) -> Path | None:
    ytdlp = song_ytdlp()
    deno = song_deno()

    if ytdlp is None or deno is None:
        return None

    cmd = [
        ytdlp,
        "--no-playlist",
        "--skip-download",
        "--js-runtimes",
        f"deno:{deno}",
        "--remote-components",
        "ejs:github",
        "--print",
        "filename",
        "-o",
        str(out_dir / "%(title)s.mp3"),
        url,
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )

    if result.returncode != 0:
        return None

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]

    if not lines:
        return None

    return Path(lines[-1])


def build_download_command(url: str, out_dir: Path, *, force: bool) -> list[str]:
    ytdlp = song_ytdlp()
    ffmpeg_bin_dir = song_ffmpeg_bin_dir()
    deno = song_deno()

    if ytdlp is None:
        ng("yt-dlp not found")
        info("run: scheck --install")
        sys.exit(1)

    if ffmpeg_bin_dir is None:
        ng("song ffmpeg not found")
        info("run: scheck --install")
        sys.exit(1)

    if deno is None:
        ng("song deno not found")
        info("run: scheck --install")
        sys.exit(1)

    cmd = [
        ytdlp,
        "--no-playlist",
        "--ffmpeg-location",
        str(ffmpeg_bin_dir),
        "--js-runtimes",
        f"deno:{deno}",
        "--remote-components",
        "ejs:github",
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

    if force:
        cmd.append("--force-overwrites")

    cmd.append(url)

    return cmd


def download_one(url: str, index: int, total: int, out_dir: Path, *, force: bool) -> bool:
    print()
    info(f"[{index}/{total}]")

    if not force:
        existing = expected_mp3_path(url, out_dir)

        if existing is not None and existing.exists():
            skip(f"already exists: {existing.name}")
            info(f"title: {existing.stem}")
            return True

    cmd = build_download_command(url, out_dir, force=force)
    success, log = run_quiet_capture("download", cmd)

    if not success:
        ng("failed")

        for line in grep_errors(log):
            print(line)

        return False

    if "Converting thumbnail" in log:
        ok("png convert")
    else:
        skip("png convert")

    if re.search(r"^\[ExtractAudio\]", log, flags=re.MULTILINE):
        ok("mp3 convert")
    else:
        skip("mp3 convert")

    title = extract_title(log)
    if title:
        info(f"title: {title}")

    return True


def build_fetch_playlist_command(url: str) -> list[str]:
    ytdlp = song_ytdlp()
    deno = song_deno()

    if ytdlp is None:
        ng("yt-dlp not found")
        info("run: mcheck song --install")
        sys.exit(1)

    if deno is None:
        ng("song deno not found")
        info("run: mcheck song --install")
        sys.exit(1)

    return [
        ytdlp,
        "--js-runtimes",
        f"deno:{deno}",
        "--remote-components",
        "ejs:github",
        "--flat-playlist",
        "--print",
        "%(url)s",
        url,
    ]


def normalize_playlist_url(line: str) -> str | None:
    line = line.strip()

    if not line:
        return None

    if line.startswith("http://") or line.startswith("https://"):
        return line

    if re.fullmatch(r"[A-Za-z0-9_-]{11}", line):
        return f"https://www.youtube.com/watch?v={line}"

    return None


def fetch_playlist_urls(url: str) -> list[str] | None:
    cmd = build_fetch_playlist_command(url)
    success, log = run_quiet_capture("fetch playlist", cmd)

    if not success:
        ng("failed to fetch playlist")

        for line in grep_errors(log):
            print(line)

        return None

    urls = []

    for line in log.splitlines():
        normalized = normalize_playlist_url(line)

        if normalized is not None:
            urls.append(normalized)

    return urls


def require_existing_category(category: str) -> tuple[Path, Path]:
    validate_category_name(category)

    root = require_workspace()
    cat = category_dir(root, category)

    if (
        not cat.is_dir()
        or not (cat / "song").is_dir()
        or not (cat / ".config" / "song.json").is_file()
    ):
        ng(f"category not found or broken: {category}")
        print(f"Run: scat {category}")
        sys.exit(1)

    return root, cat


def update_song_list_if_needed(category: str | None) -> bool:
    if not category:
        return True

    try:
        with open(os.devnull, "w", encoding="utf-8") as devnull:
            with contextlib.redirect_stdout(devnull):
                slist.update_one(category)
    except SystemExit as e:
        if e.code not in (0, None):
            ng("song list update failed")
            return False
    except Exception:
        ng("song list update failed")
        return False

    ok("song list update")
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="sadd",
        usage="sadd (-d DIR | -c CATEGORY) [options] URL",
        formatter_class=argparse.RawTextHelpFormatter,
        description=None,
        epilog="""Examples:
  sadd -c touhou "URL"
  sadd -c touhou --playlist "PLAYLIST_URL"
  sadd -d ./tmp "URL"
""",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-d", "--dir", dest="out_dir", help="Save to DIR")
    group.add_argument("-c", "--category", help="Save to workspace CATEGORY/song")

    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="force download even if the mp3 file already exists",
    )

    parser.add_argument("--playlist", action="store_true", help="Allow playlist download")
    parser.add_argument("url")

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    category: str | None = args.category
    url: str = args.url

    if category:
        _, cat = require_existing_category(category)
        out_dir = cat / "song"
    else:
        out_dir = Path(args.out_dir).expanduser()

    if args.playlist:
        if not is_valid_playlist_url(url):
            ng("--playlist requires playlist url")
            sys.exit(1)
    else:
        if is_playlist_only_url(url):
            ng("playlist url requires --playlist")
            sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_dir = out_dir.resolve()

    info(f"save directory: {out_dir}")

    if not args.playlist:
        if download_one(url, 1, 1, out_dir, force=args.force):
            print()
            ok("finished")
            info(f"saved to: {out_dir}")

            if not update_song_list_if_needed(category):
                sys.exit(1)

            return

        print()
        ng("finished with failed")
        skip("song list update (download failed)")
        sys.exit(1)

    urls = fetch_playlist_urls(url)

    if urls is None:
        sys.exit(1)

    total = len(urls)

    if total == 0:
        ng("playlist is empty")
        sys.exit(1)

    failed = 0

    for i, item_url in enumerate(urls, 1):
        if not download_one(item_url, i, total, out_dir, force=args.force):
            failed += 1

    print()

    if failed == 0:
        ok("playlist finished")
        info(f"saved to: {out_dir}")

        if not update_song_list_if_needed(category):
            sys.exit(1)
    else:
        warn(f"playlist finished with {failed} failed")
        info(f"saved to: {out_dir}")
        skip("song list update (download failed)")


if __name__ == "__main__":
    main()