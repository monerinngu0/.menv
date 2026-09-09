#!/usr/bin/env python3

from __future__ import annotations

import re
import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


INPUT_PATTERN = re.compile(r"in([1-9][0-9]*)")


class TestcaseError(Exception):
    pass


class TestStatus(Enum):
    AC = "AC"
    WA = "WA"
    RE = "RE"
    TLE = "TLE"


@dataclass(frozen=True, slots=True)
class TestCase:
    number: int
    input_path: Path
    output_path: Path


@dataclass(frozen=True, slots=True)
class TestResult:
    case: TestCase
    status: TestStatus
    elapsed_ms: float
    stdout: str
    stderr: str
    returncode: int | None

    @property
    def success(self) -> bool:
        return self.status is TestStatus.AC


def contest_test_dir(
    root: Path,
    problem: str,
) -> Path:
    return root.resolve() / problem


def standalone_test_dir(
    source: Path,
) -> Path:
    return source.resolve().parent


def testcase_number(path: Path) -> int | None:
    match = INPUT_PATTERN.fullmatch(path.name)

    if match is None:
        return None

    return int(match.group(1))


def load_testcases(
    test_dir: Path,
) -> tuple[TestCase, ...]:
    test_dir = test_dir.resolve()

    if not test_dir.is_dir():
        raise TestcaseError(
            f"test directory not found: {test_dir}"
        )

    cases: list[TestCase] = []

    for input_path in test_dir.iterdir():
        number = testcase_number(input_path)

        if number is None:
            continue

        output_path = test_dir / f"out{number}"

        if not output_path.is_file():
            raise TestcaseError(
                f"expected output not found: {output_path}"
            )

        cases.append(
            TestCase(
                number=number,
                input_path=input_path,
                output_path=output_path,
            )
        )

    cases.sort(
        key=lambda case: case.number
    )

    if not cases:
        raise TestcaseError(
            f"no test cases found: {test_dir}"
        )

    return tuple(cases)


def normalize_output(text: str) -> str:
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    lines = text.split("\n")

    while lines and lines[-1].strip() == "":
        lines.pop()

    return "\n".join(
        line.rstrip(" \t")
        for line in lines
    )


def compare_exact(
    actual: str,
    expected: str,
) -> bool:
    return (
        normalize_output(actual)
        == normalize_output(expected)
    )


def run_testcase(
    command: Sequence[str],
    case: TestCase,
    *,
    timeout: float | None = 2.0,
    cwd: Path | None = None,
    comparator: Callable[[str, str], bool] = compare_exact,
) -> TestResult:
    input_text = case.input_path.read_text(
        encoding="utf-8"
    )
    expected = case.output_path.read_text(
        encoding="utf-8"
    )

    start = time.perf_counter()

    try:
        completed = subprocess.run(
            list(command),
            input=input_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        elapsed_ms = (
            time.perf_counter() - start
        ) * 1000

        stdout = (
            error.stdout
            if isinstance(error.stdout, str)
            else ""
        )
        stderr = (
            error.stderr
            if isinstance(error.stderr, str)
            else ""
        )

        return TestResult(
            case=case,
            status=TestStatus.TLE,
            elapsed_ms=elapsed_ms,
            stdout=stdout,
            stderr=stderr,
            returncode=None,
        )

    elapsed_ms = (
        time.perf_counter() - start
    ) * 1000

    if completed.returncode != 0:
        status = TestStatus.RE
    elif comparator(
        completed.stdout,
        expected,
    ):
        status = TestStatus.AC
    else:
        status = TestStatus.WA

    return TestResult(
        case=case,
        status=status,
        elapsed_ms=elapsed_ms,
        stdout=completed.stdout,
        stderr=completed.stderr,
        returncode=completed.returncode,
    )


def run_testcases(
    command: Sequence[str],
    cases: Sequence[TestCase],
    *,
    timeout: float | None = 2.0,
    cwd: Path | None = None,
    comparator: Callable[[str, str], bool] = compare_exact,
) -> tuple[TestResult, ...]:
    return tuple(
        run_testcase(
            command,
            case,
            timeout=timeout,
            cwd=cwd,
            comparator=comparator,
        )
        for case in cases
    )