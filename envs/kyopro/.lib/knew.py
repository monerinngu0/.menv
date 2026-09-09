from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from contest import (
    CONTEST_VERSION,
    Contest,
    ContestError,
    save_contest,
)
from sites import (
    SiteError,
    get_site,
)


MENV_ROOT = Path(
    os.environ.get(
        "MENV_ROOT",
        Path.home() / ".menv",
    )
)

KYOPRO_ROOT = (
    MENV_ROOT
    / "envs"
    / "kyopro"
)


class KnewError(Exception):
    pass


def download_testcases(
    site,
    root: Path,
    problems,
) -> None:
    for problem in problems:
        destination = (
            root
            / problem.label
        )

        site.download_testcases(
            problem,
            destination,
        )

        print(
            f"[OK] downloading samples: "
            f"{problem.label}"
        )


def create_contest(
    contest_id: str,
    *,
    destination: Path,
    download_samples: bool,
) -> Path:
    site = get_site("atcoder")

    contest_id = contest_id.strip()

    if not contest_id:
        raise KnewError(
            "contest id is empty"
        )

    root = (
        destination.expanduser().resolve()
        / contest_id
    )

    if root.exists():
        raise KnewError(
            f"destination already exists: {root}"
        )

    print(
        f"fetching contest: {contest_id}"
    )

    problems = site.fetch_problems(
        contest_id
    )

    if not problems:
        raise KnewError(
            f"no problems found: {contest_id}"
        )

    root.mkdir(
        parents=True,
        exist_ok=False,
    )

    contest = Contest(
        root=root,
        version=CONTEST_VERSION,
        site="atcoder",
        id=contest_id,
        url=site.contest_url(
            contest_id
        ),
        problems=problems,
    )

    save_contest(
        contest
    )

    if download_samples:
        download_testcases(
            site,
            root,
            problems,
        )

    return root


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="knew",
        description=(
            "Create a new competitive "
            "programming contest workspace."
        ),
    )

    parser.add_argument(
        "contest",
        help=(
            "AtCoder contest id, "
            "e.g. abc001"
        ),
    )

    parser.add_argument(
        "-d",
        "--directory",
        type=Path,
        default=Path.cwd(),
        metavar="DIR",
        help=(
            "parent directory for the contest "
            "(default: current directory)"
        ),
    )

    parser.add_argument(
        "--no-download",
        action="store_true",
        help=(
            "create the contest without "
            "downloading sample test cases"
        ),
    )

    args = parser.parse_args()

    try:
        root = create_contest(
            args.contest,
            destination=args.directory,
            download_samples=not args.no_download,
        )

    except (
        ContestError,
        KnewError,
        SiteError,
    ) as error:
        print(
            f"[ERROR] {error}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        f"[OK] created contest: {root}"
    )


if __name__ == "__main__":
    main()  