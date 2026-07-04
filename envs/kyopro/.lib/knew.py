#!/usr/bin/env python3

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


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: knew <contest>")
        sys.exit(1)

    create_contest(sys.argv[1])


if __name__ == "__main__":
    main()