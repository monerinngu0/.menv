#!/usr/bin/env python3

from pathlib import Path
import os
import sys
import tomllib

import argparse
import subprocess

from common import ok, ng, warn, run_quiet
import check

MENV_ROOT = Path(os.environ.get("MENV_ROOT", Path.home() / ".menv"))
MENV_ENVS = MENV_ROOT / "envs"

def env_path(name: str | None) -> Path:
    if name in (None, "", "."):
        path = os.environ.get("MENV_PATH", "")
        if path:
            return MENV_ENVS / path
        return MENV_ROOT

    if name in ("menv", "~"):
        return MENV_ROOT

    if name.startswith("~/"):
        return MENV_ENVS / name[2:]

    if name.startswith("menv/"):
        return MENV_ENVS / name[len("menv/"):]

    if name == "..":
        path = os.environ.get("MENV_PATH", "")
        if not path:
            return MENV_ROOT
        parent = Path(path).parent
        if str(parent) == ".":
            return MENV_ROOT
        return MENV_ENVS / parent

    return MENV_ENVS / name

def load_toml(path: Path) -> dict:
    toml_path = path / ".toml"

    if not toml_path.exists():
        warn(f".toml not found: {toml_path}")
        sys.exit(1)

    with toml_path.open("rb") as f:
        return tomllib.load(f)

def display_name(path: Path) -> str:
    if path == MENV_ROOT:
        return "menv"
    return str(path.relative_to(MENV_ENVS))        

def check_env(path: Path, install: bool = False) -> None:
    conf = load_toml(path)

    print(f"==== check: {display_name(path)} ====")
    print()

    for pkg in conf.get("apt", {}).get("packages", []):
        if check.apt(pkg):
            ok(f"apt: {pkg}")
        else:
            ng(f"apt: {pkg}")
            if install:
                run_quiet(
                    f"installing apt: {pkg}",
                    ["sudo", "apt", "install", "-y", pkg],
                )
                ok(f"installed apt: {pkg}")

    for cmd in conf.get("commands", {}).get("names", []):
        if check.command(cmd):
            ok(f"command: {cmd}")
        else:
            ng(f"command: {cmd}")

    venv_conf = conf.get("venv")
    if venv_conf:
        venv_path = path / venv_conf.get("path", ".venv")

        if check.venv(venv_path):
            ok(f"venv: {venv_path.name}")
        else:
            ng(f"venv: {venv_path.name}")
            if install:
                python = venv_conf.get("python", "python3")
                run_quiet(
                    f"creating venv: {venv_path.name}",
                    [python, "-m", "venv", str(venv_path)],
                )
                ok(f"created venv: {venv_path.name}")

        for pkg in venv_conf.get("packages", []):
            if check.pip_package(venv_path, pkg):
                ok(f"pip: {pkg}")
            else:
                ng(f"pip: {pkg}")
                if install:
                    venv_python = venv_path / "bin" / "python"
                    run_quiet(
                        f"installing pip: {pkg}",
                        [str(venv_python), "-m", "pip", "install", "-U", pkg],
                    )
                    ok(f"installed pip: {pkg}")

    print()
    print("==== check finished ====")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("env", nargs="?")
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()

    path = env_path(args.env)

    if not path.exists():
        ng(f"env not found: {args.env or os.environ.get('MENV_PATH', '')}")
        sys.exit(1)

    check_env(path, install=args.install)


if __name__ == "__main__":
    main()