#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import time
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

from common import info, ng, ok, warn  # noqa: E402


LANGUAGE_DIR = Path(
    os.environ.get(
        "KTEST_LANGUAGE_DIR",
        Path(__file__).resolve().parent
        / "ktest_languages",
    )
)

KSUB_UNAVAILABLE = 69


def require_command(name: str) -> str:
    path = shutil.which(name)

    if path is None:
        ng(f"{name} not found")
        sys.exit(1)

    return path


def require_clipboard_command() -> str:
    for name in ("clip", "clip.exe"):
        path = shutil.which(name)

        if path is not None:
            return path

    ng("clip not found")
    sys.exit(1)


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
        ng("failed to copy source to clipboard")

        if result.stdout:
            print()
            print(
                result.stdout.decode(errors="replace"),
                end="",
            )

        sys.exit(result.returncode)

    ok(f"copied to clipboard: {source.name}")


def find_contest_root(
    start: Path | None = None,
) -> Path | None:
    current = (start or Path.cwd()).resolve()

    while True:
        if (current / ".contest").exists():
            return current

        if current.parent == current:
            return None

        current = current.parent


def load_language_module(path: Path) -> ModuleType:
    module_name = f"ktest_language_{path.stem}"
    spec = importlib.util.spec_from_file_location(
        module_name,
        path,
    )

    if spec is None or spec.loader is None:
        ng(f"failed to load language module: {path}")
        sys.exit(1)

    module = importlib.util.module_from_spec(spec)

    try:
        spec.loader.exec_module(module)
    except Exception as error:
        ng(f"failed to load language module: {path}")
        print(error, file=sys.stderr)
        sys.exit(1)

    return module


def load_language_handlers(
    directory: Path = LANGUAGE_DIR,
) -> dict[str, ModuleType]:
    if not directory.is_dir():
        ng(f"language directory not found: {directory}")
        sys.exit(1)

    handlers: dict[str, ModuleType] = {}

    for path in sorted(directory.glob("*.py")):
        if path.name.startswith("_"):
            continue

        module = load_language_module(path)
        extensions = getattr(
            module,
            "EXTENSIONS",
            None,
        )
        prepare = getattr(module, "prepare", None)

        if not isinstance(extensions, (set, tuple, list)):
            ng(f"EXTENSIONS not found: {path}")
            sys.exit(1)

        if not callable(prepare):
            ng(f"prepare() not found: {path}")
            sys.exit(1)

        for extension in extensions:
            if (
                not isinstance(extension, str)
                or not extension.startswith(".")
            ):
                ng(f"invalid extension in {path}: {extension}")
                sys.exit(1)

            if extension in handlers:
                ng(
                    "duplicate language handler for "
                    f"{extension}: {path}"
                )
                sys.exit(1)

            handlers[extension] = module

    if not handlers:
        ng(f"no language handlers found: {directory}")
        sys.exit(1)

    return handlers


def find_source(
    root: Path,
    problem: str,
    extensions: set[str],
) -> Path | None:
    bases = [
        root / problem,
        root / problem / "main",
        root / problem / problem,
    ]

    candidates = [
        base.with_suffix(extension)
        for base in bases
        for extension in sorted(extensions)
    ]
    found = [
        path
        for path in candidates
        if path.is_file()
    ]

    if not found:
        return None

    if len(found) > 1:
        ng(f"multiple source files found for problem: {problem}")

        for path in found:
            print(f"  {path.relative_to(root)}", file=sys.stderr)

        sys.exit(1)

    return found[0]


def contest_test_dir(
    root: Path,
    problem: str,
) -> Path:
    test_dir = root / problem

    if not test_dir.is_dir():
        ng(f"test directory not found: {test_dir}")
        sys.exit(1)

    return test_dir


def testcase_number(path: Path) -> int | None:
    match = re.fullmatch(
        r"in([1-9][0-9]*)",
        path.name,
    )

    if match is None:
        return None

    return int(match.group(1))


def find_testcases(
    test_dir: Path,
) -> list[tuple[int, Path, Path]]:
    cases: list[tuple[int, Path, Path]] = []

    for path in test_dir.iterdir():
        number = testcase_number(path)

        if number is None:
            continue

        cases.append(
            (
                number,
                path,
                test_dir / f"out{number}",
            )
        )

    cases.sort(key=lambda case: case[0])
    return cases


def list_cases(
    root: Path,
    problem: str,
) -> None:
    test_dir = contest_test_dir(root, problem)
    cases = find_testcases(test_dir)

    if not cases:
        info("no test cases")
        return

    for number, _, out_path in cases:
        state = (
            "ok"
            if out_path.is_file()
            else "missing output"
        )
        print(f"{number}\t{state}")


def normalize_output(text: str) -> str:
    text = text.replace("\r\n", "\n").replace(
        "\r",
        "\n",
    )
    lines = text.split("\n")

    while lines and lines[-1].strip() == "":
        lines.pop()

    return "\n".join(
        line.rstrip(" \t")
        for line in lines
    )


def print_block(title: str, text: str) -> None:
    print(f"--- {title} ---")

    if text:
        print(text, end="")

        if not text.endswith("\n"):
            print()

    print(f"--- end {title} ---")


