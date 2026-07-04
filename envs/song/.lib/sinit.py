#!/usr/bin/env python3

from __future__ import annotations

import os
import sys
from pathlib import Path


MENV_ROOT = Path(os.environ.get("MENV_ROOT", Path.home() / ".menv"))
SONG_ROOT = MENV_ROOT / "envs" / "song"

sys.path.insert(0, str(MENV_ROOT / ".lib"))
sys.path.insert(0, str(SONG_ROOT / ".lib"))

from common import ok, ng, info  # noqa: E402
from song import WORKSPACE_MARKER, write_json  # noqa: E402


def main() -> None:
    if len(sys.argv) > 2:
        print("usage: sinit [dir]")
        sys.exit(1)

    root = Path(sys.argv[1]) if len(sys.argv) == 2 else Path.cwd()

    if root.exists() and not root.is_dir():
        ng(f"not a directory: {root}")
        sys.exit(1)

    root = root.resolve()

    root.mkdir(parents=True, exist_ok=True)

    config_dir = root / ".config"
    config_dir.mkdir(parents=True, exist_ok=True)

    workspace_marker = config_dir / "workspace"
    workspace_marker.write_text(WORKSPACE_MARKER + "\n", encoding="utf-8")

    config_json = config_dir / "config.json"

    if not config_json.exists():
        write_json(
            config_json,
            {
                "type": WORKSPACE_MARKER,
                "version": 1,
                "categories": [],
            },
        )

    ok(f"song workspace initialized: {root}")
    info("next: scat <category>")


if __name__ == "__main__":
    main()