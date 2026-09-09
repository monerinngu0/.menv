from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from common import info, ng, ok


EXTENSIONS = {
    ".cpp",
}


def require_command(name: str) -> str:
    path = shutil.which(name)

    if path is None:
        ng(f"{name} not found")
        sys.exit(1)

    return path


def validate_output_name(output_name: str) -> None:
    output = Path(output_name)

    if output.name != output_name:
        ng("--output must be a file name, not a path")
        sys.exit(1)

    if output.suffix != ".cpp":
        ng("--output must have the .cpp extension")
        sys.exit(1)


def build_submission(
    source: Path,
    output: Path,
) -> None:
    kbuild = require_command("kbuild")
    info(f"building: {source.name} -> {output.name}")

    result = subprocess.run(
        [
            kbuild,
            "--no-compile",
            "-o",
            str(output),
            str(source),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    if result.returncode != 0:
        ng("build failed")

        if result.stdout:
            print()
            print(result.stdout, end="")

        sys.exit(result.returncode)

    if not output.is_file():
        ng(f"build output not found: {output}")
        sys.exit(1)

    ok(f"built: {output.name}")


def compile_submission(
    source: Path,
    executable: Path,
) -> None:
    compiler = require_command("g++")
    info(f"compiling: {source.name}")

    result = subprocess.run(
        [
            compiler,
            "-std=c++23",
            "-O2",
            "-Wall",
            "-Wextra",
            "-o",
            str(executable),
            str(source),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    if result.returncode != 0:
        ng("compile failed")

        if result.stdout:
            print()
            print(result.stdout, end="")

        sys.exit(result.returncode)

    ok(f"compiled: {executable.name}")


def prepare(
    source: Path,
    build_dir: Path,
    *,
    no_build: bool,
    output_name: str,
) -> tuple[list[str], Path]:
    validate_output_name(output_name)
    build_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    bundled_source = build_dir / output_name
    executable = (
        build_dir
        / f"{bundled_source.stem}.out"
    )

    if no_build:
        if not bundled_source.is_file():
            ng(
                "built source not found: "
                f"{bundled_source}"
            )
            info("run without --no-build first")
            sys.exit(1)

        info(
            "using existing build: "
            f"{bundled_source.name}"
        )
    else:
        build_submission(
            source,
            bundled_source,
        )

    compile_submission(
        bundled_source,
        executable,
    )

    return [str(executable)], bundled_source