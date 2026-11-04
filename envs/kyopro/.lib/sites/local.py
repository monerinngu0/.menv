from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from contest import (
    CONTEST_FILE,
    CONTEST_VERSION,
    Contest,
    Problem,
    save_contest,
)
from sites import (
    SiteError,
    SubmissionUnavailable,
    SubmitResult,
)


NAME = "local"


def _validate_name(name: str) -> None:
    if (
        not name.strip()
        or name in {".", ".."}
        or any(char in name for char in ("/", "\\", "\0"))
    ):
        raise SiteError(
            f"invalid local name: {name!r}"
        )


def create_contest(
    contest_id: str,
    *,
    destination: Path,
    labels: Sequence[str],
) -> Path:
    _validate_name(contest_id)

    if not labels:
        raise SiteError("at least one problem is required")

    seen: set[str] = set()
    problems: list[Problem] = []
    url = f"local://{contest_id}"

    for label in labels:
        _validate_name(label)

        if label in {CONTEST_FILE, ".build"}:
            raise SiteError(
                f"reserved problem label: {label}"
            )

        if label in seen:
            raise SiteError(
                f"duplicate problem label: {label}"
            )

        seen.add(label)
        problems.append(
            Problem(
                label=label,
                id=label,
                url=f"{url}/{label}",
            )
        )

    root = destination.expanduser().resolve() / contest_id

    if root.exists() or root.is_symlink():
        raise SiteError(
            f"destination already exists: {root}"
        )

    root.mkdir(parents=True, exist_ok=False)

    save_contest(
        Contest(
            root=root,
            version=CONTEST_VERSION,
            site=NAME,
            id=contest_id,
            url=url,
            problems=tuple(problems),
        )
    )

    for problem in problems:
        (root / problem.label).mkdir()

    return root


def submit(
    problem: Problem,
    source: Path,
    *,
    language: str | None = None,
) -> SubmitResult:
    raise SubmissionUnavailable(
        "local contest does not support submission"
    )
