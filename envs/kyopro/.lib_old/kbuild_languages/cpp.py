#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


MENV_ROOT = Path(
    os.environ.get(
        "MENV_ROOT",
        Path.home() / ".menv",
    )
)
KYOPRO_ROOT = MENV_ROOT / "envs" / "kyopro"

sys.path.insert(
    0,
    str(MENV_ROOT / ".lib"),
)
sys.path.insert(
    0,
    str(KYOPRO_ROOT / ".lib"),
)

from common import fail, info, ok


DEFAULT_LIBRARY_ROOT = Path(
    os.environ.get(
        "KYOPRO_LIBRARY",
        Path.home() / "library",
    )
)

EXTENSIONS = {
    ".cpp",
}
DEFAULT_HANDLER = True

EXPAND_PRAGMA = "#pragma kbuild expand"

INCLUDE_PATTERN = re.compile(
    r"^(?P<indent>\s*)"
    r"#\s*include\s*"
    r'(?P<open>[<"])'
    r"(?P<name>[^>\"]+)"
    r'[>"]'
    r"(?P<tail>.*)$"
)

BITS_HEADER = "bits/stdc++.h"

BITS_INCLUDED_HEADERS = {
    # C
    "cassert",
    "cctype",
    "cerrno",
    "cfenv",
    "cfloat",
    "cinttypes",
    "climits",
    "clocale",
    "cmath",
    "csetjmp",
    "csignal",
    "cstdarg",
    "cstddef",
    "cstdint",
    "cstdio",
    "cstdlib",
    "cstring",
    "ctime",
    "cuchar",
    "cwchar",
    "cwctype",

    # C++
    "algorithm",
    "any",
    "array",
    "atomic",
    "barrier",
    "bit",
    "bitset",
    "charconv",
    "chrono",
    "codecvt",
    "compare",
    "complex",
    "concepts",
    "condition_variable",
    "coroutine",
    "deque",
    "exception",
    "expected",
    "filesystem",
    "format",
    "forward_list",
    "fstream",
    "functional",
    "future",
    "iomanip",
    "initializer_list",
    "ios",
    "iosfwd",
    "iostream",
    "istream",
    "iterator",
    "latch",
    "limits",
    "list",
    "locale",
    "map",
    "memory",
    "memory_resource",
    "mutex",
    "new",
    "numbers",
    "numeric",
    "optional",
    "ostream",
    "queue",
    "random",
    "ranges",
    "ratio",
    "regex",
    "scoped_allocator",
    "semaphore",
    "set",
    "shared_mutex",
    "source_location",
    "span",
    "sstream",
    "stack",
    "stdatomic.h",
    "stdexcept",
    "stop_token",
    "streambuf",
    "string",
    "string_view",
    "syncstream",
    "system_error",
    "thread",
    "tuple",
    "type_traits",
    "typeindex",
    "typeinfo",
    "unordered_map",
    "unordered_set",
    "utility",
    "valarray",
    "variant",
    "vector",
    "version",
}


def require_command(name: str) -> str:
    path = shutil.which(name)

    if path is None:
        fail(f"{name} not found")

    return path


def find_contest_root(
    start: Path,
) -> Path | None:
    current = start.resolve()

    while True:
        if (current / ".contest").exists():
            return current

        if current.parent == current:
            return None

        current = current.parent


def default_output_path(
    source: Path,
) -> Path:
    contest_root = find_contest_root(
        source.parent
    )

    if contest_root is None:
        build_root = source.parent / ".build"
        problem = (
            source.parent.name
            if source.stem == "main"
            else source.stem
        )
    else:
        build_root = contest_root / ".build"
        relative = source.relative_to(
            contest_root
        )
        problem = (
            relative.parts[0]
            if len(relative.parts) > 1
            else source.stem
        )

    return build_root / problem / "sol.cpp"


def default_include_dirs(
    library_root: Path,
) -> list[Path]:
    """
    検索対象:

      ~/library/mone-library
      ~/library/ac-library
    """

    candidates = [
        library_root / "mone-library",
        library_root / "ac-library",
    ]

    return [
        path.expanduser().resolve()
        for path in candidates
        if path.is_dir()
    ]


