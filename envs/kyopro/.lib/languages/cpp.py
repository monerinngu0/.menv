from __future__ import annotations

import re
import subprocess
from pathlib import Path

from config import load_config
from languages.command import (
    render_command,
)


NAME = "cpp"
EXTENSIONS = {".cpp"}
SUBMISSION_FILENAME = "sol.cpp"

INCLUDE_PATTERN = re.compile(
    r'^\s*#\s*include\s*[<"]([^>"]+)[>"]\s*$'
)


class CppError(Exception):
    pass


def compile(
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

    config = load_config()

    command = list(
        render_command(
            config.cpp.build_command,
            source=source,
            output=output,
        )
    )

    include_dirs = (
        *config.cpp.include_dirs,
        *include_dirs,
    )

    for directory in include_dirs:
        command.extend(
            [
                "-I",
                str(directory.resolve()),
            ]
        )

    completed = subprocess.run(
        command
    )

    if completed.returncode != 0:
        raise CppError(
            f"compile failed: {source}"
        )

    return output


def run_command(
    source: Path,
    executable: Path,
) -> tuple[str, ...]:
    config = load_config()

    return render_command(
        config.cpp.run_command,
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

    config = load_config()

    include_dirs = tuple(
        path.resolve()
        for path in (
            *config.cpp.include_dirs,
            *include_dirs,
        )
    )

    visited: set[Path] = set()

    text = _expand_file(
        source,
        include_dirs=include_dirs,
        visited=visited,
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.write_text(
        text,
        encoding="utf-8",
    )

    return output


def _expand_file(
    path: Path,
    *,
    include_dirs: tuple[Path, ...],
    visited: set[Path],
) -> str:
    path = path.resolve()

    if path in visited:
        return ""

    visited.add(path)

    try:
        lines = path.read_text(
            encoding="utf-8"
        ).splitlines()
    except OSError as error:
        raise CppError(
            f"failed to read source: {path}"
        ) from error

    result: list[str] = []

    for line in lines:
        match = INCLUDE_PATTERN.match(line)

        if match is None:
            result.append(line)
            continue

        include_name = match.group(1)

        header = _resolve_include(
            include_name,
            current_dir=path.parent,
            include_dirs=include_dirs,
        )

        if header is None:
            result.append(line)
            continue

        result.append(
            f"// begin include: {include_name}"
        )

        expanded = _expand_file(
            header,
            include_dirs=include_dirs,
            visited=visited,
        )

        if expanded:
            result.append(expanded)

        result.append(
            f"// end include: {include_name}"
        )

    return "\n".join(result) + "\n"


def _resolve_include(
    name: str,
    *,
    current_dir: Path,
    include_dirs: tuple[Path, ...],
) -> Path | None:
    candidates = [
        current_dir / name,
        *(
            directory / name
            for directory in include_dirs
        ),
    ]

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()

    return None
