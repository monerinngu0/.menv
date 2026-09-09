from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from common import info, ng


EXTENSIONS = {
    ".py",
}


def require_python_runtime() -> str:
    name = os.environ.get(
        "KYOPRO_PYTHON",
        "python3",
    )
    path = shutil.which(name)

    if path is None:
        ng(f"{name} not found")
        sys.exit(1)

    return path


def prepare(
    source: Path,
    build_dir: Path,
    *,
    no_build: bool,
    output_name: str,
) -> tuple[list[str], Path]:
    del build_dir, output_name

    if no_build:
        info("--no-build has no effect for Python")

    python = require_python_runtime()
    info(f"using python runtime: {python}")

    return [python, str(source)], source