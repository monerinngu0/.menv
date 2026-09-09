#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

MENV_ROOT = Path(os.environ.get("MENV_ROOT", Path.home() / ".menv"))
KYOPRO_ROOT = MENV_ROOT / "envs" / "kyopro"

sys.path.insert(0, str(MENV_ROOT / ".lib"))
sys.path.insert(0, str(KYOPRO_ROOT / ".lib"))

from common import info, ng, ok, warn  # noqa: E402
from sites import get_site  # noqa: E402


def fail(message: str) -> None:
    ng(message)
    sys.exit(1)


def validate_name(
    value: str,
    *,
    kind: str,
) -> str:
    if value in {"", ".", ".."} or Path(value).name != value:
        fail(f"invalid {kind} name: {value}")

    return value


def parse_problem_labels(
    values: list[str] | None,
) -> list[str]:
    labels: list[str] = []

    for value in values or []:
        for label in value.split(","):
            label = label.strip()

            if not label:
                continue

            validate_name(
                label,
                kind="problem",
            )

            if label not in labels:
                labels.append(label)

    return labels


def prepare_contest_dir(
    contest: str,
) -> Path:
    contest_dir = Path.cwd() / contest
    marker = contest_dir / ".contest"

    if marker.exists():
        actual = marker.read_text(
            encoding="utf-8",
        ).strip()

        if actual != contest:
            fail(
                "directory is already used by "
                f"another contest: {contest_dir}"
            )

    elif (
        contest_dir.exists()
        and any(contest_dir.iterdir())
    ):
        fail(
            "directory already exists and "
            f"is not a contest: {contest_dir}"
        )

    contest_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    marker.write_text(
        contest + "\n",
        encoding="utf-8",
    )

    return contest_dir


def create_contest(
    contest: str,
    *,
    site_name: str,
) -> None:
    try:
        site = get_site(site_name)
    except ValueError as e:
        fail(str(e))

    contest_dir = prepare_contest_dir(
        contest,
    )

    info(f"creating contest: {contest}")
    info(f"site: {site.name}")

    tasks = site.fetch_tasks(contest)

    if not tasks:
        fail("no tasks found")

    contest_url = site.contest_url(
        contest,
    )

    (contest_dir / ".site").write_text(
        site.name + "\n",
        encoding="utf-8",
    )

    (contest_dir / ".contest-url").write_text(
        contest_url + "\n",
        encoding="utf-8",
    )

    task_lines: list[str] = []

    for task in tasks:
        task_dir = contest_dir / task.label
        task_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        task_lines.append(
            f"{task.label}\t"
            f"{task.task_id}\t"
            f"{task.url}\n"
        )

        try:
            site.download_samples(
                task.url,
                task_dir,
            )
        except SystemExit:
            warn(
                f"failed to download: "
                f"{task.label}"
            )
            continue

        ok(f"downloaded: {task.label}")

    (contest_dir / ".tasks.tsv").write_text(
        "".join(task_lines),
        encoding="utf-8",
    )

    ok(f"created: {contest}")


def create_manual_contest(
    contest: str,
    *,
    labels: list[str],
    site_name: str,
    contest_url: str | None,
) -> None:
    contest_dir = prepare_contest_dir(
        contest,
    )

    (contest_dir / ".site").write_text(
        site_name + "\n",
        encoding="utf-8",
    )

    if contest_url:
        (contest_dir / ".contest-url").write_text(
            contest_url + "\n",
            encoding="utf-8",
        )

    task_lines: list[str] = []

    info(
        f"creating manual contest: "
        f"{contest}"
    )
    info(f"site: {site_name}")

    for label in labels:
        task_dir = contest_dir / label

        task_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        task_lines.append(
            f"{label}\t{label}\t\n"
        )

        ok(f"prepared: {label}")

    (contest_dir / ".tasks.tsv").write_text(
        "".join(task_lines),
        encoding="utf-8",
    )

    ok(f"created: {contest}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="knew",
        description=(
            "Create a competitive programming "
            "contest workspace."
        ),
    )

    parser.add_argument(
        "contest",
        help="contest ID / directory name",
    )

    parser.add_argument(
        "--site",
        default="atcoder",
        help="contest site (default: atcoder)",
    )

    parser.add_argument(
        "--manual",
        action="store_true",
        help="create a local contest without fetching tasks",
    )

    parser.add_argument(
        "-p",
        "--problems",
        nargs="+",
        metavar="NAME",
        help="problem labels for --manual",
    )

    parser.add_argument(
        "--url",
        help="contest URL for --manual",
    )

    args = parser.parse_args()

    contest = validate_name(
        args.contest,
        kind="contest",
    )

    if args.manual:
        labels = parse_problem_labels(
            args.problems,
        )

        if not labels:
            parser.error(
                "--manual requires "
                "--problems/-p"
            )

        create_manual_contest(
            contest,
            labels=labels,
            site_name=args.site,
            contest_url=args.url,
        )

        return

    if args.problems or args.url:
        parser.error(
            "--problems and --url "
            "require --manual"
        )

    create_contest(
        contest,
        site_name=args.site,
    )


if __name__ == "__main__":
    main()