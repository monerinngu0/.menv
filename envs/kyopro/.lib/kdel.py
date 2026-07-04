#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


MENV_ROOT = Path(os.environ.get("MENV_ROOT", Path.home() / ".menv"))
KYOPRO_ROOT = MENV_ROOT / "envs" / "kyopro"

sys.path.insert(0, str(MENV_ROOT / ".lib"))
sys.path.insert(0, str(KYOPRO_ROOT / ".lib"))

from common import ok, ng, info  # noqa: E402


def read_contest_file(path: Path) -> str | None:
    contest_file = path / ".contest"

    if not contest_file.exists():
        return None

    try:
        return contest_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def validate_contest_dir(contest_arg: str) -> Path:
    if contest_arg in {"", ".", ".."}:
        ng("invalid contest name")
        print("usage: kdel <contest> [--force|-f]")
        sys.exit(1)

    contest_dir = Path(contest_arg)

    # 絶対パス削除は危ないので禁止
    if contest_dir.is_absolute():
        ng("absolute path is not allowed")
        sys.exit(1)

    # ../abc みたいな削除も危ないので禁止
    if ".." in contest_dir.parts:
        ng("parent path '..' is not allowed")
        sys.exit(1)

    if not contest_dir.exists():
        ng(f"directory not found: {contest_arg}")
        sys.exit(1)

    if not contest_dir.is_dir():
        ng(f"not a directory: {contest_arg}")
        sys.exit(1)

    if contest_dir.is_symlink():
        ng(f"symlink is not allowed: {contest_arg}")
        sys.exit(1)

    contest_name = contest_dir.name
    contest_id = read_contest_file(contest_dir)

    if contest_id is None:
        ng(f"{contest_arg} is not a contest directory")
        sys.exit(1)

    if contest_id != contest_name:
        ng("invalid contest directory")
        info(f"expected .contest: {contest_name}")
        info(f"actual .contest: {contest_id}")
        sys.exit(1)

    return contest_dir


def ask_confirm(contest_dir: Path) -> bool:
    ans = input(f"Delete '{contest_dir}'? [y/N] ").strip()
    return ans in {"y", "Y"}


def delete_contest(contest_arg: str, *, force: bool) -> None:
    contest_dir = validate_contest_dir(contest_arg)

    if not force:
        if not ask_confirm(contest_dir):
            print("cancelled.")
            return

    shutil.rmtree(contest_dir)
    ok(f"deleted: {contest_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="kdel",
        description="Delete an AtCoder contest directory.",
    )

    parser.add_argument("contest", help="contest directory name, e.g. abc464")
    parser.add_argument("-f", "--force", action="store_true", help="delete without confirmation")

    args = parser.parse_args()

    delete_contest(args.contest, force=args.force)


if __name__ == "__main__":
    main()