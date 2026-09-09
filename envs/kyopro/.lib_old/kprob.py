#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

MENV_ROOT = Path(os.environ.get("MENV_ROOT", Path.home() / ".menv"))
KYOPRO_ROOT = MENV_ROOT / "envs" / "kyopro"

sys.path.insert(0, str(MENV_ROOT / ".lib"))
sys.path.insert(0, str(KYOPRO_ROOT / ".lib"))

from common import info, ng, ok  # noqa: E402
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


def ensure_new_directory(
    path: Path,
) -> None:
    if path.exists():
        fail(
            f"directory already exists: "
            f"{path}"
        )

    if path.parent != Path.cwd().resolve():
        fail(
            "--directory must be a directory "
            "name, not a path"
        )


def write_metadata(
    root: Path,
    *,
    directory_name: str,
    site_name: str,
    contest_id: str,
    contest_url: str,
    task_id: str,
    task_url: str,
) -> None:
    # ktest / kdel から1つの作業単位として扱う。
    (root / ".contest").write_text(
        directory_name + "\n",
        encoding="utf-8",
    )

    (root / ".site").write_text(
        site_name + "\n",
        encoding="utf-8",
    )

    (root / ".contest-url").write_text(
        contest_url + "\n",
        encoding="utf-8",
    )

    # kprob 固有。
    (root / ".problem").write_text(
        task_id + "\n",
        encoding="utf-8",
    )

    (root / ".problem-url").write_text(
        task_url + "\n",
        encoding="utf-8",
    )

    # ローカル問題名は main。
    (root / ".tasks.tsv").write_text(
        f"main\t{task_id}\t{task_url}\n",
        encoding="utf-8",
    )


def create_problem(
    problem_value: str,
    *,
    directory: str | None,
    site_name: str,
) -> None:
    try:
        site = get_site(site_name)
    except ValueError as e:
        fail(str(e))

    problem = site.parse_problem(
        problem_value,
    )

    directory_name = validate_name(
        directory or problem.task_id,
        kind="directory",
    )

    root = (
        Path.cwd()
        / directory_name
    ).resolve()

    ensure_new_directory(root)

    contest_url = site.contest_url(
        problem.contest_id,
    )

    info(f"site: {site.name}")
    info(f"problem: {problem.task_id}")
    info(f"URL: {problem.url}")

    # サンプル取得失敗時に
    # 中途半端なworkspaceを残さない。
    with tempfile.TemporaryDirectory(
        prefix="kprob-",
    ) as temp_name:
        temp_root = Path(temp_name)
        temp_tests = temp_root / "main"

        site.download_samples(
            problem.url,
            temp_tests,
        )

        created = False

        try:
            root.mkdir()
            created = True

            shutil.copytree(
                temp_tests,
                root / "main",
            )

            write_metadata(
                root,
                directory_name=directory_name,
                site_name=site.name,
                contest_id=problem.contest_id,
                contest_url=contest_url,
                task_id=problem.task_id,
                task_url=problem.url,
            )

        except Exception:
            if created:
                shutil.rmtree(
                    root,
                    ignore_errors=True,
                )

            raise

    ok(f"created: {directory_name}")
    info(
        f"run: cd {directory_name} "
        "&& ktest main"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="kprob",
        description=(
            "Create a workspace "
            "for one competitive programming problem."
        ),
    )

    parser.add_argument(
        "problem",
        help="problem ID or URL",
    )

    parser.add_argument(
        "--site",
        default="atcoder",
        help="problem site (default: atcoder)",
    )

    parser.add_argument(
        "-d",
        "--directory",
        metavar="NAME",
        help=(
            "workspace directory name "
            "(default: problem ID)"
        ),
    )

    args = parser.parse_args()

    create_problem(
        args.problem,
        directory=args.directory,
        site_name=args.site,
    )


if __name__ == "__main__":
    main()