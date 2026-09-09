#!/usr/bin/env python3

import argparse
import os
import shutil
import sys
import tempfile
import subprocess
from pathlib import Path


MENV_ROOT = Path(os.environ.get("MENV_ROOT", Path.home() / ".menv"))
KYOPRO_ROOT = MENV_ROOT / "envs" / "kyopro"

sys.path.insert(0, str(MENV_ROOT / ".lib"))

from common import info, ng, ok, run_quiet


PAHCER_STUDIO_URL = "https://github.com/yunix-kyopro/pahcer-studio.git"


def fail(message: str) -> None:
    ng(message)
    sys.exit(1)


def validate_name(name: str) -> str:
    if name in {"", ".", ".."} or Path(name).name != name:
        fail(f"invalid contest name: {name}")
    return name


def require_command(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        fail(f"{name} not found")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="kahc",
        description="Create a C++ AHC project using pahcer and pahcer-studio.",
    )
    parser.add_argument("contest", help="contest name and directory, e.g. ahc070")
    parser.add_argument(
        "-o",
        "--objective",
        required=True,
        choices=("max", "min"),
        help="score objective",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="initialize an interactive problem",
    )
    args = parser.parse_args()

    contest = validate_name(args.contest)

    pahcer = require_command("pahcer")
    git = require_command("git")
    yarn = require_command("yarn")

    info("checking yarn")
    result = subprocess.run([yarn, "--version"])
    if result.returncode != 0:
        fail("failed to initialize yarn")

    template = KYOPRO_ROOT / ".template" / "main.cpp"
    if not template.is_file():
        fail(f"template not found: {template}")

    contest_dir = Path.cwd() / contest
    if contest_dir.exists():
        fail(f"directory already exists: {contest_dir}")

    info(f"creating AHC project: {contest}")
    info(f"objective: {args.objective}")
    info(f"interactive: {args.interactive}")

    # 途中で失敗した場合に、不完全なcontest directoryを残さない。
    with tempfile.TemporaryDirectory(
        prefix=f".{contest}-",
        dir=Path.cwd(),
    ) as temporary:
        project = Path(temporary)

        shutil.copyfile(template, project / "main.cpp")
        ok("created: main.cpp")

        init_command = [
            pahcer,
            "init",
            "-p",
            contest,
            "-o",
            args.objective,
            "-l",
            "cpp",
        ]
        if args.interactive:
            init_command.append("-i")

        if not run_quiet(
            "initializing pahcer",
            init_command,
            cwd=project,
        ):
            fail("pahcer init failed")

        if not run_quiet(
            "cloning pahcer-studio",
            [
                git,
                "clone",
                "--depth",
                "1",
                PAHCER_STUDIO_URL,
                "pahcer-studio",
            ],
            cwd=project,
        ):
            fail("failed to clone pahcer-studio")

        info("installing pahcer-studio")

        result = subprocess.run(
            [yarn, "install", "--frozen-lockfile"],
            cwd=project / "pahcer-studio",
        )

        if result.returncode != 0:
            fail("failed to install pahcer-studio")

        ok("installed pahcer-studio")

        project.rename(contest_dir)

    ok(f"created: {contest_dir}")
    info(f"put the official tools directory in: {contest_dir / 'tools'}")
    info(f"start studio: cd {contest}/pahcer-studio && yarn start")


if __name__ == "__main__":
    main()