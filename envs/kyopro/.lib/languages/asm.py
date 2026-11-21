from __future__ import annotations

import re
import subprocess
from pathlib import Path

from config import load_config
from languages.command import render_command


NAME = "asm"
EXTENSIONS = {".asm"}
SUBMISSION_FILENAME = "sol.asm"

INCLUDE_DIRECTIVE = re.compile(r"^\s*%\s*include\b", re.IGNORECASE)
INCLUDE_PATH = re.compile(r"""\s+(?:"([^"]+)"|'([^']+)')\s*(?:;[^\n]*)?""")


class AsmError(Exception):
    pass


def compile(
    source: Path,
    output: Path,
    *,
    include_dirs: tuple[Path, ...] = (),
) -> Path:
    source = source.resolve()
    output = output.resolve()
    config = load_config().asm

    command = list(render_command(config.build_command, source=source, output=output))
    for directory in (source.parent, *config.include_dirs, *include_dirs):
        command.extend(("-I", str(directory.resolve())))

    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(command, check=True)
    return output


def run_command(source: Path, executable: Path) -> tuple[str, ...]:
    return render_command(
        load_config().asm.run_command,
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
    config = load_config().asm
    search_dirs = (source.parent, *config.include_dirs, *include_dirs)

    text = _expand_file(source, search_dirs, (), output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    return output


def _expand_file(
    path: Path,
    search_dirs: tuple[Path, ...],
    ancestors: tuple[Path, ...],
    output: Path,
) -> str:
    if path == output:
        raise AsmError(f"output must differ from source and includes: {path}")

    chain = (*ancestors, path)
    lines: list[str] = []
    continued = False

    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        directive = INCLUDE_DIRECTIVE.match(line)
        if directive is None:
            lines.append(line + "\n")
            continued = line.rstrip().endswith("\\")
            continue

        location = f"{path}:{number}"
        match = INCLUDE_PATH.fullmatch(line[directive.end():])
        if continued or match is None or line.rstrip().endswith("\\"):
            raise AsmError(f"{location}: expected a single-line %include with a quoted path")

        name = match[1] or match[2]
        for directory in search_dirs:
            target = directory / name
            if target.is_file():
                target = target.resolve()
                break
        else:
            raise AsmError(f"{location}: include not found: {name}")

        if target in chain:
            route = " -> ".join(str(item) for item in (*chain, target))
            raise AsmError(f"{location}: cyclic %include: {route}")

        lines.append(_expand_file(target, search_dirs, chain, output))

    return "".join(lines)
