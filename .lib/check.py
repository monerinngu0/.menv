#!/usr/bin/env python3

from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path


MENV_ROOT = Path(os.environ.get("MENV_ROOT", Path.home() / ".menv"))
MENV_ENVS = MENV_ROOT / "envs"


def run(cmd: list[str], *, cwd: Path | None = None) -> int:
    return subprocess.run(cmd, cwd=cwd).returncode


def apt_global_package_exists(package: str) -> bool:
    result = subprocess.run(
        ["dpkg-query", "-W", "-f=${Status}", package],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )

    return result.returncode == 0 and "install ok installed" in result.stdout


def env_tools_dir(env_path: Path) -> Path:
    return env_path / ".tools"


def local_package_dir(env_path: Path, package: str) -> Path:
    return env_tools_dir(env_path) / package


def local_bin_dirs(env_path: Path) -> list[Path]:
    tools = env_tools_dir(env_path)

    if not tools.exists():
        return []

    result: list[Path] = []

    for child in sorted(tools.iterdir()):
        if not child.is_dir():
            continue

        result.append(child / "bin")
        result.append(child)

    return result


def venv_bin_dir(env_path: Path, venv_rel: str = ".venv") -> Path:
    return env_path / venv_rel / "bin"


def find_command(
    name: str,
    *,
    env_path: Path | None = None,
    venv_rel: str = ".venv",
    include_global: bool = True,
) -> Path | None:
    candidates: list[Path] = []

    if env_path is not None:
        candidates.append(venv_bin_dir(env_path, venv_rel) / name)

        for bin_dir in local_bin_dirs(env_path):
            candidates.append(bin_dir / name)

        candidates.append(env_path / ".bin" / name)

    candidates.append(MENV_ROOT / ".bin" / name)

    for path in candidates:
        if path.exists() and os.access(path, os.X_OK):
            return path

    if include_global:
        found = shutil.which(name)
        if found is not None:
            return Path(found)

    return None


def command_exists(
    name: str,
    *,
    env_path: Path | None = None,
    venv_rel: str = ".venv",
    include_global: bool = True,
) -> bool:
    return find_command(
        name,
        env_path=env_path,
        venv_rel=venv_rel,
        include_global=include_global,
    ) is not None


def venv_exists(venv_path: Path) -> bool:
    python = venv_path / "bin" / "python"
    return python.exists() and os.access(python, os.X_OK)


def pip_package_exists(venv_path: Path, package: str) -> bool:
    python = venv_path / "bin" / "python"

    if not python.exists():
        return False

    result = subprocess.run(
        [str(python), "-m", "pip", "show", package],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return result.returncode == 0


def download_file(url: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        urllib.request.urlretrieve(url, dest)
        return True
    except Exception:
        return False


def safe_extract_tar(archive: Path, dest: Path) -> bool:
    dest.mkdir(parents=True, exist_ok=True)
    base = dest.resolve()

    try:
        with tarfile.open(archive) as tf:
            for member in tf.getmembers():
                target = (dest / member.name).resolve()

                if not str(target).startswith(str(base)):
                    return False

            tf.extractall(dest)

        return True
    except Exception:
        return False


def temp_dir():
    return tempfile.TemporaryDirectory()


def find_file(root: Path, name: str) -> Path | None:
    for path in root.rglob(name):
        if path.is_file():
            return path

    return None