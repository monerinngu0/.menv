#!/usr/bin/env python3

from __future__ import annotations

import argparse
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


def validate_case_name(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
        ng(f"invalid case name: {name}")
        info("use only letters, numbers, '_' and '-'")
        sys.exit(1)
    return name


def next_case_name(test_dir: Path) -> str:
    index = 1
    while (test_dir / f"custom-{index}.in").exists() or (test_dir / f"custom-{index}.out").exists():
        index += 1
    return f"custom-{index}"


def read_case_block(title: str) -> str:
    print(f"Enter {title}. Finish with a line containing only a single dot (.).")
    lines: list[str] = []

    while True:
        try:
            line = input()
        except EOFError:
            break

        if line == ".":
            break
        lines.append(line)

    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def read_case_file(path: str, *, kind: str) -> str:
    case_path = Path(path)
    if not case_path.is_file():
        ng(f"{kind} file not found: {case_path}")
        sys.exit(1)
    return case_path.read_text(encoding="utf-8")


def contest_test_dir(problem: str) -> Path:
    root = find_contest_root()
    if root is None:
        ng(".contest not found")
        sys.exit(1)

    test_dir = root / problem
    if not test_dir.is_dir():
        ng(f"test directory not found: {test_dir}")
        print("Run: knew <contest> --manual --problems <problem...>")
        sys.exit(1)
    return test_dir


def add_case(
    problem: str,
    case_name: str | None,
    *,
    input_file: str | None,
    output_file: str | None,
    force: bool,
) -> None:
    test_dir = contest_test_dir(problem)
    name = validate_case_name(case_name or next_case_name(test_dir))
    in_path = test_dir / f"{name}.in"
    out_path = test_dir / f"{name}.out"

    if not force and (in_path.exists() or out_path.exists()):
        ng(f"test case already exists: {name}")
        info("use --force to overwrite it")
        sys.exit(1)

    input_text = (
        read_case_file(input_file, kind="input")
        if input_file
        else read_case_block("input")
    )
    output_text = (
        read_case_file(output_file, kind="output")
        if output_file
        else read_case_block("expected output")
    )

    in_path.write_text(input_text, encoding="utf-8")
    out_path.write_text(output_text, encoding="utf-8")
    ok(f"added test case: {name}")
    info(f"input: {in_path}")
    info(f"output: {out_path}")


def list_cases(problem: str) -> None:
    test_dir = contest_test_dir(problem)
    names = sorted(path.stem for path in test_dir.glob("*.in"))

    if not names:
        info("no test cases")
        return

    for name in names:
        output = test_dir / f"{name}.out"
        state = "ok" if output.exists() else "missing .out"
        print(f"{name}	{state}")


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
    parser = argparse.ArgumentParser(prog="ktest")
    parser.add_argument("problem", help="problem label, e.g. a")
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--add-case",
        nargs="?",
        const="",
        metavar="NAME",
        help="add an interactive or file-based custom test case",
    )
    action.add_argument("--list-cases", action="store_true", help="list test cases")
    parser.add_argument("--input-file", help="read custom test input from a file")
    parser.add_argument("--output-file", help="read expected output from a file")
    parser.add_argument("-f", "--force", action="store_true", help="overwrite a custom case")
    args = parser.parse_args()

    if args.add_case is None and (args.input_file or args.output_file or args.force):
        parser.error("--input-file, --output-file, and --force require --add-case")

    if args.add_case is not None:
        add_case(
            args.problem,
            args.add_case or None,
            input_file=args.input_file,
            output_file=args.output_file,
            force=args.force,
        )
    elif args.list_cases:
        list_cases(args.problem)
    else:
        test_problem(args.problem)


if __name__ == "__main__":
    main()  