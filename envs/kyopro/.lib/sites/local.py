from __future__ import annotations

from pathlib import Path

from contest import Problem
from sites import (
    SubmissionUnavailable,
    SubmitResult,
)


NAME = "local"


def submit(
    problem: Problem,
    source: Path,
) -> SubmitResult:
    raise SubmissionUnavailable(
        "local contest does not support submission"
    )