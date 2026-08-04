#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_LIBRARY_ROOT = Path(
    os.environ.get("KYOPRO_LIBRARY", Path.home() / "library")
)

EXPAND_PRAGMA = "#pragma kbuild expand"

INCLUDE_PATTERN = re.compile(
    r'^(?P<indent>\s*)'
    r'#\s*include\s*'
    r'(?P<open>[<"])'
    r'(?P<name>[^>"]+)'
    r'[>"]'
    r'(?P<tail>.*)$'
)


def fail(message: str, *, code: int = 1) -> None:
    print(f"[NG]   {message}", file=sys.stderr)
    sys.exit(code)


def info(message: str) -> None:
    print(f"[INFO] {message}", file=sys.stderr)


def ok(message: str) -> None:
    print(f"[OK]   {message}", file=sys.stderr)


def require_command(name: str) -> str:
    path = shutil.which(name)

    if path is None:
        fail(f"{name} not found")

    return path


def default_include_dirs(library_root: Path) -> list[Path]:
    """
    例えば次の両方を読み込めるようにする。

      ~/library/algo/dsu
      ~/library/ac-library/atcoder/all

    検索対象:

      ~/library
      ~/library/algo
      ~/library/ac-library
      ~/library/直下のその他のディレクトリ
    """

    library_root = library_root.expanduser()

    if not library_root.is_dir():
        return []

    result = [library_root.resolve()]

    for child in sorted(library_root.iterdir()):
        if child.is_dir():
            result.append(child.resolve())

    return result


class CppBundler:
    def __init__(self, include_dirs: list[Path]) -> None:
        self.include_dirs = self._unique_paths(include_dirs)

        # 実際に展開済みのファイル。
        self.expanded: set[Path] = set()

        # 循環include検出用。
        self.expansion_stack: list[Path] = []

        # 展開可能かどうかのキャッシュ。
        self.expandable_cache: dict[Path, bool] = {}

    @staticmethod
    def _unique_paths(paths: list[Path]) -> list[Path]:
        result: list[Path] = []
        seen: set[Path] = set()

        for path in paths:
            resolved = path.expanduser().resolve()

            if resolved in seen:
                continue

            seen.add(resolved)
            result.append(resolved)

        return result

    def find_include(
        self,
        name: str,
        *,
        quoted: bool,
        current_dir: Path,
    ) -> Path | None:
        candidates: list[Path] = []

        # #include "foo" は、まずinclude元と同じディレクトリを探す。
        if quoted:
            candidates.append(current_dir / name)

        # -I 相当の検索。
        for include_dir in self.include_dirs:
            candidates.append(include_dir / name)

        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()

        return None

    def should_expand(self, path: Path) -> bool:
        """
        ファイル中に

            #pragma kbuild expand

        があれば展開対象とする。

        pragmaの位置はファイル内のどこでもよい。
        """

        path = path.resolve()

        cached = self.expandable_cache.get(path)
        if cached is not None:
            return cached

        try:
            lines = path.read_text(
                encoding="utf-8"
            ).splitlines()
        except UnicodeDecodeError:
            fail(f"file is not UTF-8: {path}")
        except OSError as error:
            fail(f"failed to read {path}: {error}")

        result = any(
            line.strip() == EXPAND_PRAGMA
            for line in lines
        )

        self.expandable_cache[path] = result
        return result

    def bundle(self, source: Path) -> str:
        source = source.expanduser().resolve()

        if not source.is_file():
            fail(f"source not found: {source}")

        return "".join(
            self._bundle_file(source, is_root=True)
        )

    def _bundle_file(
        self,
        path: Path,
        *,
        is_root: bool = False,
    ) -> list[str]:
        path = path.resolve()

        if not is_root and path in self.expanded:
            return [
                "// kbuild: skipped duplicate include: "
                f"{self._display_path(path)}\n"
            ]

        if path in self.expansion_stack:
            chain = " -> ".join(
                self._display_path(item)
                for item in [*self.expansion_stack, path]
            )
            fail(f"cyclic include detected: {chain}")

        if not is_root:
            self.expanded.add(path)

        self.expansion_stack.append(path)

        try:
            lines = path.read_text(
                encoding="utf-8"
            ).splitlines(keepends=True)
        except UnicodeDecodeError:
            fail(f"file is not UTF-8: {path}")
        except OSError as error:
            fail(f"failed to read {path}: {error}")

        output: list[str] = []

        if not is_root:
            output.append(
                "\n"
                "// ===== kbuild begin: "
                f"{self._display_path(path)} =====\n"
            )

        for line in lines:
            stripped = line.strip()

            if not is_root and stripped in {
                "#pragma once",
                EXPAND_PRAGMA,
            }:
                # 展開後には不要。
                continue

            match = INCLUDE_PATTERN.match(line)

            if match is None:
                output.append(line)
                continue

            include_name = match.group("name").strip()
            quoted = match.group("open") == '"'

            include_path = self.find_include(
                include_name,
                quoted=quoted,
                current_dir=path.parent,
            )

            if include_path is None:
                # bits/stdc++.h、vectorなど、
                # ローカルライブラリ内にないincludeは残す。
                output.append(line)
                continue

            if not self.should_expand(include_path):
                # ローカルに存在するが、
                # #pragma kbuild expand がないものは残す。
                output.append(line)
                continue

            output.extend(
                self._bundle_file(include_path)
            )

        if not is_root:
            if output and not output[-1].endswith("\n"):
                output.append("\n")

            output.append(
                "// ===== kbuild end: "
                f"{self._display_path(path)} =====\n"
            )

        self.expansion_stack.pop()
        return output

    def _display_path(self, path: Path) -> str:
        path = path.resolve()

        for include_dir in self.include_dirs:
            try:
                return str(
                    path.relative_to(include_dir)
                )
            except ValueError:
                continue

        return str(path)


