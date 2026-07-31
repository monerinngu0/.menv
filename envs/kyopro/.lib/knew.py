#!/usr/bin/env python3

import argparse
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

MENV_ROOT = Path(os.environ.get("MENV_ROOT", Path.home() / ".menv"))
KYOPRO_ROOT = MENV_ROOT / "envs" / "kyopro"

sys.path.insert(0, str(MENV_ROOT / ".lib"))
sys.path.insert(0, str(KYOPRO_ROOT / ".lib"))

from common import ok, ng, warn, info, run_quiet

from kyopro import (
    kyopro_default_lang,
    kyopro_ensure_template,
    kyopro_lang_ext,
    kyopro_template_path,
)


def validate_name(value: str, *, kind: str) -> str:
    if value in {"", ".", ".."} or Path(value).name != value:
        ng(f"invalid {kind} name: {value}")
        sys.exit(1)

    return value


def parse_problem_labels(values: list[str] | None) -> list[str]:
    labels: list[str] = []

    for value in values or []:
        for label in value.split(","):
            label = label.strip()
            if not label:
                continue
            validate_name(label, kind="problem")
            if label not in labels:
                labels.append(label)

    return labels


def command_path(name: str) -> str | None:
    return shutil.which(name)


def require_command(name: str) -> str:
    path = command_path(name)
    if path is None:
        ng(f"{name} not found")
        sys.exit(1)
    return path


def default_lang() -> str:
    # 後で .toml から読むようにできる
    return os.environ.get("KYOPRO_LANG", "cpp")


def lang_ext(lang: str) -> str:
    if lang not in LANG_EXT:
        ng(f"unknown language: {lang}")
        sys.exit(1)
    return LANG_EXT[lang]


def template_path(lang: str) -> Path:
    ext = lang_ext(lang)
    path = KYOPRO_ROOT / ".template" / f"main.{ext}"
    if not path.exists():
        ng(f"template not found: {path}")
        sys.exit(1)
    return path


