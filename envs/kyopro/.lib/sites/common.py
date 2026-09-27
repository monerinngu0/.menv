from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from contest import Problem
from sites import SiteError


def download_oj_testcases(
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