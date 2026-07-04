#!/usr/bin/env python3

from __future__ import annotations

import os
import platform
import shutil
import sys
from pathlib import Path


MENV_ROOT = Path(os.environ.get("MENV_ROOT", Path.home() / ".menv"))
SONG_ROOT = MENV_ROOT / "envs" / "song"

sys.path.insert(0, str(MENV_ROOT / ".lib"))

import check  # noqa: E402


FFMPEG_URLS = {
    "x86_64": "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz",
    "amd64": "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz",
    "aarch64": "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz",
    "arm64": "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz",
}


def ffmpeg_bin_dir() -> Path:
    return SONG_ROOT / ".tools" / "ffmpeg" / "bin"


def has_ffmpeg() -> bool:
    ffmpeg = ffmpeg_bin_dir() / "ffmpeg"
    ffprobe = ffmpeg_bin_dir() / "ffprobe"

    return (
        ffmpeg.exists()
        and os.access(ffmpeg, os.X_OK)
        and ffprobe.exists()
        and os.access(ffprobe, os.X_OK)
    )


def install_ffmpeg() -> bool:
    arch = platform.machine().lower()
    url = FFMPEG_URLS.get(arch)

    if url is None:
        print(f"unsupported architecture: {arch}", file=sys.stderr)
        return False

    with check.temp_dir() as tmp:
        tmp_dir = Path(tmp)
        archive = tmp_dir / "ffmpeg.tar.xz"
        extract_dir = tmp_dir / "extract"

        if not check.download_file(url, archive):
            print("failed to download ffmpeg", file=sys.stderr)
            return False

        if not check.safe_extract_tar(archive, extract_dir):
            print("failed to extract ffmpeg", file=sys.stderr)
            return False

        ffmpeg_src = check.find_file(extract_dir, "ffmpeg")
        ffprobe_src = check.find_file(extract_dir, "ffprobe")

        if ffmpeg_src is None or ffprobe_src is None:
            print("ffmpeg or ffprobe not found in archive", file=sys.stderr)
            return False

        bin_dir = ffmpeg_bin_dir()
        bin_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy2(ffmpeg_src, bin_dir / "ffmpeg")
        shutil.copy2(ffprobe_src, bin_dir / "ffprobe")

        (bin_dir / "ffmpeg").chmod(0o755)
        (bin_dir / "ffprobe").chmod(0o755)

    return has_ffmpeg()


def has_package(package: str) -> bool:
    if package == "ffmpeg":
        return has_ffmpeg()

    return False


def install_package(package: str) -> bool:
    if package == "ffmpeg":
        return install_ffmpeg()

    print(f"unknown song package: {package}", file=sys.stderr)
    return False