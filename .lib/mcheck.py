#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any


MENV_ROOT = Path(os.environ.get("MENV_ROOT", Path.home() / ".menv"))
MENV_ENVS = MENV_ROOT / "envs"

sys.path.insert(0, str(MENV_ROOT / ".lib"))

from common import ok, ng, warn, info, run_quiet  # noqa: E402
import check  # noqa: E402


@dataclass
class CheckResult:
    ok: int = 0
    ng: int = 0

    def add(self, success: bool) -> None:
        if success:
            self.ok += 1
        else:
            self.ng += 1

    def fix(self) -> None:
        if self.ng > 0:
            self.ng -= 1
        self.ok += 1

    @property
    def success(self) -> bool:
        return self.ng == 0


def env_path(name: str | None) -> Path:
    if name in (None, "", "."):
        path = os.environ.get("MENV_PATH", "")

        if path:
            return MENV_ENVS / path

        return MENV_ROOT

    assert name is not None

    if name in {"menv", "~"}:
        return MENV_ROOT

    if name.startswith("~/"):
        return MENV_ENVS / name[2:]

    if name.startswith("menv/"):
        return MENV_ENVS / name[len("menv/") :]

    if name == "..":
        path = os.environ.get("MENV_PATH", "")

        if not path:
            return MENV_ROOT

        parent = Path(path).parent

        if str(parent) == ".":
            return MENV_ROOT

        return MENV_ENVS / parent

    return MENV_ENVS / name


def display_name(path: Path) -> str:
    if path.resolve() == MENV_ROOT.resolve():
        return "menv"

    try:
        return str(path.resolve().relative_to(MENV_ENVS.resolve()))
    except ValueError:
        return str(path)


def load_toml(path: Path) -> dict[str, Any]:
    toml_path = path / ".toml"

    if not toml_path.exists():
        warn(f".toml not found: {toml_path}")
        sys.exit(1)

    with toml_path.open("rb") as f:
        return tomllib.load(f)


def list_of_strings(conf: dict[str, Any], section: str, key: str) -> list[str]:
    section_conf = conf.get(section, {})

    if section_conf is None:
        return []

    if not isinstance(section_conf, dict):
        warn(f"invalid .toml: [{section}] must be a table")
        return []

    value = section_conf.get(key, [])

    if value is None:
        return []

    if not isinstance(value, list):
        warn(f"invalid .toml: [{section}].{key} must be a list")
        return []

    return [str(x) for x in value]


def load_plugin_packages(env: Path) -> ModuleType | None:
    path = env / ".lib" / "packages.py"

    if not path.exists():
        return None

    module_name = f"menv_plugin_packages_{display_name(env).replace('/', '_').replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, path)

    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)

    plugin_lib = str(env / ".lib")
    sys.path.insert(0, plugin_lib)

    try:
        spec.loader.exec_module(module)
    finally:
        try:
            sys.path.remove(plugin_lib)
        except ValueError:
            pass

    return module


def plugin_has_package(module: ModuleType | None, package: str) -> bool:
    if module is None:
        return False

    func = getattr(module, "has_package", None)

    if func is None:
        return False

    return bool(func(package))


def plugin_install_package(module: ModuleType | None, package: str) -> bool:
    if module is None:
        return False

    func = getattr(module, "install_package", None)

    if func is None:
        return False

    return bool(func(package))


def install_local_package_internal(env: Path, package: str) -> int:
    plugin_packages = load_plugin_packages(env)

    if plugin_packages is None:
        return 1

    success = plugin_install_package(plugin_packages, package)

    return 0 if success else 1


def handle_internal_command() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] == "__install_local_package__":
        if len(sys.argv) != 4:
            sys.exit(1)

        env = Path(sys.argv[2])
        package = sys.argv[3]

        sys.exit(install_local_package_internal(env, package))


def check_local_packages(
    env: Path,
    conf: dict[str, Any],
    *,
    install: bool,
    result: CheckResult,
) -> None:
    packages = list_of_strings(conf, "apt", "packages")

    if not packages:
        return

    plugin_packages = load_plugin_packages(env)

    print("local packages:")

    for pkg in packages:
        if plugin_has_package(plugin_packages, pkg):
            ok(f"apt: {pkg}")
            result.add(True)
            continue

        ng(f"apt: {pkg}")
        result.add(False)

        if plugin_packages is None:
            warn(f"plugin package hook not found: {env / '.lib' / 'packages.py'}")
            info("define has_package(package) and install_package(package) in the plugin")
            continue

        if install:
            success = run_quiet(
                f"installing apt: {pkg}",
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "__install_local_package__",
                    str(env),
                    pkg,
                ],
            )

            plugin_packages = load_plugin_packages(env)

            if success and plugin_has_package(plugin_packages, pkg):
                ok(f"installed apt: {pkg}")
                result.fix()
            else:
                ng(f"failed to install apt: {pkg}")
        else:
            info(f"install: mcheck {display_name(env)} --install")

    print()


