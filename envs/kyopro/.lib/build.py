#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from contest import find_contest_root
from languages import get_language


class BuildError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class BuildResult:
    source: Path
    output: Path


def default_output_path(
    source: Path,
) -> Path:
    source = source.resolve()
    root = find_contest_root(source.parent)

    language = get_language(source)

    filename = getattr(
        language,
        "SUBMISSION_FILENAME",
        None,
    )

    if not isinstance(filename, str) or not filename:
        raise BuildError(
            f"submission filename not defined for: {source.suffix}"
        )

    if root is None:
        return source.parent / filename

    if source.parent != root:
        raise BuildError(
            f"contest source must be in contest root: {source}"
        )

    problem = source.stem

    return (
        root
        / ".build"
        / problem
        / filename
    )


def build_submission(
    source: Path,
    *,
    output: Path | None = None,
    include_dirs: tuple[Path, ...] = (),
) -> BuildResult:
    source = source.resolve()

    if not source.is_file():
        raise BuildError(
            f"source not found: {source}"
        )

    language = get_language(source)

    if output is None:
        output = default_output_path(source)
    else:
        output = output.resolve()

    try:
        built = language.build_submission(
            source,
            output,
            include_dirs=include_dirs,
        )
    except Exception as error:
        raise BuildError(
            f"failed to build submission source: {source}"
        ) from error

    built = Path(built).resolve()

    if not built.is_file():
        raise BuildError(
            f"submission source was not created: {built}"
        )

    return BuildResult(
        source=source,
        output=built,
    )