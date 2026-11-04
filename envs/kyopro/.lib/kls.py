from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from contest import CONTEST_FILE, ContestError, load_contest


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="kls",
        description="List contest workspaces in the current directory.",
    )
    parser.parse_args()

    try:
        names = []
        for path in Path.cwd().iterdir():
            if not path.is_dir() or not (path / CONTEST_FILE).is_file():
                continue

            try:
                load_contest(path)
            except (ContestError, OSError, UnicodeError):
                continue

            names.append(path.name)

        if names:
            # Let ls handle terminal width, columns and filename quoting.
            result = subprocess.run(["ls", "-d", "--", *names])
            sys.exit(result.returncode)
    except OSError as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
