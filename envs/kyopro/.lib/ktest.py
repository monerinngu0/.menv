#!/usr/bin/env python3

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


MENV_ROOT = Path(os.environ.get("MENV_ROOT", Path.home() / ".menv"))
KYOPRO_ROOT = MENV_ROOT / "envs" / "kyopro"

sys.path.insert(0, str(MENV_ROOT / ".lib"))
sys.path.insert(0, str(KYOPRO_ROOT / ".lib"))

from common import ok, ng, info  # noqa: E402


SOURCE_EXT_LANG = {
    ".cpp": "cpp",
    ".py": "py",
}


def command_path(name: str) -> str | None:
    return shutil.which(name)


def require_command(name: str) -> str:
    path = command_path(name)
    if path is None:
        ng(f"{name} not found")
        sys.exit(1)
    return path


def require_oj() -> str:
    return require_command("oj")


def require_gpp() -> str:
    return require_command("g++")


def require_python_runtime() -> str:
    py = os.environ.get("KYOPRO_PYTHON", "python3")
    return require_command(py)


def find_contest_root(start: Path | None = None) -> Path | None:
    cur = (start or Path.cwd()).resolve()

    while True:
        if (cur / ".contest").exists():
            return cur

        if cur.parent == cur:
            return None

        cur = cur.parent


def kyopro_find_source(root: Path, problem: str) -> Path | None:
    candidates = [
        root / f"{problem}.cpp",
        root / f"{problem}.py",
        root / problem / "main.cpp",
        root / problem / "main.py",
        root / problem / f"{problem}.cpp",
        root / problem / f"{problem}.py",
    ]

    for path in candidates:
        if path.exists():
            return path

    return None


def kyopro_source_lang(src: Path) -> str | None:
    return SOURCE_EXT_LANG.get(src.suffix)


def build_cpp(src: Path, exe: Path) -> None:
    gpp = require_gpp()

    info(f"compiling: {src.name}")

    result = subprocess.run(
        [
            gpp,
            "-std=c++23",
            "-O2",
            "-Wall",
            "-Wextra",
            "-o",
            str(exe),
            str(src),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    if result.returncode != 0:
        ng("compile failed")
        print()
        print(result.stdout, end="")
        sys.exit(result.returncode)


def make_command(src: Path, exe: Path, lang: str) -> str:
    if lang == "cpp":
        build_cpp(src, exe)
        return shlex.quote(str(exe))

    if lang == "py":
        py = require_python_runtime()
        info(f"using python runtime: {py}")
        return shlex.join([py, str(src)])

    ng(f"test is not supported for language: {lang}")
    sys.exit(1)


def print_oj_log(text: str) -> None:
    for line in text.splitlines():
        print(line)


def extract_cases(output: str) -> str:
    m = re.search(r"\[INFO\]\s+([0-9]+)\s+cases found", output)
    if m:
        return m.group(1)

    return "?"


def run_samples(oj: str, command: str, test_dir: Path) -> tuple[int, str]:
    result = subprocess.run(
        [
            oj,
            "test",
            "-c",
            command,
            "-d",
            str(test_dir),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    return result.returncode, result.stdout


def test_problem(problem: str) -> None:
    oj = require_oj()

    root = find_contest_root()
    if root is None:
        ng(".contest not found")
        sys.exit(1)

    test_dir = root / problem
    exe = root / ".build" / problem

    src = kyopro_find_source(root, problem)
    if src is None:
        ng(f"source not found: {root}/{problem}.{{cpp,py}}")
        sys.exit(1)

    lang = kyopro_source_lang(src)
    if lang is None:
        ng(f"unknown source language: {src}")
        sys.exit(1)

    if not test_dir.is_dir():
        ng(f"test directory not found: {test_dir}")
        print("Run: knew <contest>")
        sys.exit(1)

    (root / ".build").mkdir(parents=True, exist_ok=True)

    command = make_command(src, exe, lang)

    info(f"running samples: {problem}")

    status, out = run_samples(oj, command, test_dir)

    if status == 0:
        cases = extract_cases(out)
        ok(f"sample tests passed ({cases} cases)")
    else:
        ng("sample tests failed")
        print()
        print_oj_log(out)
        sys.exit(status)


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: ktest <problem>")
        sys.exit(1)

    test_problem(sys.argv[1])


if __name__ == "__main__":
    main()  