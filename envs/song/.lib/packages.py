#!/usr/bin/env python3

from __future__ import annotations

import os
import platform
import shutil
import sys
import zipfile
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


DENO_URLS = {
    "x86_64": "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip",
    "amd64": "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip",
    "aarch64": "https://github.com/denoland/deno/releases/latest/download/deno-aarch64-unknown-linux-gnu.zip",
    "arm64": "https://github.com/denoland/deno/releases/latest/download/deno-aarch64-unknown-linux-gnu.zip",
}


def tool_bin_dir(name: str) -> Path:
    return SONG_ROOT / ".tools" / name / "bin"


def ffmpeg_bin_dir() -> Path:
    return tool_bin_dir("ffmpeg")


def deno_bin_dir() -> Path:
    return tool_bin_dir("deno")


def is_executable(path: Path) -> bool:
    return path.exists() and os.access(path, os.X_OK)


def has_ffmpeg() -> bool:
    ffmpeg = ffmpeg_bin_dir() / "ffmpeg"
    ffprobe = ffmpeg_bin_dir() / "ffprobe"

    return is_executable(ffmpeg) and is_executable(ffprobe)


def has_deno() -> bool:
    deno = deno_bin_dir() / "deno"

    return is_executable(deno)


def install_ffmpeg() -> bool:
    arch = platform.machine().lower()
    url = FFMPEG_URLS.get(arch)

    if url is None:
        print(f"unsupported architecture for ffmpeg: {arch}", file=sys.stderr)
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


def is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def safe_extract_zip(archive: Path, dest: Path) -> bool:
    dest.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(archive) as zf:
            for member in zf.infolist():
                target = dest / member.filename

                if not is_relative_to(target, dest):
                    print(f"unsafe zip path: {member.filename}", file=sys.stderr)
                    return False

            zf.extractall(dest)

        return True
    except Exception as e:
        print(f"failed to extract zip: {e}", file=sys.stderr)
        return False


def install_deno() -> bool:
    arch = platform.machine().lower()
    url = DENO_URLS.get(arch)

    if url is None:
        print(f"unsupported architecture for deno: {arch}", file=sys.stderr)
        return False

    with check.temp_dir() as tmp:
        tmp_dir = Path(tmp)
        archive = tmp_dir / "deno.zip"
        extract_dir = tmp_dir / "extract"

        if not check.download_file(url, archive):
            print("failed to download deno", file=sys.stderr)
            return False

        if not safe_extract_zip(archive, extract_dir):
            return False

        deno_src = check.find_file(extract_dir, "deno")

        if deno_src is None:
            print("deno not found in archive", file=sys.stderr)
            return False

        bin_dir = deno_bin_dir()
        bin_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy2(deno_src, bin_dir / "deno")
        (bin_dir / "deno").chmod(0o755)

    return has_deno()


def has_package(package: str) -> bool:
    if package == "ffmpeg":
        return has_ffmpeg()

    if package == "deno":
        return has_deno()

    return False


def install_package(package: str) -> bool:
    if package == "ffmpeg":
        return install_ffmpeg()

    if package == "deno":
        return install_deno()

    print(f"unknown song package: {package}", file=sys.stderr)
    return False