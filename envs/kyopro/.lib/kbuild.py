#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import os
import sys
import shutil
import subprocess
from pathlib import Path
from types import ModuleType


MENV_ROOT = Path(
    os.environ.get(
        "MENV_ROOT",
        Path.home() / ".menv",
    )
)
KYOPRO_ROOT = MENV_ROOT / "envs" / "kyopro"

sys.path.insert(0, str(MENV_ROOT / ".lib"))
sys.path.insert(0, str(KYOPRO_ROOT / ".lib"))

from common import fail


LANGUAGE_DIR = Path(
    os.environ.get(
        "KBUILD_LANGUAGE_DIR",
        Path(__file__).resolve().parent
        / "kbuild_languages",
    )
)


def load_language_module(path: Path) -> ModuleType:
    module_name = f"kbuild_language_{path.stem}"
    spec = importlib.util.spec_from_file_location(
        module_name,
        path,
    )

    if spec is None or spec.loader is None:
        fail(f"failed to load language module: {path}")

    module = importlib.util.module_from_spec(spec)

    try:
        spec.loader.exec_module(module)
    except Exception as error:
        fail(
            f"failed to load language module "
            f"{path}: {error}"
        )

    return module


def load_language_handlers(
    directory: Path = LANGUAGE_DIR,
) -> tuple[dict[str, ModuleType], ModuleType | None]:
    if not directory.is_dir():
        fail(f"language directory not found: {directory}")

    handlers: dict[str, ModuleType] = {}
    default_handler: ModuleType | None = None

    for path in sorted(directory.glob("*.py")):
        if path.name.startswith("_"):
            continue

        module = load_language_module(path)
        extensions = getattr(
            module,
            "EXTENSIONS",
            None,
        )
        detect_source = getattr(
            module,
            "detect_source",
            None,
        )
        entrypoint = getattr(module, "main", None)

        if not isinstance(extensions, (set, tuple, list)):
            fail(f"EXTENSIONS not found: {path}")

        if not callable(detect_source):
            fail(f"detect_source() not found: {path}")

        if not callable(entrypoint):
            fail(f"main() not found: {path}")

        if getattr(module, "DEFAULT_HANDLER", False):
            if default_handler is not None:
                fail("multiple default language handlers")

            default_handler = module

        for extension in extensions:
            if (
                not isinstance(extension, str)
                or not extension.startswith(".")
            ):
                fail(f"invalid extension in {path}: {extension}")

            if extension in handlers:
                fail(
                    "duplicate language handler for "
                    f"{extension}: {path}"
                )

            handlers[extension] = module

    if not handlers:
        fail(f"no language handlers found: {directory}")

    return handlers, default_handler


def select_handler(
    argv: list[str],
    handlers: dict[str, ModuleType],
    default_handler: ModuleType | None,
) -> ModuleType:
    if not argv or "-h" in argv or "--help" in argv:
        if default_handler is None:
            fail("default language handler not found")

        return default_handler

    matched: list[ModuleType] = []

    for module in set(handlers.values()):
        if module.detect_source(argv) is not None:
            matched.append(module)

    if len(matched) == 1:
        return matched[0]

    if len(matched) > 1:
        fail("multiple language handlers matched")

    if default_handler is not None:
        return default_handler

    fail("no language handler matched the source")


def require_clipboard_command() -> str:
    for name in ("clip", "clip.exe"):
        path = shutil.which(name)

        if path is not None:
            return path

    fail("clip not found")


def copy_to_clipboard(source: Path) -> None:
    clipboard = require_clipboard_command()

    with source.open("rb") as stream:
        result = subprocess.run(
            [clipboard],
            stdin=stream,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

    if result.returncode != 0:
        fail("failed to copy source to clipboard")

    print(f"[OK] copied to clipboard: {source.name}")


def main() -> None:
    argv = sys.argv[1:]

    clip = "--clip" in argv

    if clip:
        argv = [
            arg
            for arg in argv
            if arg != "--clip"
        ]

    handlers, default_handler = (
        load_language_handlers()
    )

    handler = select_handler(
        argv,
        handlers,
        default_handler,
    )

    output = handler.main(argv)

    if clip:
        if not isinstance(output, Path):
            fail(
                "language handler did not return "
                "an output source path"
            )

        copy_to_clipboard(output)


if __name__ == "__main__":
    main()
