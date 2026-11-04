from __future__ import annotations

import argparse
import sys
from pathlib import Path

from contest import CONTEST_FILE


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="kls",
        description="List contest workspaces in the current directory.",
    )
    parser.parse_args()

    try:
        names = sorted(
            path.name
            for path in Path.cwd().iterdir()
            if path.is_dir()
            and (path / CONTEST_FILE).is_file()
        )
    except OSError as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        sys.exit(1)

    for name in names:
        print(name)


if __name__ == "__main__":
    main()
