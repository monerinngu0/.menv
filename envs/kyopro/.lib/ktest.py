from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from contest import (
    ContestError,
    find_contest_root,
    load_contest,
)
from languages import (
    LanguageError,
    find_source,
    get_language,
)
from testcase import (
    TestResult,
    TestStatus,
    TestcaseError,
    contest_test_dir,
    standalone_test_dir,
)
from testing import (
    TestingError,
    test_source,
)


MENV_ROOT = Path(
    os.environ.get(
        "MENV_ROOT",
        Path.home() / ".menv",
    )
)

sys.path.insert(
    0,
    str(MENV_ROOT / ".lib"),
)

from common import ng, ok  # noqa: E402


class KtestError(Exception):
    pass


def normalize_include_dirs(
    paths: list[Path],
) -> tuple[Path, ...]:
    result: list[Path] = []

    for path in paths:
        path = path.expanduser().resolve()

        if not path.is_dir():
            raise KtestError(
                f"include directory not found: {path}"
            )

        result.append(path)

    return tuple(result)


def resolve_contest_target(
    root: Path,
    problem: str | None,
) -> tuple[Path, Path, Path]:
    if problem is None:
        raise KtestError(
            "problem label is required in contest mode"
        )

    contest = load_contest(root)

    # .contest 内に存在する問題か確認
    contest.problem(problem)

    source = find_source(
        root / problem
    )

    test_dir = contest_test_dir(
        root,
        problem,
    )

    executable = (
        root
        / ".build"
        / problem
        / "run"
    )

    return (
        source,
        test_dir,
        executable,
    )


def resolve_standalone_target(
    argument: str | None,
) -> tuple[Path, Path, Path]:
    if argument is None:
        source = (
            Path.cwd()
            / "main.cpp"
        )
    else:
        source = Path(argument)

    source = source.expanduser().resolve()

    if not source.is_file():
        raise KtestError(
            f"source not found: {source}"
        )

    # 対応言語か確認
    get_language(source)

    test_dir = standalone_test_dir(
        source
    )

    executable = (
        source.parent
        / ".build"
        / source.stem
        / "run"
    )

    return (
        source,
        test_dir,
        executable,
    )


def resolve_target(
    argument: str | None,
) -> tuple[Path, Path, Path]:
    root = find_contest_root()

    if root is not None:
        return resolve_contest_target(
            root,
            argument,
        )

    return resolve_standalone_target(
        argument
    )


def print_block(
    title: str,
    text: str,
) -> None:
    print(f"--- {title} ---")

    if text:
        print(
            text,
            end="" if text.endswith("\n") else "\n",
        )

    print(f"--- end {title} ---")


def print_result(
    result: TestResult,
) -> None:
    number = result.case.number

    if result.status is TestStatus.AC:
        ok(
            f"case {number}: "
            f"AC ({result.elapsed_ms:.1f} ms)"
        )
        return

    ng(
        f"case {number}: "
        f"{result.status.value} "
        f"({result.elapsed_ms:.1f} ms)"
    )

    if result.status is TestStatus.WA:
        expected = (
            result.case.output_path.read_text(
                encoding="utf-8"
            )
        )

        print_block(
            "expected",
            expected,
        )
        print_block(
            "actual",
            result.stdout,
        )

    elif result.stdout:
        print_block(
            "stdout",
            result.stdout,
        )

    if result.stderr:
        print_block(
            "stderr",
            result.stderr,
        )


def run(
    target: str | None,
    *,
    include_dirs: tuple[Path, ...],
    timeout: float,
) -> bool:
    (
        source,
        test_dir,
        executable,
    ) = resolve_target(target)

    print(f"source: {source}")
    print(f"tests:  {test_dir}")
    print()

    test_run = test_source(
        source,
        test_dir,
        executable,
        include_dirs=include_dirs,
        timeout=timeout,
        cwd=source.parent,
    )

    for result in test_run.results:
        print_result(result)

    print()

    if test_run.success:
        ok(
            f"all tests passed "
            f"({test_run.passed}/{test_run.total})"
        )
        return True

    ng(
        f"tests failed "
        f"({test_run.passed}/{test_run.total})"
    )

    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ktest",
        description="Compile and run local test cases.",
    )

    parser.add_argument(
        "target",
        nargs="?",
        help=(
            "problem label in contest mode, "
            "source file in standalone mode "
            "(default: main.cpp)"
        ),
    )

    parser.add_argument(
        "-I",
        "--include-dir",
        action="append",
        type=Path,
        default=[],
        metavar="DIR",
        help="add a C++ include directory",
    )

    parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=2.0,
        metavar="SEC",
        help="timeout per test case (default: 2.0)",
    )

    args = parser.parse_args()

    try:
        include_dirs = normalize_include_dirs(
            args.include_dir
        )

        success = run(
            args.target,
            include_dirs=include_dirs,
            timeout=args.timeout,
        )

    except (
        ContestError,
        KtestError,
        LanguageError,
        TestcaseError,
        TestingError,
    ) as error:
        ng(str(error))
        sys.exit(1)

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()