from __future__ import annotations

import shutil
from pathlib import Path

from config import load_config
from languages.command import render_command

EXTENSIONS = {".py"}
SUBMISSION_FILENAME = "sol.py"

ATCODER_LANGUAGE = "CPython"


def compile(
    source: Path,
    output: Path,
    *,
    include_dirs: tuple[Path, ...] = (),
) -> Path:
    # Python はコンパイル不要
    return source.resolve()


def run_command(
    source: Path,
    executable: Path,
) -> tuple[str, ...]:
    config = load_config()

    return render_command(
        config.python.run_command,
        source=source,
        output=executable,
    )


def build_submission(
    source: Path,
    output: Path,
    *,
    include_dirs: tuple[Path, ...] = (),
) -> Path:
    source = source.resolve()
    output = output.resolve()

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copyfile(
        source,
        output,
    )

    return output
