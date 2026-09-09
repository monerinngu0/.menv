#!/usr/bin/env python3

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path


CONTEST_FILE = ".contest"
CONTEST_VERSION = 1


class ContestError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Problem:
    label: str
    id: str
    url: str


@dataclass(frozen=True, slots=True)
class Contest:
    root: Path
    version: int
    site: str
    id: str
    url: str
    problems: tuple[Problem, ...]

    @property
    def path(self) -> Path:
        return self.root / CONTEST_FILE

    def problem(self, label: str) -> Problem:
        for problem in self.problems:
            if problem.label == label:
                return problem

        raise ContestError(f"problem not found: {label}")

    def has_problem(self, label: str) -> bool:
        return any(
            problem.label == label
            for problem in self.problems
        )


def find_contest_root(
    start: Path | None = None,
) -> Path | None:
    current = (start or Path.cwd()).resolve()

    while True:
        if (current / CONTEST_FILE).is_file():
            return current

        if current.parent == current:
            return None

        current = current.parent


def load_contest(root: Path) -> Contest:
    root = root.resolve()
    path = root / CONTEST_FILE

    if not path.is_file():
        raise ContestError(f"{CONTEST_FILE} not found: {root}")

    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
    except tomllib.TOMLDecodeError as error:
        raise ContestError(
            f"invalid {CONTEST_FILE}: {error}"
        ) from error

    version = data.get("version")

    if version != CONTEST_VERSION:
        raise ContestError(
            f"unsupported contest version: {version}"
        )

    site = _require_string(data, "site")
    contest_id = _require_string(data, "id")
    url = _require_string(data, "url")

    raw_problems = data.get("problems", [])

    if not isinstance(raw_problems, list):
        raise ContestError("problems must be an array")

    problems: list[Problem] = []
    labels: set[str] = set()

    for index, raw in enumerate(raw_problems):
        if not isinstance(raw, dict):
            raise ContestError(
                f"problems[{index}] must be a table"
            )

        label = _require_string(
            raw,
            "label",
            context=f"problems[{index}]",
        )
        problem_id = _require_string(
            raw,
            "id",
            context=f"problems[{index}]",
        )
        problem_url = _require_string(
            raw,
            "url",
            context=f"problems[{index}]",
        )

        if label in labels:
            raise ContestError(
                f"duplicate problem label: {label}"
            )

        labels.add(label)

        problems.append(
            Problem(
                label=label,
                id=problem_id,
                url=problem_url,
            )
        )

    return Contest(
        root=root,
        version=version,
        site=site,
        id=contest_id,
        url=url,
        problems=tuple(problems),
    )


def save_contest(contest: Contest) -> None:
    path = contest.path
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    lines = [
        f"version = {contest.version}",
        f"site = {_toml_string(contest.site)}",
        f"id = {_toml_string(contest.id)}",
        f"url = {_toml_string(contest.url)}",
    ]

    for problem in contest.problems:
        lines.extend(
            [
                "",
                "[[problems]]",
                f"label = {_toml_string(problem.label)}",
                f"id = {_toml_string(problem.id)}",
                f"url = {_toml_string(problem.url)}",
            ]
        )

    text = "\n".join(lines) + "\n"

    temporary = path.with_name(
        f"{path.name}.tmp"
    )
    temporary.write_text(
        text,
        encoding="utf-8",
    )
    temporary.replace(path)


def _require_string(
    data: dict,
    key: str,
    *,
    context: str = "",
) -> str:
    value = data.get(key)

    if not isinstance(value, str) or not value:
        prefix = f"{context}." if context else ""
        raise ContestError(
            f"{prefix}{key} must be a non-empty string"
        )

    return value


def _toml_string(value: str) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
    )   