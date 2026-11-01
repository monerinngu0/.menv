from __future__ import annotations

import sys
from pathlib import Path

from config import ClipboardConfig, load_config

# The shared clipboard command works independently of the kyopro environment.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / ".lib"))
from menv_clipboard import copy_bytes  # noqa: E402


def copy_to_clipboard(
    source: Path,
    config: ClipboardConfig | None = None,
) -> bool:
    config = config if config is not None else load_config().clipboard
    try:
        data = source.read_bytes()
    except OSError:
        return False
    return copy_bytes(data, config)
