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

def skip(msg: str) -> None:
    print(f"{YELLOW}[SKIP]{RESET} {msg}")


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

def run_quiet_func(message: str, func):
    import threading

    done = threading.Event()
    result = {}

    def worker() -> None:
        try:
            result["value"] = func()
        except BaseException as e:
            result["error"] = e
        finally:
            done.set()

    thread = threading.Thread(target=worker)
    thread.start()

    dots = 0
    print(message, end="", flush=True)

    while not done.wait(0.5):
        dots = (dots + 1) % 7
        print("\r" + message + "." * dots + " " * (6 - dots), end="", flush=True)

    thread.join()

    if "error" in result:
        print("\r" + message + " failed")
        raise result["error"]

    print("\r" + message + " done")
    return result.get("value")

def run_quiet_capture(
    message: str,
    cmd: Sequence[str],
    *,
    cwd: str | Path | None = None,
) -> tuple[bool, str]:
    with tempfile.NamedTemporaryFile("w+", delete=False, encoding="utf-8") as f:
        log_path = Path(f.name)

    print(message, end="", flush=True)

    with log_path.open("w", encoding="utf-8", errors="replace") as log:
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
    log_text = log_path.read_text(encoding="utf-8", errors="replace")

    if status == 0:
        print(f"\r{message} done")
        log_path.unlink(missing_ok=True)
        return True, log_text

    print(f"\r{message} failed")
    ng("command failed")
    print("---- log ----")
    print(log_text, end="")
    print("-------------")
    log_path.unlink(missing_ok=True)

    return False, log_text