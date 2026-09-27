from __future__ import annotations

from pathlib import Path

import requests

from contest import Problem
from sites import (
    SiteError,
    SubmissionUnavailable,
    SubmitResult,
)
from submission import SubmissionLanguage
from sites.common import download_oj_testcases


NAME = "codeforces"
BASE_URL = "https://codeforces.com"
API_BASE_URL = f"{BASE_URL}/api"

SUBMISSION_AVAILABLE = False


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
    download_oj_testcases(
        problem,
        destination,
    )


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