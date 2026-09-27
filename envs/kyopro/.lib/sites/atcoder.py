from __future__ import annotations

import http.cookiejar
import re
import shutil
import subprocess
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from contest import Problem
from sites import (
    SiteError,
    SubmitResult,
)

from submission import SubmissionLanguage
from sites.common import download_oj_testcases


NAME = "atcoder"
BASE_URL = "https://atcoder.jp"

SUBMISSION_AVAILABLE = True

OJ_COOKIE_PATH = (
    Path.home()
    / ".local"
    / "share"
    / "online-judge-tools"
    / "cookie.jar"
)

TASK_HREF_PATTERN = re.compile(
    r"^/contests/([^/]+)/tasks/([^/]+)$"
)


def _create_session() -> requests.Session:
    session = requests.Session()

    if not OJ_COOKIE_PATH.is_file():
        return session

    jar = http.cookiejar.LWPCookieJar(
        str(OJ_COOKIE_PATH)
    )

    try:
        jar.load(
            ignore_discard=True,
            ignore_expires=True,
        )
    except (
        OSError,
        http.cookiejar.LoadError,
    ) as error:
        raise SiteError(
            f"failed to load oj cookie: "
            f"{OJ_COOKIE_PATH}"
        ) from error

    session.cookies = jar

    return session


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
    session = _create_session()

    try:
        response = session.get(
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

    command = [
        oj,
        "submit",
        "--yes",
        "--no-open",
    ]

    if language is not None:
        command += [
            "--language",
            language.query,
        ]

    command += [
        problem.url,
        str(source),
    ]

    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
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
