# sites/base.py

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Task:
    label: str
    task_id: str
    url: str


@dataclass(frozen=True)
class Problem:
    contest_id: str
    task_id: str
    url: str


class Site(Protocol):
    name: str

    def contest_url(self, contest_id: str) -> str:
        ...

    def fetch_tasks(
        self,
        contest_id: str,
    ) -> list[Task]:
        ...

    def parse_problem(
        self,
        value: str,
    ) -> Problem:
        ...

    def download_samples(
        self,
        task_url: str,
        directory: Path,
    ) -> None:
        ...