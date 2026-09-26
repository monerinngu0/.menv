from __future__ import annotations

from pathlib import Path
from types import ModuleType

from . import cpp
from . import python


class LanguageError(Exception):
    pass


LANGUAGES = (
    cpp,
    python,
)


def get_language(
    source: Path,
) -> ModuleType:
    for language in LANGUAGES:
        if source.suffix in language.EXTENSIONS:
            return language

    raise LanguageError(
        f"unsupported source language: "
        f"{source.suffix}"
    )


def supported_extensions() -> set[str]:
    extensions: set[str] = set()

    for language in LANGUAGES:
        extensions.update(
            language.EXTENSIONS
        )

    return extensions


def find_source(
    base: Path,
) -> Path:
    candidates = [
        base.with_suffix(extension)
        for extension in sorted(
            supported_extensions()
        )
    ]

    found = [
        path.resolve()
        for path in candidates
        if path.is_file()
    ]

    if not found:
        raise LanguageError(
            f"source not found: {base.name}"
        )

    if len(found) > 1:
        names = ", ".join(
            path.name
            for path in found
        )

        raise LanguageError(
            f"multiple source files found: {names}"
        )

    return found[0]
