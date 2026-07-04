#!/usr/bin/env python3

from __future__ import annotations

import os
import shutil
from pathlib import Path


MENV_ROOT = Path(os.environ.get("MENV_ROOT", Path.home() / ".menv"))
KYOPRO_ROOT = MENV_ROOT / "envs" / "kyopro"

VENV = KYOPRO_ROOT / ".venv"
CONFIG = KYOPRO_ROOT / ".config"
TEMPLATE_DIR = KYOPRO_ROOT / ".template"
ATCODER_URL = "https://atcoder.jp/"


LANGS = {
    "cpp": {
        "ext": "cpp",
        "template": "main.cpp",
    },
    "py": {
        "ext": "py",
        "template": "main.py",
    },
}


DEFAULT_TEMPLATES = {
    "cpp": """#include <bits/stdc++.h>
using namespace std;
using ll = long long;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    return 0;
}
""",
    "py": """import sys


def main() -> None:
    input = sys.stdin.readline


if __name__ == "__main__":
    main()
""",
}


def kyopro_langs() -> list[str]:
    return list(LANGS.keys())


def kyopro_validate_lang(lang: str) -> bool:
    return lang in LANGS


def kyopro_lang_ext(lang: str) -> str:
    if not kyopro_validate_lang(lang):
        raise ValueError(f"unsupported language: {lang}")

    return LANGS[lang]["ext"]


def kyopro_lang_template_name(lang: str) -> str:
    if not kyopro_validate_lang(lang):
        raise ValueError(f"unsupported language: {lang}")

    return LANGS[lang]["template"]


def kyopro_template_path(lang: str) -> Path:
    return TEMPLATE_DIR / kyopro_lang_template_name(lang)


def kyopro_write_default_template(lang: str, path: Path) -> None:
    if lang not in DEFAULT_TEMPLATES:
        raise ValueError(f"default template is not available: {lang}")

    path.write_text(DEFAULT_TEMPLATES[lang], encoding="utf-8")


def kyopro_ensure_config() -> None:
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG.exists():
        CONFIG.write_text("DEFAULT_LANG=cpp\n", encoding="utf-8")


def kyopro_read_config() -> dict[str, str]:
    kyopro_ensure_config()

    result: dict[str, str] = {}

    try:
        lines = CONFIG.read_text(encoding="utf-8").splitlines()
    except OSError:
        return result

    for line in lines:
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()

    return result


def kyopro_default_lang() -> str:
    config = kyopro_read_config()
    lang = config.get("DEFAULT_LANG", "cpp")

    if kyopro_validate_lang(lang):
        return lang

    return "cpp"


def kyopro_set_default_lang(lang: str) -> None:
    if not kyopro_validate_lang(lang):
        raise ValueError(f"unsupported language: {lang}")

    kyopro_ensure_config()
    CONFIG.write_text(f"DEFAULT_LANG={lang}\n", encoding="utf-8")


def kyopro_ensure_template(lang: str) -> None:
    if not kyopro_validate_lang(lang):
        raise ValueError(f"unsupported language: {lang}")

    path = kyopro_template_path(lang)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        kyopro_write_default_template(lang, path)


def kyopro_ensure_all_templates() -> None:
    for lang in kyopro_langs():
        kyopro_ensure_template(lang)


def kyopro_python_runtime() -> str | None:
    candidates = [
        VENV / "bin" / "python",
        VENV / "bin" / "python3",
    ]

    for path in candidates:
        if path.exists() and os.access(path, os.X_OK):
            return str(path)

    return shutil.which("python3")


def kyopro_oj_path() -> str | None:
    path = VENV / "bin" / "oj"

    if path.exists() and os.access(path, os.X_OK):
        return str(path)

    return shutil.which("oj")


def kyopro_find_source(root: Path, problem: str) -> Path | None:
    default = kyopro_default_lang()
    order = [default] + [lang for lang in kyopro_langs() if lang != default]

    candidates: list[Path] = []

    for lang in order:
        ext = kyopro_lang_ext(lang)

        candidates.append(root / f"{problem}.{ext}")
        candidates.append(root / problem / f"main.{ext}")

    for path in candidates:
        if path.exists():
            return path

    return None


def kyopro_source_lang(path: Path) -> str | None:
    suffix = path.suffix.lstrip(".")

    for lang in kyopro_langs():
        if kyopro_lang_ext(lang) == suffix:
            return lang

    return None


def find_contest_root(start: Path | None = None) -> Path | None:
    cur = (start or Path.cwd()).resolve()

    while True:
        if (cur / ".contest").exists():
            return cur

        if cur.parent == cur:
            return None

        cur = cur.parent