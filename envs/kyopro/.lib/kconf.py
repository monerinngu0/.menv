#!/usr/bin/env python3

from __future__ import annotations

import os
import shlex
import shutil
import sys
from pathlib import Path


MENV_ROOT = Path(os.environ.get("MENV_ROOT", Path.home() / ".menv"))
KYOPRO_ROOT = MENV_ROOT / "envs" / "kyopro"

sys.path.insert(0, str(MENV_ROOT / ".lib"))
sys.path.insert(0, str(KYOPRO_ROOT / ".lib"))

from common import ok, ng  # noqa: E402
from kyopro import (  # noqa: E402
    kyopro_default_lang,
    kyopro_ensure_all_templates,
    kyopro_ensure_config,
    kyopro_ensure_template,
    kyopro_lang_ext,
    kyopro_lang_template_name,
    kyopro_langs,
    kyopro_set_default_lang,
    kyopro_template_path,
    kyopro_validate_lang,
)


def usage() -> None:
    print(
        """usage:
  kconf show
  kconf default <lang>
  kconf edit <lang>
  kconf path <lang>
  kconf list"""
    )


def require_lang(lang: str) -> None:
    if not kyopro_validate_lang(lang):
        ng(f"unsupported language: {lang}")
        print("Run: kconf list")
        sys.exit(1)


def find_editor() -> list[str] | None:
    if os.environ.get("EDITOR"):
        return shlex.split(os.environ["EDITOR"])

    for editor in ["nvim", "vim", "vi", "nano"]:
        path = shutil.which(editor)
        if path is not None:
            return [path]

    return None


def cmd_show() -> None:
    lang = kyopro_default_lang()

    print(f"DEFAULT_LANG={lang}")
    print()
    print("templates:")

    for item in kyopro_langs():
        ext = kyopro_lang_ext(item)
        path = kyopro_template_path(item)
        print(f"  {item:<5} extension={ext:<5} template={path}")


def cmd_default(args: list[str]) -> None:
    if len(args) != 1:
        usage()
        sys.exit(1)

    lang = args[0]
    require_lang(lang)

    kyopro_set_default_lang(lang)
    kyopro_ensure_template(lang)

    ok(f"DEFAULT_LANG={lang}")


def cmd_edit(args: list[str]) -> None:
    if len(args) != 1:
        usage()
        sys.exit(1)

    lang = args[0]
    require_lang(lang)

    kyopro_ensure_template(lang)
    path = kyopro_template_path(lang)

    editor = find_editor()
    if editor is None:
        ng("editor not found")
        print("Set EDITOR or install nvim, vim, vi, or nano.")
        sys.exit(1)

    os.execvp(editor[0], editor + [str(path)])


def cmd_path(args: list[str]) -> None:
    if len(args) != 1:
        usage()
        sys.exit(1)

    lang = args[0]
    require_lang(lang)

    kyopro_ensure_template(lang)
    print(kyopro_template_path(lang))


def cmd_list() -> None:
    for item in kyopro_langs():
        ext = kyopro_lang_ext(item)
        tmpl = kyopro_lang_template_name(item)
        print(f"{item:<5} extension={ext:<5} template={tmpl}")


def main() -> None:
    kyopro_ensure_config()
    kyopro_ensure_all_templates()

    cmd = sys.argv[1] if len(sys.argv) >= 2 else ""

    if cmd == "show":
        cmd_show()
    elif cmd == "default":
        cmd_default(sys.argv[2:])
    elif cmd == "edit":
        cmd_edit(sys.argv[2:])
    elif cmd == "path":
        cmd_path(sys.argv[2:])
    elif cmd == "list":
        cmd_list()
    elif cmd in {"", "-h", "--help", "help"}:
        usage()
    else:
        ng(f"unknown command: {cmd}")
        usage()
        sys.exit(1)


if __name__ == "__main__":
    main()