"""Validate definitions and expand strings without invoking a shell."""

from __future__ import annotations

import os
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path


NAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*(?:/[a-zA-Z0-9][a-zA-Z0-9_.-]*)*")
KEY = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")
PLACEHOLDER = re.compile(r"\{\{|\}\}|(?<!\$)\{([a-zA-Z_][a-zA-Z0-9_]*)\}")
BUILTINS = {"root", "env", "home", "python", "data", "cache", "state", "work"}


def name(value: str) -> str:
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise ValueError(f"invalid definition name: {value!r}")
    return value


def fields(value: object, allowed: set[str], label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a table")
    unknown = value.keys() - allowed
    if unknown:
        raise ValueError(f"unknown {label} fields: {', '.join(sorted(unknown))}")
    return value


def string(value: object, label: str, *, empty: bool = False) -> str:
    if not isinstance(value, str) or "\0" in value or (not empty and not value.strip()):
        raise ValueError(f"{label} must be a {'possibly empty ' if empty else ''}string")
    return value


def argv(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError("run/commands entries must be nonempty argument arrays")
    result = tuple(string(v, "argument", empty=True) for v in value)
    string(result[0], "executable")
    return result


@dataclass(frozen=True)
class Step:
    run: tuple[str, ...]
    cwd: str = "."
    unless_path: str | None = None


@dataclass(frozen=True)
class Action:
    description: str
    steps: tuple[Step, ...]


@dataclass(frozen=True)
class Option:
    description: str
    default: str | None
    choices: tuple[str, ...]


@dataclass(frozen=True)
class Definition:
    name: str
    version: int
    description: str
    options: dict[str, Option]
    actions: dict[str, Action]


def parse(raw: bytes, expected: str) -> Definition:
    conf = fields(tomllib.loads(raw.decode("utf-8")),
                  {"name", "version", "description", "options", "init", "update"}, "definition")
    if name(conf.get("name")) != expected:
        raise ValueError(f"definition name must be {expected!r}")
    version = conf.get("version")
    if type(version) is not int or version < 1:
        raise ValueError("version must be a positive definition revision")
    description = string(conf.get("description"), "description")
    options = {}
    raw_options = conf.get("options", {})
    if not isinstance(raw_options, dict):
        raise ValueError("options must be a table")
    for key, value in raw_options.items():
        if not KEY.fullmatch(key) or key in BUILTINS:
            raise ValueError(f"invalid or reserved option: {key}")
        value = fields(value, {"description", "default", "choices"}, f"options.{key}")
        default = value.get("default")
        if default is not None:
            string(default, f"options.{key}.default", empty=True)
        choices = value.get("choices", [])
        if not isinstance(choices, list):
            raise ValueError(f"options.{key}.choices must be an array")
        choices = tuple(string(v, "choice", empty=True) for v in choices)
        if choices and default is not None and default not in choices:
            raise ValueError(f"default for {key} is not in choices")
        options[key] = Option(string(value.get("description"), "option description"), default, choices)
    actions = {}
    for action in ("init", "update"):
        if action not in conf:
            continue
        value = fields(conf[action], {"description", "commands", "steps"}, action)
        if ("commands" in value) == ("steps" in value):
            raise ValueError(f"{action}: specify exactly one of commands or steps")
        commands = value.get("commands", value.get("steps"))
        if not isinstance(commands, list) or not commands:
            raise ValueError(f"{action}: commands/steps must be nonempty")
        steps = []
        for command in commands:
            if "commands" in value:
                steps.append(Step(argv(command)))
            else:
                command = fields(command, {"run", "cwd", "unless_path"}, "step")
                condition = command.get("unless_path")
                if condition is not None:
                    string(condition, "unless_path")
                steps.append(Step(argv(command.get("run")),
                                  string(command.get("cwd", "."), "cwd"), condition))
        actions[action] = Action(string(value.get("description"), "action description"), tuple(steps))
    if "init" not in actions:
        raise ValueError("definition must declare init")
    return Definition(expected, version, description, options, actions)


def expand(template: str, values: dict[str, str]) -> str:
    def replace(match: re.Match) -> str:
        if match[0] == "{{":
            return "{"
        if match[0] == "}}":
            return "}"
        key = match[1]
        if key not in values:
            raise ValueError(f"unknown placeholder: {key}")
        return values[key]
    # Substitute once: braces in user input are literal, never recursively expanded.
    return PLACEHOLDER.sub(replace, template)


@dataclass(frozen=True)
class Paths:
    root: Path
    data: Path
    cache: Path
    state: Path

    @classmethod
    def load(cls) -> Paths:
        def xdg(key: str, fallback: str) -> Path:
            path = Path(os.environ.get(key) or Path.home() / fallback).expanduser()
            if not path.is_absolute():
                raise ValueError(f"{key} must be absolute")
            return path / "menv" / "setup"
        root = Path(os.environ.get("MENV_ROOT", Path(__file__).resolve().parents[3])).resolve()
        return cls(root, xdg("XDG_DATA_HOME", ".local/share"),
                   xdg("XDG_CACHE_HOME", ".cache"), xdg("XDG_STATE_HOME", ".local/state"))

    def values(self, base: Path) -> dict[str, str]:
        return {"root": str(self.root), "env": str(base), "work": str(base),
                "home": str(Path.home()), "python": sys.executable,
                "data": str(self.data), "cache": str(self.cache), "state": str(self.state)}
