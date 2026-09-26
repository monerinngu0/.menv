from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


MENV_ROOT = Path(
    os.environ.get(
        "MENV_ROOT",
        Path.home() / ".menv",
    )
)

KYOPRO_ROOT = (
    MENV_ROOT
    / "envs"
    / "kyopro"
)

CONFIG_PATH = KYOPRO_ROOT / ".config"


class ConfigError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class DefaultsConfig:
    site: str = "atcoder"
    language: str = "cpp"


@dataclass(frozen=True, slots=True)
class KnewConfig:
    download_samples: bool = True


@dataclass(frozen=True, slots=True)
class TestingConfig:
    timeout: float = 2.0


@dataclass(frozen=True, slots=True)
class KsubConfig:
    test_before_submit: bool = False


@dataclass(frozen=True, slots=True)
class CppConfig:
    build_command: tuple[str, ...] = (
        "g++",
        "-std=gnu++23",
        "{source}",
        "-o",
        "{output}",
    )

    run_command: tuple[str, ...] = (
        "{output}",
    )

    include_dirs: tuple[Path, ...] = ()


@dataclass(frozen=True, slots=True)
class PythonConfig:
    run_command: tuple[str, ...] = (
        "python3",
        "{source}",
    )


@dataclass(frozen=True, slots=True)
class KyoproConfig:
    defaults: DefaultsConfig = field(
        default_factory=DefaultsConfig
    )

    knew: KnewConfig = field(
        default_factory=KnewConfig
    )

    testing: TestingConfig = field(
        default_factory=TestingConfig
    )

    ksub: KsubConfig = field(
        default_factory=KsubConfig
    )

    cpp: CppConfig = field(
        default_factory=CppConfig
    )

    python: PythonConfig = field(
        default_factory=PythonConfig
    )


def _table(
    data: dict,
    name: str,
) -> dict:
    value = data.get(name, {})

    if not isinstance(value, dict):
        raise ConfigError(
            f"[{name}] must be a table"
        )

    return value


def _string(
    table: dict,
    key: str,
    default: str,
) -> str:
    value = table.get(
        key,
        default,
    )

    if not isinstance(value, str) or not value:
        raise ConfigError(
            f"{key} must be a non-empty string"
        )

    return value


def _bool(
    table: dict,
    key: str,
    default: bool,
) -> bool:
    value = table.get(
        key,
        default,
    )

    if not isinstance(value, bool):
        raise ConfigError(
            f"{key} must be a boolean"
        )

    return value


def _float(
    table: dict,
    key: str,
    default: float,
) -> float:
    value = table.get(
        key,
        default,
    )

    if not isinstance(
        value,
        (int, float),
    ):
        raise ConfigError(
            f"{key} must be a number"
        )

    value = float(value)

    if value <= 0:
        raise ConfigError(
            f"{key} must be positive"
        )

    return value


def _string_list(
    table: dict,
    key: str,
    default: tuple[str, ...],
) -> tuple[str, ...]:
    value = table.get(
        key,
        list(default),
    )

    if not isinstance(value, list):
        raise ConfigError(
            f"{key} must be an array"
        )

    result: list[str] = []

    for item in value:
        if not isinstance(item, str):
            raise ConfigError(
                f"{key} must contain only strings"
            )

        result.append(item)

    return tuple(result)


def load_config(
    path: Path | None = None,
) -> KyoproConfig:
    path = path or CONFIG_PATH

    if not path.is_file():
        return KyoproConfig()

    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
    except (
        OSError,
        tomllib.TOMLDecodeError,
    ) as error:
        raise ConfigError(
            f"failed to load config: {path}"
        ) from error

    defaults = _table(
        data,
        "defaults",
    )

    knew = _table(
        data,
        "knew",
    )

    testing = _table(
        data,
        "testing",
    )

    ksub = _table(
        data,
        "ksub",
    )

    cpp = _table(
        data,
        "cpp",
    )

    python = _table(
        data,
        "python",
    )

    cpp_include_dirs = tuple(
        Path(path).expanduser().resolve()
        for path in _string_list(
            cpp,
            "include_dirs",
            (),
        )
    )

    return KyoproConfig(
        defaults=DefaultsConfig(
            site=_string(
                defaults,
                "site",
                "atcoder",
            ),
            language=_string(
                defaults,
                "language",
                "cpp",
            ),
        ),
        knew=KnewConfig(
            download_samples=_bool(
                knew,
                "download_samples",
                True,
            ),
        ),
        testing=TestingConfig(
            timeout=_float(
                testing,
                "timeout",
                2.0,
            ),
        ),
        ksub=KsubConfig(
            test_before_submit=_bool(
                ksub,
                "test_before_submit",
                False,
            ),
        ),
        cpp=CppConfig(
            build_command=_string_list(
                cpp,
                "build_command",
                CppConfig().build_command,
            ),
            run_command=_string_list(
                cpp,
                "run_command",
                CppConfig().run_command,
            ),
            include_dirs=cpp_include_dirs,
        ),
        python=PythonConfig(
            run_command=_string_list(
                python,
                "run_command",
                PythonConfig().run_command,
            ),
        ),
    )