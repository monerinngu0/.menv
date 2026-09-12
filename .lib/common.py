from __future__ import annotations

import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TypeVar


GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
RESET = "\033[0m"

T = TypeVar("T")


def ok(msg: str) -> None:
    print(f"{GREEN}[OK]{RESET}   {msg}")


def ng(msg: str) -> None:
    print(f"{RED}[NG]{RESET}   {msg}", file=sys.stderr)


def warn(msg: str) -> None:
    print(f"{YELLOW}[WARN]{RESET} {msg}")


def info(msg: str) -> None:
    print(f"{BLUE}[INFO]{RESET} {msg}")


def skip(msg: str) -> None:
    print(f"{YELLOW}[SKIP]{RESET} {msg}")


def fail(message: str, *, code: int = 1) -> None:
    ng(message)
    raise SystemExit(code)


def run_quiet(
    message: str,
    cmd: Sequence[str],
    *,
    cwd: str | Path | None = None,
) -> bool:
    with tempfile.NamedTemporaryFile(
        mode="w+",
        delete=False,
        encoding="utf-8",
    ) as file:
        log_path = Path(file.name)

    print(message, end="", flush=True)

    try:
        with log_path.open(
            "w",
            encoding="utf-8",
            errors="replace",
        ) as log:
            proc = subprocess.Popen(
                list(cmd),
                stdout=log,
                stderr=subprocess.STDOUT,
                cwd=cwd,
            )

        dots = 0

        while proc.poll() is None:
            time.sleep(0.5)
            dots += 1

            print(
                "\r"
                + message
                + "." * dots
                + " " * (6 - dots),
                end="",
                flush=True,
            )

            if dots >= 6:
                dots = 0

        status = proc.wait()

        if status == 0:
            print(f"\r{message} done{' ' * 6}")
            return True

        print(f"\r{message} failed{' ' * 6}")
        ng("command failed")

        print("---- log ----")
        print(
            log_path.read_text(
                encoding="utf-8",
                errors="replace",
            ),
            end="",
        )
        print("-------------")

        return False

    finally:
        log_path.unlink(missing_ok=True)


def run_quiet_func(
    message: str,
    func: Callable[[], T],
) -> T:
    done = threading.Event()
    result: dict[str, object] = {}

    def worker() -> None:
        try:
            result["value"] = func()
        except BaseException as error:
            result["error"] = error
        finally:
            done.set()

    thread = threading.Thread(
        target=worker,
        daemon=True,
    )
    thread.start()

    dots = 0
    print(message, end="", flush=True)

    while not done.wait(0.5):
        dots = (dots + 1) % 7

        print(
            "\r"
            + message
            + "." * dots
            + " " * (6 - dots),
            end="",
            flush=True,
        )

    thread.join()

    error = result.get("error")

    if isinstance(error, BaseException):
        print(f"\r{message} failed{' ' * 6}")
        raise error

    print(f"\r{message} done{' ' * 6}")

    return result["value"]  # type: ignore[return-value]


def run_quiet_capture(
    message: str,
    cmd: Sequence[str],
    *,
    cwd: str | Path | None = None,
) -> tuple[bool, str]:
    with tempfile.NamedTemporaryFile(
        mode="w+",
        delete=False,
        encoding="utf-8",
    ) as file:
        log_path = Path(file.name)

    print(message, end="", flush=True)

    try:
        with log_path.open(
            "w",
            encoding="utf-8",
            errors="replace",
        ) as log:
            proc = subprocess.Popen(
                list(cmd),
                stdout=log,
                stderr=subprocess.STDOUT,
                cwd=cwd,
            )

        dots = 0

        while proc.poll() is None:
            time.sleep(0.5)
            dots += 1

            print(
                "\r"
                + message
                + "." * dots
                + " " * (6 - dots),
                end="",
                flush=True,
            )

            if dots >= 6:
                dots = 0

        status = proc.wait()

        log_text = log_path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        if status == 0:
            print(f"\r{message} done{' ' * 6}")
            return True, log_text

        print(f"\r{message} failed{' ' * 6}")
        ng("command failed")

        print("---- log ----")
        print(log_text, end="")
        print("-------------")

        return False, log_text

    finally:
        log_path.unlink(missing_ok=True)