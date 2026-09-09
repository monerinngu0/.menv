from __future__ import annotations

import argparse
import sys
from pathlib import Path

from build import (
    BuildError,
    build_submission,
)
from languages import LanguageError


class KbuildError(Exception):
    pass


def normalize_include_dirs(
    paths: list[Path],
) -> tuple[Path, ...]:
    result: list[Path] = []

    for path in paths:
        path = path.expanduser().resolve()

        if not path.is_dir():
            raise KbuildError(
                f"include directory not found: {path}"
            )

        result.append(path)

    return tuple(result)


def resolve_source(
    source: Path,
) -> Path:
    source = source.expanduser().resolve()

    if not source.is_file():
        raise KbuildError(
            f"source not found: {source}"
        )

    return source


def resolve_output(
    output: Path | None,
) -> Path | None:
    if output is None:
        return None

    return output.expanduser().resolve()


def run(
    source: Path,
    *,
    output: Path | None,
    include_dirs: tuple[Path, ...],
) -> Path:
    result = build_submission(
        source,
        output=output,
        include_dirs=include_dirs,
    )

    return result.output


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="kbuild",
        description=(
            "Generate a standalone source file "
            "for online judge submission."
        ),
    )

    parser.add_argument(
        "source",
        type=Path,
        help="source file to build",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        metavar="FILE",
        help="override output path",
    )

    parser.add_argument(
        "-I",
        "--include-dir",
        action="append",
        type=Path,
        default=[],
        metavar="DIR",
        help="add an include directory",
    )

    args = parser.parse_args()

    try:
        source = resolve_source(
            args.source
        )

        output = resolve_output(
            args.output
        )

        include_dirs = normalize_include_dirs(
            args.include_dir
        )

        built = run(
            source,
            output=output,
            include_dirs=include_dirs,
        )

    except (
        BuildError,
        LanguageError,
        KbuildError,
    ) as error:
        print(
            f"[ERROR] {error}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"[OK] built: {built}")


if __name__ == "__main__":
    main()