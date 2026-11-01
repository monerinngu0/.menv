from __future__ import annotations

import base64
import os
import shutil
import subprocess
from pathlib import Path

from config import ClipboardConfig, load_config


COMMANDS = (
    ("clip.exe",),
    ("clip",),
    ("wl-copy",),
    ("xclip", "-selection", "clipboard"),
    ("xsel", "--clipboard", "--input"),
)


def _copy_command(command: tuple[str, ...], data: bytes) -> bool:
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


def copy_to_clipboard(
    source: Path,
    config: ClipboardConfig | None = None,
) -> bool:
    config = config if config is not None else load_config().clipboard

    try:
        data = source.read_bytes()
    except OSError:
        return False

    if config.method == "osc52":
        return _copy_osc52(data)
    if config.method == "command":
        return _copy_command(config.command, data)

    commands = ((config.command,) if config.command else ()) + COMMANDS
    for command in commands:
        if shutil.which(command[0]) and _copy_command(command, data):
            return True

    return _copy_osc52(data)
