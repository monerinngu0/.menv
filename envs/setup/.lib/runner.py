"""Prepare immutable execution plans, then run exactly those plans."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from config import Definition, Paths, expand, name, string
from remote import atomic_write


@dataclass(frozen=True)
class Command:
    argv: tuple[str, ...]
    cwd: Path
    unless_path: Path | None


@dataclass(frozen=True)
class Plan:
    identity: str
    version: int
    action: str
    description: str
    options: tuple[tuple[str, str], ...]
    base: Path
    registry: str | None
    commands: tuple[Command, ...]


def prepare(definition: Definition, source: str, action: str, base: Path,
            paths: Paths, supplied: dict, *, saved: dict | None = None,
            registry: str | None = None, interactive: bool = True) -> Plan:
    if action not in definition.actions:
        raise ValueError(f"{source}:{definition.name} has no {action} action")
    if supplied.keys() - definition.options.keys():
        raise ValueError(f"unknown options: {', '.join(supplied.keys() - definition.options.keys())}")
    options = {}
    for key, option in definition.options.items():
        previous = (saved or {}).get(key, option.default)
        if key in supplied:
            value = supplied[key]
        elif interactive:
            prompt = f"{definition.name}.{key}: {option.description}"
            if option.choices:
                prompt += f" ({', '.join(option.choices)})"
            answer = input(prompt + (f" [{previous}]" if previous is not None else "") + ": ")
            value = answer if answer else previous
        else:
            value = previous
        if value is None:
            raise ValueError(f"required option {key}: supply --set {key}=value")
        string(value, key, empty=True)
        if option.choices and value not in option.choices:
            raise ValueError(f"invalid {key}: choose from {', '.join(option.choices)}")
        options[key] = value
    values = paths.values(base) | options
    action_conf = definition.actions[action]
    commands = []
    for step in action_conf.steps:
        cwd = Path(expand(step.cwd, values)).expanduser()
        cwd = Path(os.path.abspath(base / cwd))
        condition = None
        if step.unless_path is not None:
            condition = Path(os.path.abspath(cwd / Path(expand(step.unless_path, values)).expanduser()))
        args = tuple(expand(arg, values) for arg in step.run)
        for arg in args:
            string(arg, "expanded argument", empty=True)
        string(args[0], "expanded executable")
        commands.append(Command(args, cwd, condition))
    return Plan(f"{source}:{definition.name}", definition.version, action,
                expand(action_conf.description, values), tuple(options.items()), base,
                registry, tuple(commands))


def display(plan: Plan) -> None:
    print(f"\n{plan.action} {plan.identity} · Definition v{plan.version}")
    if plan.registry:
        print(f"Registry: {plan.registry}")
    print(f"Work directory: {shlex.quote(str(plan.base))}")
    for key, value in plan.options:
        print(f"  {key} = {value!r}")
    print(plan.description)
    for i, command in enumerate(plan.commands, 1):
        print(f"  {i}. (cwd {shlex.quote(str(command.cwd))}) {shlex.join(command.argv)}")
        if command.unless_path is not None:
            print(f"     skip if path exists: {shlex.quote(str(command.unless_path))}")
    sys.stdout.flush()


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    state = json.loads(path.read_text())
    if not isinstance(state, dict):
        raise ValueError("installed.json must be an object")
    for key, entry in state.items():
        source, separator, target = key.partition(":")
        if separator != ":" or source not in ("local", "remote"):
            raise ValueError(f"invalid installed target: {key}")
        name(target)
        if not isinstance(entry, dict) or not isinstance(entry.get("options"), dict):
            raise ValueError(f"invalid installed record: {key}")
        string(entry.get("workdir"), "saved workdir")
        if not Path(entry["workdir"]).is_absolute():
            raise ValueError("saved workdir must be absolute")
        if type(entry.get("version")) is not int or entry["version"] < 1:
            raise ValueError("saved version must be a positive revision")
        for option, value in entry["options"].items():
            string(value, f"saved option {option}", empty=True)
        if source == "remote":
            string(entry.get("registry"), "saved registry")
    return state


def execute(plans: tuple[Plan, ...], paths: Paths, state: dict) -> int:
    log_path = paths.state / "history.jsonl"
    for plan in plans:
        plan.base.mkdir(parents=True, exist_ok=True)
        for index, command in enumerate(plan.commands, 1):
            status = 0
            skipped = command.unless_path is not None and command.unless_path.exists()
            if not skipped:
                print(f"[{plan.identity} {index}/{len(plan.commands)}] {shlex.join(command.argv)}", flush=True)
                try:
                    status = subprocess.run(command.argv, cwd=command.cwd, shell=False).returncode
                except OSError as error:
                    print(f"setup: {error}", file=sys.stderr)
                    status = 127
            else:
                print(f"[{plan.identity} {index}] skipped", flush=True)
            record = {"time": datetime.now(timezone.utc).isoformat(), "target": plan.identity,
                      "action": plan.action, "version": plan.version, "step": index,
                      "argv": command.argv, "cwd": str(command.cwd),
                      "skipped": skipped, "returncode": status}
            with log_path.open("a", encoding="utf-8") as log:
                log.write(json.dumps(record, ensure_ascii=False) + "\n")
            if status:
                print(f"setup: stopped at {plan.identity} step {index}, exit {status}; "
                      "completed steps are not rolled back", file=sys.stderr)
                return status if 0 < status < 256 else 1
        # An explicit update of an uninitialized target does not register it.
        if plan.action == "init" or plan.identity in state:
            state[plan.identity] = {"version": plan.version, "options": dict(plan.options),
                                    "workdir": str(plan.base), "registry": plan.registry}
            atomic_write(paths.state / "installed.json",
                         (json.dumps(state, ensure_ascii=False, indent=2) + "\n").encode())
    return 0
