from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path
from collections.abc import Sequence

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
RESET = "\033[0m"


def ok(msg: str) -> None:
    print(f"{GREEN}[OK]{RESET}   {msg}")


def ng(msg: str) -> None:
    print(f"{RED}[NG]{RESET}   {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}[WARN]{RESET} {msg}")


def info(msg: str) -> None:
    print(f"{BLUE}[INFO]{RESET} {msg}")


def run_quiet(message: str, cmd: Sequence[str], *, cwd: str | Path | None = None) -> bool:
    with tempfile.NamedTemporaryFile("w+", delete=False) as f:
        log_path = Path(f.name)

    print(message, end="", flush=True)

    with log_path.open("w") as log:
        proc = subprocess.Popen(
            list(cmd),
            stdout=log,
            stderr=subprocess.STDOUT,
            cwd=cwd,
        )

    dots = 0
    while proc.poll() is None:
        time.sleep(0.5)
        print(".", end="", flush=True)
        dots += 1

        if dots >= 6:
            print(f"\r{message}      \r{message}", end="", flush=True)
            dots = 0

    status = proc.wait()

    if status == 0:
        print(f"\r{message} done")
        log_path.unlink(missing_ok=True)
        return True

    print(f"\r{message} failed")
    ng("command failed")
    print("---- log ----")
    print(log_path.read_text(errors="replace"), end="")
    print("-------------")
    log_path.unlink(missing_ok=True)
    return False