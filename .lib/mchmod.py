#!/usr/bin/env python3

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path


MENV_ROOT = Path(os.environ.get("MENV_ROOT", Path.home() / ".menv"))

sys.path.insert(0, str(MENV_ROOT / ".lib"))

from common import ok, warn, info  # noqa: E402


EXCLUDE_DIRS = {
    "venv",
    ".venv",
    "__pycache__",
}


def has_shebang(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            return f.readline().startswith(b"#!")
    except OSError:
        return False


def is_excluded(path: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in path.parts)


def is_under_dotbin(path: Path) -> bool:
    return ".bin" in path.parts


def add_executable(path: Path, dry_run: bool = False) -> bool:
    mode = path.stat().st_mode

    if os.access(path, os.X_OK):
        return False

    new_mode = mode

    # chmod +x に近い挙動
    if mode & stat.S_IRUSR:
        new_mode |= stat.S_IXUSR
    if mode & stat.S_IRGRP:
        new_mode |= stat.S_IXGRP
    if mode & stat.S_IROTH:
        new_mode |= stat.S_IXOTH

    if not dry_run:
        path.chmod(new_mode)

    print(f"chmod +x {path}")
    return True


def iter_command_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue

        if is_excluded(path):
            continue

        if not is_under_dotbin(path):
            continue

        yield path


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    if not MENV_ROOT.exists():
        warn(f"MENV_ROOT not found: {MENV_ROOT}")
        sys.exit(1)

    count = 0

    for path in iter_command_files(MENV_ROOT):
        if os.access(path, os.X_OK):
            continue

        if not has_shebang(path):
            continue

        if add_executable(path, dry_run=dry_run):
            count += 1

    if dry_run:
        info(f"dry-run: {count} files would be updated")
    else:
        ok(f"updated {count} files")


if __name__ == "__main__":
    main()