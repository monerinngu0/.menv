#!/usr/bin/env python3

from __future__ import annotations

import os
import sys
from pathlib import Path


MENV_ROOT = Path(os.environ.get("MENV_ROOT", Path.home() / ".menv"))
SONG_ROOT = MENV_ROOT / "envs" / "song"

sys.path.insert(0, str(MENV_ROOT / ".lib"))
sys.path.insert(0, str(SONG_ROOT / ".lib"))

from common import ok, info  # noqa: E402
from song import create_category, require_workspace  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: scat <category>")
        sys.exit(1)

    root = require_workspace()
    cat = create_category(root, sys.argv[1])

    ok(f"category ready: {cat.name}")
    info(f"path: {cat}")


if __name__ == "__main__":
    main()