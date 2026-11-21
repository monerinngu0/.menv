import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class KbuildAsmTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.lib = self.root / "library"
        self.lib.mkdir()
        self.config = self.root / "menv/envs/kyopro/.config"
        self.config.parent.mkdir(parents=True)
        self.config.write_text(
            '[cpp]\ninclude_dirs = ["missing-cpp-dir"]\n'
            '[asm]\ninclude_dirs = ["library"]\n',
            encoding="utf-8",
        )
        self.source = self.root / "a.asm"
        self.output = self.root / "sol.asm"

    def build(self):
        return subprocess.run(
            [sys.executable, str(ROOT / "envs/kyopro/.lib/kbuild.py"), "a.asm"],
            cwd=self.root,
            env=dict(os.environ, MENV_ROOT=str(self.root / "menv")),
            capture_output=True,
            text=True,
        )

    def test_expand_shared_dependency_at_each_include_site(self):
        self.source.write_text(
            '%ifdef DEBUG\n%include "debug.inc"\n%endif\n'
            '%include "sum.inc" ; needed even with DEBUG off\n',
            encoding="utf-8",
        )
        self.lib.joinpath("debug.inc").write_text('%include "common.inc"\n', encoding="utf-8")
        self.lib.joinpath("sum.inc").write_text("%include 'common.inc'\n", encoding="utf-8")
        common = "%ifndef COMMON_INC\n%define COMMON_INC\n%define VALUE 42\n%endif\n"
        self.lib.joinpath("common.inc").write_text(common, encoding="utf-8")

        result = self.build()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.output.read_text(encoding="utf-8"),
            f"%ifdef DEBUG\n{common}%endif\n{common}",
        )

    def test_include_errors_preserve_previous_output(self):
        self.output.write_text("previous output\n", encoding="utf-8")
        self.lib.joinpath("cycle.inc").write_text('%include "a.asm"\n', encoding="utf-8")

        for directive, error in (
            ('%include "missing.inc"', "a.asm:1: include not found: missing.inc"),
            ("%include HEADER", "a.asm:1: expected a single-line %include"),
            ('%include "cycle.inc"', "cycle.inc:1: cyclic %include:"),
        ):
            with self.subTest(directive=directive):
                self.source.write_text(directive + "\n", encoding="utf-8")
                result = self.build()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(error, result.stderr)
                self.assertEqual(self.output.read_text(encoding="utf-8"), "previous output\n")
