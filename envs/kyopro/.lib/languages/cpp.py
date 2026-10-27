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
    seen_includes: set[str] = set()

    text = _expand_file(
        source,
        include_dirs=include_dirs,
        visited=visited,
        seen_includes=seen_includes,
    )

    text = _merge_namespaces(text)

    # Normalize blank lines once, after all nested includes are expanded.
    cleaned: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            if cleaned and cleaned[-1].strip():
                cleaned.append("")
        else:
            if (
                INCLUDE_PATTERN.match(line)
                and len(cleaned) >= 2
                and not cleaned[-1]
                and INCLUDE_PATTERN.match(cleaned[-2])
            ):
                cleaned.pop()
            cleaned.append(line)
    while cleaned and not cleaned[-1].strip():
        cleaned.pop()
    text = "\n".join(cleaned) + "\n"

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.write_text(
        text,
        encoding="utf-8",
    )

    return output


def _merge_namespaces(text: str) -> str:
    # Tokenize literals/comments as units so their braces are not scopes.
    token_pattern = re.compile(
        r'(?P<raw>(?:u8|u|U|L)?R"(?P<delimiter>[^\s()\\]{0,16})\('
        r'.*?\)(?P=delimiter)")'
        r'|(?P<comment>//[^\n]*|/\*.*?\*/)'
        r'|(?P<literal>"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')'
        r'|(?P<directive>^[ \t]*\#(?:\\\n|[^\n])*)'
        r'|[A-Za-z_]\w*|[^\s]',
        re.DOTALL | re.MULTILINE,
    )
    tokens = [
        token for token in token_pattern.finditer(text)
        if token.lastgroup != "comment"
    ]
    scopes: list[str | None] = []
    edits: list[tuple[int, int]] = []

    for i, token in enumerate(tokens):
        value = token.group()
        if token.lastgroup == "directive":
            # Conditional compilation can change the brace structure.
            if re.match(r"\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b", value):
                scopes.clear()
        elif value == "{":
            name = None
            if (
                i >= 2
                and tokens[i - 2].group() == "namespace"
                and re.fullmatch(r"[A-Za-z_]\w*", tokens[i - 1].group())
                and (i < 3 or tokens[i - 3].group() != "inline")
            ):
                name = tokens[i - 1].group()
            scopes.append(name)
        elif value == "}" and scopes:
            name = scopes.pop()
            if name is None or i + 3 >= len(tokens):
                continue
            following = tokens[i + 1:i + 4]
            if [item.group() for item in following] != ["namespace", name, "{"]:
                continue
            # The scope stack identifies the closing brace; spelling and
            # line layout are irrelevant. Keep comments between the tokens.
            edits.append((token.start(), token.end()))
            edits.extend((item.start(), item.end()) for item in following)

    for start, end in sorted(edits, reverse=True):
        text = text[:start] + " " + text[end:]
    return text



def _expand_file(
    path: Path,
    *,
    include_dirs: tuple[Path, ...],
    visited: set[Path],
    seen_includes: set[str],
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
        if line.strip() in ("#pragma once", "#pragma kbuild expand"):
            continue

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
            # Keep external headers only once.
            # Include spelling is kept so system paths remain unchanged.
            if include_name not in seen_includes:
                seen_includes.add(include_name)
                result.append(line)
            continue

        expanded = _expand_file(
            header,
            include_dirs=include_dirs,
            visited=visited,
            seen_includes=seen_includes,
        )

        if expanded:
            result.append(expanded)

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
