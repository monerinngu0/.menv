from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from build import (
    BuildError,
    build_submission,
)
from contest import (
    ContestError,
    find_contest_root,
    load_contest,
)
from languages import (
    LanguageError,
    find_source,
)
from sites import (
    SiteError,
    SubmissionUnavailable,
    get_site,
)
from testcase import (
    TestResult,
    TestStatus,
    TestcaseError,
    contest_test_dir,
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

from common import info, ng, ok, warn  # noqa: E402


class KsubError(Exception):
    pass


def normalize_include_dirs(
    paths: list[Path],
) -> tuple[Path, ...]:
    result: list[Path] = []

    for path in paths:
        path = path.expanduser().resolve()

        if not path.is_dir():
            raise KsubError(
                f"include directory not found: {path}"
            )

        result.append(path)

    return tuple(result)


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


def run_tests(
    root: Path,
    problem: str,
    source: Path,
    *,
    include_dirs: tuple[Path, ...],
    timeout: float,
) -> None:
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

    info(f"running tests: {problem}")

    test_run = test_source(
        source,
        test_dir,
        executable,
        include_dirs=include_dirs,
        timeout=timeout,
        cwd=root,
    )

    for result in test_run.results:
        print_result(result)

    if not test_run.success:
        raise KsubError(
            f"tests failed "
            f"({test_run.passed}/{test_run.total})"
        )

    ok(
        f"all tests passed "
        f"({test_run.passed}/{test_run.total})"
    )


def build_source(
    source: Path,
    *,
    include_dirs: tuple[Path, ...],
) -> Path:
    result = build_submission(
        source,
        include_dirs=include_dirs,
    )

    ok(
        f"built submission source: "
        f"{result.output}"
    )

    return result.output


def copy_to_clipboard(
    source: Path,
) -> bool:
    command = (
        shutil.which("clip.exe")
        or shutil.which("clip")
    )

    if command is None:
        return False

    with source.open("rb") as stream:
        completed = subprocess.run(
            [command],
            stdin=stream,
        )

    return completed.returncode == 0


def submit(
    problem_label: str,
    *,
    include_dirs: tuple[Path, ...],
    timeout: float,
    test: bool,
) -> None:
    root = find_contest_root()

    if root is None:
        raise KsubError(
            "ksub requires a contest environment"
        )

    contest = load_contest(root)

    problem = contest.problem(
        problem_label
    )

    source = find_source(
        root / problem.label
    )

    info(f"contest: {contest.id}")
    info(f"problem: {problem.label}")
    info(f"source: {source}")

    #
    # optional test
    #

    if test:
        run_tests(
            root,
            problem.label,
            source,
            include_dirs=include_dirs,
            timeout=timeout,
        )

    #
    # build
    #

    submission_source = build_source(
        source,
        include_dirs=include_dirs,
    )

    #
    # submit
    #

    site = get_site(
        contest.site
    )

    info(
        f"submitting to {contest.site}: "
        f"{problem.url}"
    )

    try:
        result = site.submit(
            problem,
            submission_source,
        )

    except SubmissionUnavailable as error:
        warn(str(error))

        if copy_to_clipboard(
            submission_source
        ):
            ok(
                "copied submission source "
                "to clipboard"
            )

        raise KsubError(
            "automatic submission unavailable"
        ) from error

    if not result.success:
        warn(result.message)

        if copy_to_clipboard(
            submission_source
        ):
            ok(
                "copied submission source "
                "to clipboard"
            )

        raise KsubError(
            "submission failed"
        )

    ok(result.message)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ksub",
        description=(
            "Build and submit "
            "a contest solution."
        ),
    )

    parser.add_argument(
        "problem",
        help="problem label, e.g. a, b, ex",
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="run local tests before submission",
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
        help=(
            "timeout per test case "
            "(used with --test, default: 2.0)"
        ),
    )

    args = parser.parse_args()

    try:
        include_dirs = normalize_include_dirs(
            args.include_dir
        )

        submit(
            args.problem,
            include_dirs=include_dirs,
            timeout=args.timeout,
            test=args.test,
        )

    except (
        BuildError,
        ContestError,
        KsubError,
        LanguageError,
        SiteError,
        TestcaseError,
        TestingError,
    ) as error:
        ng(str(error))
        sys.exit(1)


if __name__ == "__main__":
    main()