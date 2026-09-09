from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from contest import Problem
from sites import (
    SiteError,
    SubmitResult,
)


NAME = "atcoder"
BASE_URL = "https://atcoder.jp"

TASK_HREF_PATTERN = re.compile(
    r"^/contests/([^/]+)/tasks/([^/]+)$"
)


def contest_url(
    contest_id: str,
) -> str:
    return (
        f"{BASE_URL}/contests/{contest_id}"
    )


def tasks_url(
    contest_id: str,
) -> str:
    return (
        f"{contest_url(contest_id)}/tasks"
    )


def problem_url(
    contest_id: str,
    problem_id: str,
) -> str:
    return (
        f"{contest_url(contest_id)}"
        f"/tasks/{problem_id}"
    )


def fetch_problems(
    contest_id: str,
) -> tuple[Problem, ...]:
    url = tasks_url(contest_id)

    try:
        response = requests.get(
            url,
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise SiteError(
            f"failed to fetch contest: {url}"
        ) from error

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    problems: list[Problem] = []
    seen: set[str] = set()

    for row in soup.select("table tbody tr"):
        anchors = row.find_all(
            "a",
            href=True,
        )

        if not anchors:
            continue

        anchor = anchors[0]
        href = anchor["href"]

        if not isinstance(href, str):
            continue

        match = TASK_HREF_PATTERN.fullmatch(
            href
        )

        if match is None:
            continue

        href_contest_id = match.group(1)
        problem_id = match.group(2)

        if href_contest_id != contest_id:
            continue

        if problem_id in seen:
            continue

        label = anchor.get_text(
            strip=True
        ).lower()

        if not label:
            continue

        seen.add(problem_id)

        problems.append(
            Problem(
                label=label,
                id=problem_id,
                url=f"{BASE_URL}{href}",
            )
        )

    if not problems:
        raise SiteError(
            f"no problems found: {url}"
        )

    return tuple(problems)


def download_testcases(
    problem: Problem,
    destination: Path,
) -> None:
    oj = shutil.which("oj")

    if oj is None:
        raise SiteError(
            "oj not found"
        )

    destination = destination.resolve()

    destination.mkdir(
        parents=True,
        exist_ok=True,
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        completed = subprocess.run(
            [
                oj,
                "download",
                problem.url,
            ],
            cwd=tmp_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        if completed.returncode != 0:
            raise SiteError(
                f"failed to download testcases: "
                f"{problem.label}\n"
                f"{completed.stdout}"
            )

        _move_oj_testcases(
            tmp_path,
            destination,
        )


def _move_oj_testcases(
    source_root: Path,
    destination: Path,
) -> None:
    test_dir = source_root / "test"

    if not test_dir.is_dir():
        raise SiteError(
            "oj test directory not found"
        )

    inputs = sorted(
        test_dir.glob("sample-*.in"),
        key=_sample_number,
    )

    if not inputs:
        raise SiteError(
            "no sample testcases downloaded"
        )

    for index, input_path in enumerate(
        inputs,
        start=1,
    ):
        output_path = input_path.with_suffix(
            ".out"
        )

        if not output_path.is_file():
            raise SiteError(
                f"sample output not found: "
                f"{output_path.name}"
            )

        shutil.copyfile(
            input_path,
            destination / f"in{index}",
        )

        shutil.copyfile(
            output_path,
            destination / f"out{index}",
        )


def _sample_number(
    path: Path,
) -> int:
    match = re.fullmatch(
        r"sample-([0-9]+)\.in",
        path.name,
    )

    if match is None:
        return 10**9

    return int(match.group(1))


def submit(
    problem: Problem,
    source: Path,
) -> SubmitResult:
    oj = shutil.which("oj")

    if oj is None:
        raise SiteError(
            "oj not found"
        )

    source = source.resolve()

    if not source.is_file():
        raise SiteError(
            f"submission source not found: "
            f"{source}"
        )

    completed = subprocess.run(
        [
            oj,
            "submit",
            "--yes",
            problem.url,
            str(source),
        ]
    )

    if completed.returncode != 0:
        return SubmitResult(
            success=False,
            returncode=completed.returncode,
            message="AtCoder submission failed",
        )

    return SubmitResult(
        success=True,
        returncode=0,
        message="submitted to AtCoder",
    )