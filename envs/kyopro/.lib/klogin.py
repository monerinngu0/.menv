#!/usr/bin/env python3

import os
import shutil
import subprocess
import sys
from pathlib import Path

MENV_ROOT = Path(os.environ.get("MENV_ROOT", Path.home() / ".menv"))
KYOPRO_ROOT = MENV_ROOT / "envs" / "kyopro"

sys.path.insert(0, str(MENV_ROOT / ".lib"))
sys.path.insert(0, str(KYOPRO_ROOT / ".lib"))

from common import ok, ng, info, run_quiet


def require_command(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        ng(f"{name} not found")
        sys.exit(1)
    return path


def is_logged_in(oj: str) -> bool:
    return subprocess.run(
        [oj, "login", "--check", "https://atcoder.jp/"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def main() -> None:
    oj = require_command("oj")

    if is_logged_in(oj):
        ok("AtCoder login")
        return

    ng("AtCoder login")

    info("opening oj login")
    result = subprocess.run([oj, "login", "https://atcoder.jp/"])

    if result.returncode != 0:
        ng("login failed")
        sys.exit(result.returncode)

    if is_logged_in(oj):
        ok("AtCoder login")
    else:
        ng("login check failed")
        sys.exit(1)


if __name__ == "__main__":
    main()