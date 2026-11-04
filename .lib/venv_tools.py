"""Helpers used explicitly by bundled TOML definitions; not part of setup runner."""
from __future__ import annotations
import os
import re
import subprocess
import sys
from pathlib import Path

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



def main():
    action, folder, *packages = sys.argv[1:]
    requested = Path(folder).absolute()
    venv = validate_local_venv(requested.parent, requested.name)
    if action == "ensure":
        if packages:
            raise ValueError("ensure does not accept packages")
        if not (venv / "bin/python").exists():
            subprocess.run([sys.executable, "-I", "-m", "venv", str(venv)], check=True)
        validate_local_venv(requested.parent, requested.name)
        return 0
    if action not in ("install", "update"):
        raise ValueError("expected ensure/install/update")
    if not (venv / "bin/python").exists():
        raise ValueError("venv missing: run setup init first")
    return subprocess.run(pip_command(venv, "install", "--no-user",
                          *(["--upgrade"] if action == "update" else []), *packages)).returncode

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"venv: {error}", file=sys.stderr)
        raise SystemExit(1)