def require_oj_login(oj: str) -> None:
    result = subprocess.run(
        [oj, "login", "--check", "https://atcoder.jp/"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        ng("AtCoder login required")
        info("run: oj login https://atcoder.jp/")
        sys.exit(1)


def fetch_tasks(contest: str) -> list[tuple[str, str, str]]:
    url = f"https://atcoder.jp/contests/{contest}/tasks"

    try:
        html = urllib.request.urlopen(url).read().decode("utf-8", errors="ignore")
    except Exception as e:
        ng(f"failed to fetch tasks page: {e}")
        sys.exit(1)

    ids: list[str] = []

    pattern = rf'/contests/{re.escape(contest)}/tasks/([^"?#]+)'
    for m in re.finditer(pattern, html):
        task_id = m.group(1)
        if task_id not in ids:
            ids.append(task_id)

    tasks = []
    for task_id in ids:
        if task_id.startswith(contest + "_"):
            label = task_id[len(contest) + 1:]
        else:
            label = task_id

        task_url = f"https://atcoder.jp/contests/{contest}/tasks/{task_id}"
        tasks.append((label, task_id, task_url))

    return tasks


def create_contest(contest: str) -> None:
    py = require_command("python3")
    oj = require_command("oj")
    require_oj_login(oj)

    lang = kyopro_default_lang()
    ext = kyopro_lang_ext(lang)
    kyopro_ensure_template(lang)
    template = kyopro_template_path(lang)

    tasks = fetch_tasks(contest)
    if not tasks:
        ng("failed to fetch tasks")
        sys.exit(1)

    contest_dir = Path.cwd() / contest
    contest_dir.mkdir(parents=True, exist_ok=True)

    (contest_dir / ".contest").write_text(contest + "\n", encoding="utf-8")
    (contest_dir / ".site").write_text("atcoder\n", encoding="utf-8")
    (contest_dir / ".contest-url").write_text(
        f"https://atcoder.jp/contests/{contest}\n",
        encoding="utf-8",
    )
    tasks_tsv = contest_dir / ".tasks.tsv"
    tasks_tsv.write_text("", encoding="utf-8")

    info(f"creating contest: {contest}")
    info(f"language: {lang}")
    info(f"python: {py}")

    for label, task_id, url in tasks:
        task_dir = contest_dir / label
        task_dir.mkdir(parents=True, exist_ok=True)

        source = contest_dir / f"{label}.{ext}"
        if not source.exists():
            shutil.copyfile(template, source)

        with tasks_tsv.open("a", encoding="utf-8") as f:
            f.write(f"{label}\t{task_id}\t{url}\n")

        ok_download = run_quiet(
            f"downloading: {label}",
            [oj, "download", url, "-d", str(task_dir)],
        )

        if ok_download:
            ok(f"downloaded: {label}")
        else:
            warn(f"failed to download: {label}")

    info(f"created: {contest}")


def prepare_contest_dir(contest: str) -> Path:
    contest_dir = Path.cwd() / contest
    marker = contest_dir / ".contest"

    if marker.exists():
        actual = marker.read_text(encoding="utf-8").strip()
        if actual != contest:
            ng(f"directory is already used by another contest: {contest_dir}")
            sys.exit(1)
    elif contest_dir.exists() and any(contest_dir.iterdir()):
        ng(f"directory already exists and is not a contest: {contest_dir}")
        sys.exit(1)

    contest_dir.mkdir(parents=True, exist_ok=True)
    marker.write_text(contest + "\n", encoding="utf-8")
    return contest_dir


def create_manual_contest(
    contest: str,
    *,
    site: str,
    labels: list[str],
    contest_url: str | None,
) -> None:
    lang = kyopro_default_lang()
    ext = kyopro_lang_ext(lang)
    kyopro_ensure_template(lang)
    template = kyopro_template_path(lang)
    contest_dir = prepare_contest_dir(contest)

    (contest_dir / ".site").write_text(site + "\n", encoding="utf-8")
    if contest_url:
        (contest_dir / ".contest-url").write_text(contest_url + "\n", encoding="utf-8")

    task_lines: list[str] = []

    info(f"creating manual contest: {contest}")
    info(f"site: {site}")
    info(f"language: {lang}")

    for label in labels:
        task_dir = contest_dir / label
        task_dir.mkdir(parents=True, exist_ok=True)

        source = contest_dir / f"{label}.{ext}"
        if not source.exists():
            shutil.copyfile(template, source)

        task_lines.append(f"{label}\t{label}\t\n")
        ok(f"prepared: {label}")

    (contest_dir / ".tasks.tsv").write_text("".join(task_lines), encoding="utf-8")
    info(f"created: {contest}")
    info(f"add a test case: cd {contest} && ktest <problem> --add-case")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="knew",
        description="Create an AtCoder contest or a site-independent manual contest.",
    )
    parser.add_argument("contest", help="contest directory/name")
    parser.add_argument(
        "--manual",
        action="store_true",
        help="do not search a contest site; create local files only",
    )
    parser.add_argument(
        "--site",
        help="site identifier stored in .site (manual default: manual)",
    )
    parser.add_argument(
        "-p",
        "--problems",
        nargs="+",
        metavar="NAME",
        help="manual problem names; spaces and comma-separated values are supported",
    )
    parser.add_argument("--url", help="optional contest URL stored in .contest-url")
    args = parser.parse_args()

    contest = validate_name(args.contest, kind="contest")

    if args.manual:
        labels = parse_problem_labels(args.problems)
        if not labels:
            parser.error("--manual requires --problems/-p")

        create_manual_contest(
            contest,
            site=args.site or "manual",
            labels=labels,
            contest_url=args.url,
        )
        return

    if args.problems or args.url or args.site not in {None, "atcoder"}:
        parser.error("--problems, --url, and non-AtCoder --site require --manual")

    create_contest(contest)


if __name__ == "__main__":
    main()