def run_case(
    command: list[str],
    *,
    number: int,
    in_path: Path,
    out_path: Path,
) -> bool:
    input_text = in_path.read_text(
        encoding="utf-8",
    )
    expected = out_path.read_text(
        encoding="utf-8",
    )

    start = time.perf_counter()
    result = subprocess.run(
        command,
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    elapsed_ms = (
        time.perf_counter() - start
    ) * 1000

    if result.returncode != 0:
        ng(
            f"case {number}: RE "
            f"(exit {result.returncode}, "
            f"{elapsed_ms:.1f} ms)"
        )

        if result.stderr:
            print()
            print_block("stderr", result.stderr)

        return False

    actual_normalized = normalize_output(
        result.stdout
    )
    expected_normalized = normalize_output(
        expected
    )

    if actual_normalized == expected_normalized:
        ok(f"case {number}: AC ({elapsed_ms:.1f} ms)")
        return True

    ng(f"case {number}: WA ({elapsed_ms:.1f} ms)")
    print()
    print_block("expected", expected)
    print_block("actual", result.stdout)

    if result.stderr:
        print_block("stderr", result.stderr)

    return False


def run_testcases(
    command: list[str],
    *,
    test_dir: Path,
) -> None:
    cases = find_testcases(test_dir)

    if not cases:
        ng(f"no test cases found: {test_dir}")
        info("expected files: in1/out1, in2/out2, ...")
        sys.exit(1)

    missing = [
        number
        for number, _, out_path in cases
        if not out_path.is_file()
    ]

    if missing:
        for number in missing:
            ng(f"missing expected output: out{number}")

        sys.exit(1)

    passed = 0

    for number, in_path, out_path in cases:
        if run_case(
            command,
            number=number,
            in_path=in_path,
            out_path=out_path,
        ):
            passed += 1

    total = len(cases)
    print()

    if passed != total:
        ng(f"tests failed ({passed}/{total})")
        sys.exit(1)

    ok(f"all tests passed ({passed}/{total})")


def run_ksub(
    root: Path,
    problem: str,
    submission_source: Path,
) -> None:
    ksub = require_command("ksub")
    info(
        "passing tested source to ksub: "
        f"{submission_source}"
    )
    sys.stdout.flush()
    sys.stderr.flush()

    result = subprocess.run(
        [
            ksub,
            problem,
            "--source",
            str(submission_source),
        ],
        cwd=root,
    )

    if result.returncode == 0:
        return

    if result.returncode == KSUB_UNAVAILABLE:
        warn(
            "ksub could not submit; "
            "copying the tested source instead"
        )
        copy_to_clipboard(submission_source)
        return

    ng(f"ksub failed (exit {result.returncode})")
    sys.exit(result.returncode)


def test_problem(
    problem: str,
    *,
    no_build: bool,
    no_submit: bool,
    output_name: str,
) -> None:
    root = find_contest_root()

    if root is None:
        ng(".contest not found")
        sys.exit(1)

    test_dir = contest_test_dir(root, problem)
    handlers = load_language_handlers()
    source = find_source(
        root,
        problem,
        set(handlers),
    )

    if source is None:
        ng(f"source not found for problem: {problem}")
        sys.exit(1)

    handler = handlers[source.suffix]
    build_dir = root / ".build" / problem
    prepared = handler.prepare(
        source,
        build_dir,
        no_build=no_build,
        output_name=output_name,
    )

    if (
        not isinstance(prepared, tuple)
        or len(prepared) != 2
    ):
        ng(
            "language prepare() must return "
            "(command, submission_source)"
        )
        sys.exit(1)

    command, submission_source = prepared

    if not isinstance(command, list) or not command:
        ng("language prepare() returned an invalid command")
        sys.exit(1)

    submission_source = Path(
        submission_source
    ).resolve()

    if not submission_source.is_file():
        ng(
            "submission source not found: "
            f"{submission_source}"
        )
        sys.exit(1)

    info(f"running tests: {problem}")
    run_testcases(
        command,
        test_dir=test_dir,
    )

    if no_submit:
        return

    run_ksub(
        root,
        problem,
        submission_source,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ktest",
        description=(
            "Build, test, and hand a competitive "
            "programming solution to ksub."
        ),
    )
    parser.add_argument(
        "problem",
        help="problem label, e.g. a, ex, or f2",
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        help=(
            "reuse language-specific build artifacts "
            "when supported"
        ),
    )
    parser.add_argument(
        "--no-submit",
        action="store_true",
        help="stop after all sample cases pass",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="sol.cpp",
        metavar="FILE",
        help=(
            "language-specific submission output name "
            "(C++ default: sol.cpp)"
        ),
    )
    parser.add_argument(
        "--list-cases",
        action="store_true",
        help="list sample cases without building",
    )

    args = parser.parse_args()
    root = find_contest_root()

    if root is None:
        ng(".contest not found")
        sys.exit(1)

    if args.list_cases:
        list_cases(root, args.problem)
        return

    test_problem(
        args.problem,
        no_build=args.no_build,
        no_submit=args.no_submit,
        output_name=args.output,
    )


if __name__ == "__main__":
    main()