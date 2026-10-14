"""GitHub release checks; package writes are confined to a validated local venv."""
from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

from common import info, ng, ok, run_quiet


def validate_local_venv(env: Path, relative: str) -> Path:
    path = (env / relative).resolve()
    if Path(relative).is_absolute() or path == env.resolve() or not path.is_relative_to(env.resolve()):
        raise ValueError("venv path must stay inside the selected environment")
    python = path / "bin" / "python"
    if python.exists():
        cfg = path / "pyvenv.cfg"
        if not cfg.is_file() or not re.search(
            r"(?im)^include-system-site-packages\s*=\s*false\s*$", cfg.read_text()
        ):
            raise ValueError(f"not an isolated venv: {path}")
        probe = subprocess.run(
            [str(python), "-I", "-c", "import sys; print(sys.prefix); print(sys.base_prefix)"],
            capture_output=True, text=True, check=True,
        ).stdout.splitlines()
        if len(probe) != 2 or Path(probe[0]).resolve() != path or probe[0] == probe[1]:
            raise ValueError(f"Python does not belong to the local venv: {path}")
    return path


def pip_command(venv: Path, *args: str) -> list[str]:
    # Ignore inherited pip destination overrides and config, including PIP_TARGET.
    script = (
        "import os,sys; "
        "[os.environ.pop(k) for k in list(os.environ) if k.startswith('PIP_')]; "
        "os.environ['PIP_CONFIG_FILE']=os.devnull; "
        "from pip._internal.cli.main import main; sys.exit(main(sys.argv[1:]))"
    )
    return [str(venv / "bin" / "python"), "-I", "-c", script, *args]


def latest_release(repository: str, tag_prefix: str = "v") -> str:
    match = re.fullmatch(r"https://github\.com/([\w.-]+)/([\w.-]+)/?", repository)
    if not match:
        raise ValueError("repository must be a GitHub repository URL")
    owner, repo = match.groups()
    request = urllib.request.Request(
        f"https://api.github.com/repos/{owner}/{repo}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "menv-mcheck"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        release = json.load(response)
    tag = release.get("tag_name")
    if not isinstance(tag, str) or release.get("draft") or release.get("prerelease"):
        raise ValueError("no stable GitHub release found")
    if tag_prefix and tag.startswith(tag_prefix):
        tag = tag[len(tag_prefix):]
    # A GitHub tag is never allowed to turn into pip options or a URL.
    if not re.fullmatch(r"[0-9][0-9A-Za-z.!+_-]*", tag):
        raise ValueError(f"release tag cannot be mapped to a package version: {tag}")
    return tag


def package_versions(venv: Path, package: str, latest: str) -> tuple[str, bool]:
    script = (
        "import importlib.metadata,sys; from pip._vendor.packaging.version import Version; "
        "current=importlib.metadata.version(sys.argv[1]); "
        "print(current); print(int(Version(current) < Version(sys.argv[2])))"
    )
    completed = subprocess.run(
        [str(venv / "bin" / "python"), "-I", "-c", script, package, latest],
        capture_output=True, text=True,
    )
    if completed.returncode:
        raise ValueError(f"cannot read/compare installed version for {package}")
    current, newer = completed.stdout.strip().splitlines()
    return current, newer == "1"


def check_github_updates(
    env: Path, conf: dict[str, Any], *, venv_rel: str, update: bool, result: Any,
) -> None:
    entries = conf.get("update", {}).get("github", [])
    if not isinstance(entries, list):
        raise ValueError("[update].github must be an array of tables")
    declared = conf.get("venv", {}).get("packages", [])
    declared_names = {p.split(" @ ", 1)[0].lower().replace("_", "-") for p in declared}
    for entry in entries:
        try:
            if not isinstance(entry, dict):
                raise ValueError("GitHub update entry must be a table")
            package = entry.get("package", "")
            if not isinstance(package, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", package):
                raise ValueError("invalid GitHub update package name")
            if package.lower().replace("_", "-") not in declared_names:
                raise ValueError(f"GitHub update package must be declared in [venv].packages: {package}")
            venv = validate_local_venv(env, venv_rel)
            if not (venv / "bin" / "python").exists():
                raise ValueError("local venv missing; use --install first")
            latest = latest_release(entry["repository"], entry.get("tag_prefix", "v"))
            current, newer = package_versions(venv, package, latest)
            if not newer:
                ok(f"GitHub: {package} {current} is up to date (release {latest})")
                result.add(True)
                continue
            info(f"GitHub: {package} {current} -> {latest}")
            if not update:
                ng(f"update available: {package}; use --update")
                result.add(False)
                continue
            # Use the exact released version from PyPI; do not execute repo main.
            success = run_quiet(
                f"updating local pip package: {package}",
                pip_command(venv, "install", "--no-user", f"{package}=={latest}"),
            )
            if not success:
                raise ValueError(f"failed to install released version: {package}=={latest}")
            installed, still_newer = package_versions(venv, package, latest)
            if still_newer:
                raise ValueError(f"update verification failed: {package} {installed}")
            ok(f"updated: {package} {installed}")
            result.add(True)
        except (KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError) as error:
            ng(f"GitHub update check failed: {error}")
            result.add(False)
