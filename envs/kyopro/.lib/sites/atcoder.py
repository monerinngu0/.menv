# sites/atcoder.py

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from common import info, ng, run_quiet

from .base import Problem, Task


ATCODER_HOSTS = {
    "atcoder.jp",
    "www.atcoder.jp",
}

NAME_PATTERN = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9_-]*"
)


def fail(message: str) -> None:
    ng(message)
    sys.exit(1)


def validate_name(
    value: str,
    *,
    kind: str,
) -> str:
    if not NAME_PATTERN.fullmatch(value):
        fail(f"invalid {kind} name: {value}")

    return value


def require_command(name: str) -> str:
    path = shutil.which(name)

    if path is None:
        fail(f"{name} not found")

    return path


def require_oj_login(oj: str) -> None:
    result = subprocess.run(
        [
            oj,
            "login",
            "--check",
            "https://atcoder.jp/",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if result.returncode != 0:
        ng("AtCoder login required")
        info("run: oj login https://atcoder.jp/")
        sys.exit(1)


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
            fail(f"test case already exists: {new_path}")

        path.rename(new_path)


class AtCoderSite:
    name = "atcoder"

    def contest_url(self, contest_id: str) -> str:
        contest_id = validate_name(
            contest_id,
            kind="contest",
        )

        return (
            "https://atcoder.jp/"
            f"contests/{contest_id}"
        )

    def fetch_tasks(
        self,
        contest_id: str,
    ) -> list[Task]:
        contest_id = validate_name(
            contest_id,
            kind="contest",
        )

        url = (
            "https://atcoder.jp/"
            f"contests/{contest_id}/tasks"
        )

        try:
            html = (
                urllib.request
                .urlopen(url)
                .read()
                .decode(
                    "utf-8",
                    errors="ignore",
                )
            )
        except Exception as e:
            fail(
                f"failed to fetch tasks page: {e}"
            )

        ids: list[str] = []

        pattern = (
            rf"/contests/{re.escape(contest_id)}"
            rf"/tasks/([^\"?#]+)"
        )

        for match in re.finditer(pattern, html):
            task_id = match.group(1)

            if task_id not in ids:
                ids.append(task_id)

        tasks: list[Task] = []

        for task_id in ids:
            if task_id.startswith(
                contest_id + "_"
            ):
                label = task_id[
                    len(contest_id) + 1:
                ]
            else:
                label = task_id

            task_url = (
                "https://atcoder.jp/"
                f"contests/{contest_id}/"
                f"tasks/{task_id}"
            )

            tasks.append(
                Task(
                    label=label,
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
            if parsed.scheme not in {
                "http",
                "https",
            }:
                fail(
                    "unsupported URL scheme: "
                    f"{parsed.scheme}"
                )

            if (
                parsed.netloc.lower()
                not in ATCODER_HOSTS
            ):
                fail(
                    "unsupported site: "
                    f"{parsed.netloc}"
                )

            parts = [
                part
                for part
                in parsed.path.split("/")
                if part
            ]

            if (
                len(parts) != 4
                or parts[0] != "contests"
                or parts[2] != "tasks"
            ):
                fail(
                    "invalid AtCoder problem URL: "
                    f"{value}"
                )

            contest_id = validate_name(
                parts[1],
                kind="contest",
            )

            task_id = validate_name(
                parts[3],
                kind="problem",
            )

            url = (
                "https://atcoder.jp/"
                f"contests/{contest_id}/"
                f"tasks/{task_id}"
            )

            return Problem(
                contest_id=contest_id,
                task_id=task_id,
                url=url,
            )

        task_id = validate_name(
            value,
            kind="problem",
        )

        if "_" not in task_id:
            fail(
                "cannot infer the contest "
                "from the task ID; "
                "pass the full AtCoder "
                "problem URL"
            )

        contest_id = task_id.split(
            "_",
            1,
        )[0]

        url = (
            "https://atcoder.jp/"
            f"contests/{contest_id}/"
            f"tasks/{task_id}"
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
        require_oj_login(oj)

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