def check_global_packages(
    conf: dict[str, Any],
    *,
    install: bool,
    result: CheckResult,
) -> None:
    packages = list_of_strings(conf, "apt-g", "packages")

    if not packages:
        return

    print("global apt packages:")

    for pkg in packages:
        if check.apt_global_package_exists(pkg):
            ok(f"apt-g: {pkg}")
            result.add(True)
            continue

        ng(f"apt-g: {pkg}")
        result.add(False)

        if install:
            success = run_quiet(
                f"installing apt-g: {pkg}",
                ["sudo", "apt", "install", "-y", pkg],
            )

            if success and check.apt_global_package_exists(pkg):
                ok(f"installed apt-g: {pkg}")
                result.fix()
            else:
                ng(f"failed to install apt-g: {pkg}")
        else:
            info(f"install: sudo apt install -y {pkg}")

    print()


def check_venv(
    env: Path,
    conf: dict[str, Any],
    *,
    install: bool,
    result: CheckResult,
) -> str:
    venv_conf = conf.get("venv")

    if not venv_conf:
        return ".venv"

    if not isinstance(venv_conf, dict):
        warn("invalid .toml: [venv] must be a table")
        return ".venv"

    venv_rel = str(venv_conf.get("path", ".venv"))
    python = str(venv_conf.get("python", "python3"))

    raw_packages = venv_conf.get("packages", [])
    if raw_packages is None:
        raw_packages = []

    if not isinstance(raw_packages, list):
        warn("invalid .toml: [venv].packages must be a list")
        raw_packages = []

    packages = [str(x) for x in raw_packages]
    venv_path = env / venv_rel

    print("venv:")

    if check.venv_exists(venv_path):
        ok(f"venv: {venv_rel}")
        result.add(True)
    else:
        ng(f"venv: {venv_rel}")
        result.add(False)

        if install:
            success = run_quiet(
                f"creating venv: {venv_rel}",
                [python, "-m", "venv", str(venv_path)],
            )

            if success and check.venv_exists(venv_path):
                ok(f"created venv: {venv_rel}")
                result.fix()
            else:
                ng(f"failed to create venv: {venv_rel}")
        else:
            info(f"install: mcheck {display_name(env)} --install")

    for pkg in packages:
        if check.pip_package_exists(venv_path, pkg):
            ok(f"pip: {pkg}")
            result.add(True)
            continue

        ng(f"pip: {pkg}")
        result.add(False)

        if not check.venv_exists(venv_path):
            info(f"venv is missing, cannot install pip package yet: {pkg}")
            continue

        if install:
            success = run_quiet(
                f"installing pip: {pkg}",
                [
                    str(venv_path / "bin" / "python"),
                    "-m",
                    "pip",
                    "install",
                    "-U",
                    pkg,
                ],
            )

            if success and check.pip_package_exists(venv_path, pkg):
                ok(f"installed pip: {pkg}")
                result.fix()
            else:
                ng(f"failed to install pip: {pkg}")
        else:
            info(f"install: mcheck {display_name(env)} --install")

    print()

    return venv_rel


def check_commands(
    env: Path,
    conf: dict[str, Any],
    *,
    venv_rel: str,
    result: CheckResult,
) -> None:
    commands = list_of_strings(conf, "commands", "names")

    if not commands:
        return

    print("commands:")

    for cmd in commands:
        found = check.find_command(
            cmd,
            env_path=env,
            venv_rel=venv_rel,
            include_global=True,
        )

        if found is not None:
            ok(f"command: {cmd} -> {found}")
            result.add(True)
        else:
            ng(f"command: {cmd}")
            result.add(False)
            info(f"install: mcheck {display_name(env)} --install")

    print()


def check_env(env: Path, *, install: bool = False) -> bool:
    conf = load_toml(env)
    result = CheckResult()

    print(f"==== check: {display_name(env)} ====")
    print()

    check_local_packages(env, conf, install=install, result=result)
    check_global_packages(conf, install=install, result=result)
    venv_rel = check_venv(env, conf, install=install, result=result)
    check_commands(env, conf, venv_rel=venv_rel, result=result)

    print("summary:")

    ok(f"ok: {result.ok}")

    if result.ng:
        ng(f"ng: {result.ng}")
    else:
        ok("all checks passed")

    print()
    print("==== check finished ====")

    return result.success


def main() -> None:
    handle_internal_command()

    parser = argparse.ArgumentParser(prog="mcheck")

    parser.add_argument("env", nargs="?")
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--strict", action="store_true")

    args = parser.parse_args()

    env = env_path(args.env)

    if not env.exists():
        ng(f"env not found: {args.env or os.environ.get('MENV_PATH', '')}")
        sys.exit(1)

    success = check_env(env, install=args.install)

    if args.strict and not success:
        sys.exit(1)


if __name__ == "__main__":
    main()