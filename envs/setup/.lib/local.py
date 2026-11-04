"""Local definitions are discovered independently of the runner."""

from pathlib import Path

from config import Definition, name, parse


def discover(root: Path) -> dict[str, Path]:
    envs = root / "envs"
    result = {}
    if (root / ".toml").is_file():
        result["menv"] = root
    for path in sorted(envs.rglob(".toml")):
        relative = path.parent.relative_to(envs)
        if any(part.startswith(".") for part in relative.parts):
            continue
        key = name(relative.as_posix())
        path.resolve().relative_to(envs.resolve())
        result[key] = path.parent
    return result


def load(root: Path, key: str) -> tuple[Definition, Path]:
    definitions = discover(root)
    if key not in definitions:
        raise ValueError(f"local definition not found: {key}")
    base = definitions[key]
    return parse((base / ".toml").read_bytes(), key), base