def compile_source(
    source: Path,
    executable: Path,
    *,
    compiler: str,
    standard: str,
    extra_flags: list[str],
) -> None:
    executable.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        compiler,
        f"-std={standard}",
        "-O2",
        "-Wall",
        "-Wextra",
        *extra_flags,
        str(source),
        "-o",
        str(executable),
    ]

    info("checking compilation")

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    if result.returncode != 0:
        print(
            result.stdout,
            end="",
            file=sys.stderr,
        )
        fail(
            "compile failed",
            code=result.returncode,
        )

    ok(f"compiled: {executable}")


def split_arguments(
    argv: list[str],
) -> tuple[list[str], list[str]]:
    """
    `--` より前をkbuildの引数、
    `--` より後をコンパイラ引数として分離する。

    例:

        kbuild a.cpp -o sol.cpp -- -Wshadow -Wconversion
    """

    if "--" not in argv:
        return argv, []

    index = argv.index("--")

    return (
        argv[:index],
        argv[index + 1:],
    )


def parse_args(
    argv: list[str],
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="kbuild",
        description=(
            "Bundle opted-in local C++ headers "
            "and compile-check the result."
        ),
    )

    parser.add_argument(
        "source",
        type=Path,
        help="source file, e.g. a.cpp",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help=(
            "bundled source path "
            "(default: .build/<source>-submission.cpp)"
        ),
    )

    parser.add_argument(
        "-I",
        "--include",
        action="append",
        type=Path,
        default=[],
        help="additional local include directory",
    )

    parser.add_argument(
        "--library-root",
        type=Path,
        default=DEFAULT_LIBRARY_ROOT,
        help=(
            "library root "
            f"(default: {DEFAULT_LIBRARY_ROOT})"
        ),
    )

    parser.add_argument(
        "--compiler",
        default="g++",
        help="C++ compiler (default: g++)",
    )

    parser.add_argument(
        "--std",
        default="gnu++23",
        help="C++ standard (default: gnu++23)",
    )

    parser.add_argument(
        "--no-compile",
        action="store_true",
        help=(
            "generate the bundled source "
            "without compiling it"
        ),
    )

    parser.add_argument(
        "--print",
        action="store_true",
        dest="print_output",
        help=(
            "write bundled source to stdout "
            "instead of a file"
        ),
    )

    return parser.parse_args(argv)


def main() -> None:
    kbuild_argv, compiler_flags = split_arguments(
        sys.argv[1:]
    )

    args = parse_args(kbuild_argv)

    source = args.source.expanduser().resolve()

    if not source.is_file():
        fail(f"source not found: {source}")

    library_root = (
        args.library_root
        .expanduser()
        .resolve()
    )

    include_dirs = default_include_dirs(
        library_root
    )
    include_dirs.extend(args.include)

    if not include_dirs:
        info(
            "library directory not found: "
            f"{library_root}"
        )

    bundler = CppBundler(include_dirs)
    bundled = bundler.bundle(source)

    if args.print_output:
        sys.stdout.write(bundled)
        return

    if args.output is None:
        output = (
            source.parent
            / ".build"
            / f"{source.stem}-submission.cpp"
        )
    else:
        output = args.output.expanduser()

        if not output.is_absolute():
            output = Path.cwd() / output

    output = output.resolve()

    if output == source:
        fail(
            "output path must differ "
            "from source path"
        )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    output.write_text(
        bundled,
        encoding="utf-8",
    )

    ok(f"generated: {output}")

    if args.no_compile:
        return

    compiler = require_command(args.compiler)

    executable = (
        output.parent
        / f"{output.stem}.out"
    )

    compile_source(
        output,
        executable,
        compiler=compiler,
        standard=args.std,
        extra_flags=compiler_flags,
    )


if __name__ == "__main__":
    main()