from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import requests

from contest import Problem
from sites import (
    SiteError,
    SubmissionUnavailable,
    SubmitResult,
)

from submission import SubmissionLanguage


NAME = "codeforces"
BASE_URL = "https://codeforces.com"
API_BASE_URL = f"{BASE_URL}/api"


def contest_url(
    contest_id: str,
) -> str:
    return (
        f"{BASE_URL}/contest/{contest_id}"
    )


def problem_url(
    contest_id: str,
    problem_id: str,
) -> str:
    return (
        f"{contest_url(contest_id)}"
        f"/problem/{problem_id}"
    )


def fetch_problems(
    contest_id: str,
) -> tuple[Problem, ...]:
    url = (
        f"{API_BASE_URL}/contest.standings"
    )

    try:
        response = requests.get(
            url,
            params={
                "contestId": contest_id,
            },
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise SiteError(
            f"failed to fetch contest: "
            f"{contest_url(contest_id)}"
        ) from error

    try:
        data = response.json()
    except ValueError as error:
        raise SiteError(
            "invalid Codeforces API response"
        ) from error

    if not isinstance(data, dict):
        raise SiteError(
            "invalid Codeforces API response"
        )

    if data.get("status") != "OK":
        comment = data.get(
            "comment",
            "unknown error",
        )

        raise SiteError(
            f"Codeforces API error: {comment}"
        )

    result = data.get("result")

    if not isinstance(result, dict):
        raise SiteError(
            "invalid Codeforces API result"
        )

    raw_problems = result.get(
        "problems",
        [],
    )

    if not isinstance(raw_problems, list):
        raise SiteError(
            "invalid Codeforces problem list"
        )

    problems: list[Problem] = []

    for raw in raw_problems:
        if not isinstance(raw, dict):
            continue

        problem_id = raw.get("index")

        if (
            not isinstance(problem_id, str)
            or not problem_id
        ):
            continue

        problems.append(
            Problem(
                label=problem_id.lower(),
                id=problem_id,
                url=problem_url(
                    contest_id,
                    problem_id,
                ),
            )
        )

    if not problems:
        raise SiteError(
            f"no problems found: "
            f"{contest_url(contest_id)}"
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
    *,
    language: SubmissionLanguage | None = None,
) -> SubmitResult:
    raise SubmissionUnavailable(
        "Codeforces automatic submission "
        "is not implemented yet"
    )