class CppBundler:
    def __init__(
        self,
        include_dirs: list[Path],
    ) -> None:
        self.include_dirs = self._unique_paths(
            include_dirs
        )

        self.expanded: set[Path] = set()
        self.expansion_stack: list[Path] = []
        self.expandable_cache: dict[Path, bool] = {}
        self.emitted_includes: set[str] = set()

    @staticmethod
    def _unique_paths(
        paths: list[Path],
    ) -> list[Path]:
        result: list[Path] = []
        seen: set[Path] = set()

        for path in paths:
            resolved = path.expanduser().resolve()

            if resolved in seen:
                continue

            seen.add(resolved)
            result.append(resolved)

        return result

    @staticmethod
    def _normalize_blank_lines(
        source: str,
    ) -> str:
        """
        連続する空行を1行にまとめる。

        競プロ提出用コードを想定しているため、
        raw string literal 内の連続空行も変化する。
        """

        output: list[str] = []
        previous_blank = False

        for line in source.splitlines(
            keepends=True
        ):
            blank = line.strip() == ""

            if blank and previous_blank:
                continue

            output.append(line)
            previous_blank = blank

        return "".join(output)

    def find_include(
        self,
        name: str,
        *,
        quoted: bool,
        current_dir: Path,
    ) -> Path | None:
        candidates: list[Path] = []

        # #include "foo" は、まずinclude元と
        # 同じディレクトリを探す。
        if quoted:
            candidates.append(
                current_dir / name
            )

        # コンパイラの -I 相当の検索。
        for include_dir in self.include_dirs:
            candidates.append(
                include_dir / name
            )

        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()

        return None

    def should_expand(
        self,
        path: Path,
    ) -> bool:
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

    def bundle(
        self,
        source: Path,
    ) -> str:
        source = source.expanduser().resolve()

        if not source.is_file():
            fail(f"source not found: {source}")

        # 同じインスタンスで複数回実行可能にする。
        self.expanded.clear()
        self.expansion_stack.clear()
        self.emitted_includes.clear()

        bundled = "".join(
            self._bundle_file(
                source,
                is_root=True,
            )
        )

        bundled = (
            self._normalize_standard_includes(
                bundled
            )
        )
        bundled = self._normalize_blank_lines(
            bundled
        )

        return bundled

    def _bundle_file(
        self,
        path: Path,
        *,
        is_root: bool = False,
    ) -> list[str]:
        path = path.resolve()

        # 同じ展開対象ヘッダは一度だけ展開する。
        if (
            not is_root
            and path in self.expanded
        ):
            return []

        # A -> B -> A のような循環を検出。
        if path in self.expansion_stack:
            chain = " -> ".join(
                self._display_path(item)
                for item in [
                    *self.expansion_stack,
                    path,
                ]
            )
            fail(
                f"cyclic include detected: {chain}"
            )

        if not is_root:
            self.expanded.add(path)

        self.expansion_stack.append(path)

        try:
            try:
                lines = path.read_text(
                    encoding="utf-8"
                ).splitlines(
                    keepends=True
                )
            except UnicodeDecodeError:
                fail(
                    f"file is not UTF-8: {path}"
                )
            except OSError as error:
                fail(
                    f"failed to read {path}: "
                    f"{error}"
                )

            output: list[str] = []

            for line in lines:
                stripped = line.strip()

                # 展開されるヘッダではpragmaを除去。
                if (
                    not is_root
                    and stripped
                    in {
                        "#pragma once",
                        EXPAND_PRAGMA,
                    }
                ):
                    continue

                match = INCLUDE_PATTERN.match(line)

                if match is None:
                    output.append(line)
                    continue

                include_name = (
                    match.group("name").strip()
                )
                quoted = (
                    match.group("open") == '"'
                )

                include_path = self.find_include(
                    include_name,
                    quoted=quoted,
                    current_dir=path.parent,
                )

                # 標準ヘッダなど、検索対象外のinclude。
                if include_path is None:
                    output.extend(
                        self._emit_include_once(
                            line,
                            include_name,
                            quoted=quoted,
                        )
                    )
                    continue

                # 展開pragmaがないファイルは
                # include文のまま残す。
                if not self.should_expand(
                    include_path
                ):
                    output.extend(
                        self._emit_include_once(
                            line,
                            include_name,
                            quoted=quoted,
                        )
                    )
                    continue

                output.extend(
                    self._bundle_file(
                        include_path
                    )
                )

            if not is_root:
                # pragma削除後の先頭空行を除去。
                while (
                    output
                    and output[0].strip() == ""
                ):
                    output.pop(0)

                # ヘッダ末尾の余分な空行を除去。
                while (
                    output
                    and output[-1].strip() == ""
                ):
                    output.pop()

                # ファイル末尾に改行がなければ補う。
                if (
                    output
                    and not output[-1].endswith(
                        "\n"
                    )
                ):
                    output[-1] += "\n"

                # 次のコードとの間に空行を1行入れる。
                if output:
                    output.append("\n")

            return output

        finally:
            self.expansion_stack.pop()

    def _emit_include_once(
        self,
        line: str,
        include_name: str,
        *,
        quoted: bool,
    ) -> list[str]:
        """
        同じinclude文を2回以上出力しない。

        <foo> と "foo" は別のincludeとして扱う。
        """

        opening = '"' if quoted else "<"
        key = f"{opening}{include_name}"

        if key in self.emitted_includes:
            return []

        self.emitted_includes.add(key)
        return [line]

    def _normalize_standard_includes(
        self,
        source: str,
    ) -> str:
        """
        bits/stdc++.h が存在する場合、
        bits/stdc++.h に含まれる個別の標準ヘッダを
        最終出力から削除する。

        includeの出現順には依存しない。
        """

        lines = source.splitlines(
            keepends=True
        )

        has_bits = any(
            self._get_angle_include_name(line)
            == BITS_HEADER
            for line in lines
        )

        if not has_bits:
            return source

        output: list[str] = []

        for line in lines:
            include_name = (
                self._get_angle_include_name(line)
            )

            if (
                include_name
                in BITS_INCLUDED_HEADERS
            ):
                continue

            output.append(line)

        return "".join(output)

    @staticmethod
    def _get_angle_include_name(
        line: str,
    ) -> str | None:
        """
        #include <foo> なら foo を返す。

        #include "foo" または通常行なら None。
        """

        match = INCLUDE_PATTERN.match(line)

        if match is None:
            return None

        if match.group("open") != "<":
            return None

        return match.group("name").strip()

    def _display_path(
        self,
        path: Path,
    ) -> str:
        path = path.resolve()

        for include_dir in self.include_dirs:
            try:
                return str(
                    path.relative_to(
                        include_dir
                    )
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

        kbuild a.cpp -o sol.cpp -- -Wshadow
    """

    if "--" not in argv:
        return argv, []

    index = argv.index("--")

    return (
        argv[:index],
        argv[index + 1 :],
    )


def create_parser(
    *,
    add_help: bool = True,
    exit_on_error: bool = True,
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kbuild",
        add_help=add_help,
        exit_on_error=exit_on_error,
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
            "(default: "
            ".build/<problem>/sol.cpp)"
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

    return parser


def parse_args(
    argv: list[str],
) -> argparse.Namespace:
    return create_parser().parse_args(argv)


def detect_source(
    argv: list[str],
) -> Path | None:
    kbuild_argv, _ = split_arguments(argv)

    try:
        args = create_parser(
            add_help=False,
            exit_on_error=False,
        ).parse_args(kbuild_argv)
    except (argparse.ArgumentError, SystemExit):
        return None

    source = args.source.expanduser()

    if source.suffix not in EXTENSIONS:
        return None

    return source


def main(
    argv: list[str] | None = None,
) -> None:
    arguments = (
        sys.argv[1:]
        if argv is None
        else argv
    )
    kbuild_argv, compiler_flags = (
        split_arguments(arguments)
    )

    args = parse_args(kbuild_argv)

    source = args.source.expanduser().resolve()

    if not source.is_file():
        fail(f"source not found: {source}")

    if source.suffix not in EXTENSIONS:
        fail(
            "C++ handler does not support source: "
            f"{source}"
        )

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
        output = default_output_path(source)
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

    compiler = require_command(
        args.compiler
    )

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