from __future__ import annotations

import argparse
import base64
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ClipboardConfig:
    method: str = "auto"
    command: tuple[str, ...] = ()


COMMANDS = (
    ("clip.exe",),
    ("clip",),
    ("wl-copy",),
    ("xclip", "-selection", "clipboard"),
    ("xsel", "--clipboard", "--input"),
)


def _copy_command(command: tuple[str, ...], data: bytes) -> bool:
    if not command:
        return False
    executable = shutil.which(command[0])
    wrapper = Path(__file__).resolve().parents[1] / ".bin" / "clip"
    if executable and Path(executable).resolve() == wrapper.resolve():
        return False
    if executable and Path(executable).name.lower() == "clip.exe":
        try:
            # Windows Unicode input avoids the local ANSI code page.
            data = b"\xff\xfe" + data.decode("utf-8").encode("utf-16-le")
        except UnicodeError:
            return False
    try:
        completed = subprocess.run(
            command,
            input=data,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return False

    return completed.returncode == 0


def _copy_osc52(data: bytes) -> bool:
    sequence = b"\x1b]52;c;" + base64.b64encode(data) + b"\x07"
    if os.environ.get("TMUX"):
        sequence = (
            b"\x1bPtmux;" + sequence.replace(b"\x1b", b"\x1b\x1b") + b"\x1b\\"
        )

    try:
        # Use the controlling terminal, never redirected stdout or log files.
        with open("/dev/tty", "wb") as terminal:
            terminal.write(sequence)
            terminal.flush()
    except OSError:
        return False

    # OSC 52 has no acknowledgement from the terminal.
    return True


def copy_bytes(
    data: bytes,
    config: ClipboardConfig | None = None,
) -> bool:
    config = config if config is not None else ClipboardConfig()

    if config.method == "osc52":
        return _copy_osc52(data)
    if config.method == "command":
        return _copy_command(config.command, data)

    # A remote desktop clipboard is not the SSH client's clipboard.
    if os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_TTY"):
        return _copy_osc52(data)

    commands = ((config.command,) if config.command else ()) + COMMANDS
    for command in commands:
        executable = shutil.which(command[0])
        if executable is None:
            continue
        if _copy_command(command, data):
            return True

    return _copy_osc52(data)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="clip",
        description="Copy UTF-8 text from stdin to the local clipboard (OSC 52 over SSH).",
    )
    parser.add_argument(
        "--method",
        choices=("auto", "osc52", "command"),
        default="auto",
    )
    parser.add_argument(
        "--command",
        nargs=argparse.REMAINDER,
        metavar="ARG",
        help="external command and arguments (use last)",
    )
    args = parser.parse_args()
    if args.method == "command" and not args.command:
        parser.error("--method command requires --command")
    config = ClipboardConfig(
        method=args.method,
        command=tuple(args.command or ()),
    )
    try:
        if not copy_bytes(sys.stdin.buffer.read(), config):
            print("clip: clipboard copy failed", file=sys.stderr)
            sys.exit(1)
    except OSError as error:
        print(f"clip: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
