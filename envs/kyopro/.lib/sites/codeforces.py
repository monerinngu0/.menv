from __future__ import annotations

import re
import shutil
import sys
import json
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from common import ng, run_quiet

from .base import Problem, Task


CODEFORCES_HOSTS = {
    "codeforces.com",
    "www.codeforces.com",
}

CONTEST_PATTERN = re.compile(r"[0-9]+")
INDEX_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9]*")


def fail(message: str) -> None:
    ng(message)
    sys.exit(1)


def require_command(name: str) -> str:
    path = shutil.which(name)

    if path is None:
        fail(f"{name} not found")

    return path


def validate_contest_id(value: str) -> str:
    if not CONTEST_PATTERN.fullmatch(value):
        fail(f"invalid Codeforces contest ID: {value}")

    return value


def validate_index(value: str) -> str:
    if not INDEX_PATTERN.fullmatch(value):
        fail(f"invalid Codeforces problem index: {value}")

    return value.upper()


def normalize_testcases(directory: Path) -> None:
    for path in directory.iterdir():
        match = re.fullmatch(
            r"sample-(\d+)\.(in|out)",
            path.name,
        )

        if match is None:
            continue

        number, kind = match.groups()

        if kind == "in":
            new_name = f"in{number}"
        else:
            new_name = f"out{number}"

        new_path = directory / new_name

        if new_path.exists():
            fail(
                f"test case already exists: {new_path}"
            )

        path.rename(new_path)


class CodeforcesSite:
    name = "codeforces"

    def contest_url(
        self,
        contest_id: str,
    ) -> str:
        contest_id = validate_contest_id(
            contest_id,
        )

        return (
            "https://codeforces.com/"
            f"contest/{contest_id}"
        )

    def fetch_tasks(
        self,
        contest_id: str,
    ) -> list[Task]:
        contest_id = validate_contest_id(
            contest_id,
        )

        api_url = (
            "https://codeforces.com/api/"
            "contest.standings"
            f"?contestId={contest_id}"
        )

        try:
            request = urllib.request.Request(
                api_url,
                headers={
                    "User-Agent": "menv-kyopro/1.0",
                },
            )

            with urllib.request.urlopen(
                request,
                timeout=15,
            ) as response:
                data = json.load(response)

        except Exception as e:
            fail(
                f"failed to fetch contest: {e}"
            )

        if data.get("status") != "OK":
            fail(
                "Codeforces API error: "
                f"{data.get('comment', 'unknown error')}"
            )

        problems = data["result"]["problems"]

        tasks: list[Task] = []

        for problem in problems:
            index = problem["index"]

            task_id = f"{contest_id}{index}"

            task_url = (
                "https://codeforces.com/"
                f"contest/{contest_id}/"
                f"problem/{index}"
            )

            tasks.append(
                Task(
                    label=index,
                    task_id=task_id,
                    url=task_url,
                )
            )

        return tasks

    def parse_problem(
        self,
        value: str,
    ) -> Problem:
        value = value.strip()
        parsed = urlparse(value)

        if parsed.scheme or parsed.netloc:
            return self._parse_problem_url(
                value,
                parsed,
            )

        return self._parse_problem_id(value)

    def _parse_problem_url(
        self,
        value: str,
        parsed,
    ) -> Problem:
        if parsed.scheme not in {
            "http",
            "https",
        }:
            fail(
                f"unsupported URL scheme: "
                f"{parsed.scheme}"
            )

        if (
            parsed.netloc.lower()
            not in CODEFORCES_HOSTS
        ):
            fail(
                f"unsupported site: "
                f"{parsed.netloc}"
            )

        parts = [
            part
            for part in parsed.path.split("/")
            if part
        ]

        # /contest/2026/problem/A
        if (
            len(parts) == 4
            and parts[0] == "contest"
            and parts[2] == "problem"
        ):
            contest_id = validate_contest_id(
                parts[1]
            )

            index = validate_index(
                parts[3]
            )

            return self._make_problem(
                contest_id,
                index,
            )

        # /problemset/problem/2026/A
        if (
            len(parts) == 4
            and parts[0] == "problemset"
            and parts[1] == "problem"
        ):
            contest_id = validate_contest_id(
                parts[2]
            )

            index = validate_index(
                parts[3]
            )

            return self._make_problem(
                contest_id,
                index,
            )

        fail(
            f"invalid Codeforces problem URL: "
            f"{value}"
        )

    def _parse_problem_id(
        self,
        value: str,
    ) -> Problem:
        # 2026A
        match = re.fullmatch(
            r"([0-9]+)([A-Za-z][A-Za-z0-9]*)",
            value,
        )

        if match is not None:
            contest_id, index = match.groups()

            return self._make_problem(
                validate_contest_id(contest_id),
                validate_index(index),
            )

        # 2026/A
        match = re.fullmatch(
            r"([0-9]+)/([A-Za-z][A-Za-z0-9]*)",
            value,
        )

        if match is not None:
            contest_id, index = match.groups()

            return self._make_problem(
                validate_contest_id(contest_id),
                validate_index(index),
            )

        fail(
            "invalid Codeforces problem ID; "
            "use e.g. 2026A, 2026/A, or "
            "a full problem URL"
        )

    def _make_problem(
        self,
        contest_id: str,
        index: str,
    ) -> Problem:
        task_id = f"{contest_id}{index}"

        url = (
            "https://codeforces.com/"
            f"contest/{contest_id}/"
            f"problem/{index}"
        )

        return Problem(
            contest_id=contest_id,
            task_id=task_id,
            url=url,
        )

    def download_samples(
        self,
        task_url: str,
        directory: Path,
    ) -> None:
        oj = require_command("oj")

        downloaded = run_quiet(
            "downloading samples",
            [
                oj,
                "download",
                task_url,
                "-d",
                str(directory),
            ],
        )

        if not downloaded:
            fail("failed to download samples")

        normalize_testcases(directory)