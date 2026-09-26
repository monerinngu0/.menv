from __future__ import annotations

import os
import shutil
from pathlib import Path


EXTENSIONS = {".py"}
SUBMISSION_FILENAME = "sol.py"

ATCODER_LANGUAGE = "CPython"

PYTHON = os.environ.get(
    "KYOPRO_PYTHON",
    "python3",
)


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
