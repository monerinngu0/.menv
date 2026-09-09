from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from languages import get_language
from testcase import (
    TestResult,
    TestcaseError,
    load_testcases,
    run_testcases,
)


class TestingError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class TestRun:
    source: Path
    test_dir: Path
    executable: Path
    results: tuple[TestResult, ...]

    @property
    def success(self) -> bool:
        return all(
            result.success
            for result in self.results
        )

    @property
    def passed(self) -> int:
        return sum(
            result.success
            for result in self.results
        )

    @property
    def total(self) -> int:
        return len(self.results)


def compile_source(
    source: Path,
    executable: Path,
    *,
    include_dirs: tuple[Path, ...] = (),
) -> tuple[str, ...]:
    source = source.resolve()
    executable = executable.resolve()

    language = get_language(source)

    executable.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        built = language.compile(
            source,
            executable,
            include_dirs=include_dirs,
        )
    except Exception as error:
        raise TestingError(
            f"compile failed: {source}"
        ) from error

    return language.run_command(
        built
    )


def test_source(
    source: Path,
    test_dir: Path,
    executable: Path,
    *,
    include_dirs: tuple[Path, ...] = (),
    timeout: float | None = 2.0,
    cwd: Path | None = None,
) -> TestRun:
    source = source.resolve()
    test_dir = test_dir.resolve()
    executable = executable.resolve()

    if not source.is_file():
        raise TestingError(
            f"source not found: {source}"
        )

    if not test_dir.is_dir():
        raise TestingError(
            f"test directory not found: {test_dir}"
        )

    command = compile_source(
        source,
        executable,
        include_dirs=include_dirs,
    )

    try:
        cases = load_testcases(
            test_dir
        )
    except TestcaseError:
        raise

    results = run_testcases(
        command,
        cases,
        timeout=timeout,
        cwd=cwd or source.parent,
    )

    return TestRun(
        source=source,
        test_dir=test_dir,
        executable=executable,
        results=results,
    )