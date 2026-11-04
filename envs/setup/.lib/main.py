#!/usr/bin/env python3
"""menv's definition-driven setup CLI (Python 3.11+)."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import shlex
import sys
from pathlib import Path

import local
from config import Paths, name
from remote import DEFAULT_REGISTRY, Registry
from runner import display, execute, load_state, prepare


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "update", "list", "search", "info"):
        sub = commands.add_parser(command)
        sub.add_argument("--registry", default=None, help="HTTPS registry base URL")
        sub.add_argument("--offline", action="store_true", help="use validated registry cache only")
        if command in ("init", "update", "info"):
            sub.add_argument("name", nargs="?" if command == "update" else None)
            sub.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
            sub.add_argument("--workdir", type=Path, help="remote work directory (saved after success)")
        if command in ("init", "update"):
            sub.add_argument("--dry-run", action="store_true", help="display plan without execution or registration")
            sub.add_argument("-y", "--yes", action="store_true", help="use saved/default options and approve displayed plan")
        if command == "update":
            sub.add_argument("--all", action="store_true", help="update only successfully initialized targets")
        if command in ("list", "search"):
            sub.add_argument("--local", action="store_true", help="only local definitions; no network")
        if command == "search":
            sub.add_argument("keyword")
    return parser.parse_args()


def split_target(target: str) -> tuple[str | None, str]:
    source = None
    if ":" in target:
        source, target = target.split(":", 1)
        if source not in ("local", "remote"):
            raise ValueError(f"invalid source: {source}")
    return source, name(target)


def main() -> int:
    args = arguments()
    paths = Paths.load()
    registry_url = args.registry or os.environ.get("MENV_SETUP_REGISTRY", DEFAULT_REGISTRY)
    registries = {}

    def registry(url: str = registry_url) -> Registry:
        if url not in registries:
            registries[url] = Registry(url, paths.cache, args.offline)
        return registries[url]

    if args.command in ("list", "search"):
        rows = []
        for key in local.discover(paths.root):
            definition, _ = local.load(paths.root, key)
            rows.append((f"local:{key}", definition.version, definition.description))
        if not args.local:
            for key, entry in registry().index().items():
                rows.append((f"remote:{key}", entry["version"], entry.get("description", "")))
        for identity, version, description in sorted(rows):
            if args.command == "list" or args.keyword.casefold() in f"{identity} {description}".casefold():
                print(f"{identity}\tv{version}\t{description}")
        return 0

    supplied = {}
    for assignment in args.set:
        if "=" not in assignment:
            raise ValueError("--set requires KEY=VALUE")
        key, value = assignment.split("=", 1)
        if key in supplied:
            raise ValueError(f"duplicate option: {key}")
        supplied[key] = value
    if args.command == "update":
        if bool(args.name) == bool(args.all):
            raise ValueError("update requires exactly one of a target name or --all")
        if args.all and (supplied or args.workdir):
            raise ValueError("--all reuses per-target options/workdir; --set and --workdir need a single target")

    # Hold the lock across planning, approval, execution and registration to avoid lost updates.
    paths.state.mkdir(parents=True, exist_ok=True)
    with (paths.state / ".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("another setup operation is running") from error
        state = load_state(paths.state / "installed.json")
        targets = list(state) if args.command == "update" and args.all else [args.name]
        if not targets:
            print("No initialized targets.")
            return 0
        plans = []
        for target in targets:
            source, key = split_target(target)
            if source is None:
                source = "local" if key in local.discover(paths.root) else "remote"
            identity = f"{source}:{key}"
            saved = state.get(identity, {})
            remote_url = None
            if source == "local":
                if args.workdir:
                    raise ValueError("--workdir only applies to remote definitions")
                definition, base = local.load(paths.root, key)
            else:
                remote_url = args.registry or saved.get("registry") or registry_url
                remote_registry = registry(remote_url)
                remote_url = remote_registry.url
                definition = remote_registry.load(key)
                base = args.workdir or Path(saved.get("workdir", paths.data / "work" / key))
                base = base.expanduser().resolve()
            if args.command == "info":
                if supplied:
                    raise ValueError("info displays templates; use init/update --dry-run --set for expanded plans")
                print(f"{identity} · Definition v{definition.version}\n{definition.description}")
                print(f"Work directory: {base}")
                if remote_url:
                    print(f"Registry: {remote_url}")
                for option, value in definition.options.items():
                    print(f"{option}: {value.description}; default={value.default!r}; choices={value.choices}")
                for action, value in definition.actions.items():
                    print(f"\n[{action}] {value.description}")
                    for step in value.steps:
                        print(f"  (cwd {step.cwd!r}) {shlex.join(step.run)}")
                        if step.unless_path is not None:
                            print(f"    unless_path: {step.unless_path!r}")
                return 0
            plans.append(prepare(definition, source, args.command, base, paths, supplied,
                                 saved=saved.get("options"), registry=remote_url,
                                 interactive=sys.stdin.isatty() and not args.yes))
        for plan in plans:
            display(plan)
        if args.dry_run:
            return 0
        if not args.yes:
            try:
                answer = input("\nProceed? [y/N] ")
            except EOFError:
                answer = ""
            if answer.strip().lower() not in ("y", "yes"):
                print("Cancelled.")
                return 1
        return execute(tuple(plans), paths, state)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, EOFError, json.JSONDecodeError) as error:
        print(f"setup: {error}", file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("\nsetup: interrupted; completed steps are not rolled back", file=sys.stderr)
        raise SystemExit(130)
