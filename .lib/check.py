from pathlib import Path
import shutil
import subprocess


def command(name: str) -> bool:
    return shutil.which(name) is not None


def apt(package: str) -> bool:
    return subprocess.run(
        ["dpkg", "-s", package],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def venv(path: str | Path) -> bool:
    p = Path(path)
    return (p / "bin" / "python").exists()


def pip_package(venv_path: str | Path, package: str) -> bool:
    python = Path(venv_path) / "bin" / "python"

    if not python.exists():
        return False

    return subprocess.run(
        [str(python), "-m", "pip", "show", package],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0