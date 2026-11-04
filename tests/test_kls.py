import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class KlsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.menv = self.root / 'menv'
        kyopro = self.menv / 'envs/kyopro'
        (kyopro / '.venv/bin').mkdir(parents=True)
        (kyopro / '.venv/bin/python').symlink_to(sys.executable)
        (kyopro / '.lib').symlink_to(ROOT / 'envs/kyopro/.lib', target_is_directory=True)
        self.env = dict(os.environ, MENV_ROOT=str(self.menv))

    def cli(self, *args, cwd=None):
        return subprocess.run(
            [str(ROOT / 'envs/kyopro/.bin/kls'), *args],
            cwd=cwd or self.root, env=self.env, capture_output=True, text=True,
        )

    def test_lists_direct_contests_in_name_order_without_recursing(self):
        for name, site in (('practice', 'local'), ('abc400', 'atcoder'), ('2267', 'codeforces')):
            path = self.root / name
            path.mkdir()
            (path / '.contest').write_text(f'version = 1\nsite = "{site}"\nid = "{name}"\nurl = "{site}://{name}"\n')
        nested = self.root / 'other/nested'
        nested.mkdir(parents=True)
        (nested / '.contest').touch()
        (self.root / 'ordinary.txt').touch()
        (self.root / 'not-contest/.contest').mkdir(parents=True)
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '2267\nabc400\npractice\n')
        self.assertEqual(result.stderr, '')
        result = self.cli(cwd=self.root / 'practice')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')

    def test_empty_directory_prints_nothing(self):
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')

    def test_lists_workspace_created_by_knew(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / 'envs/kyopro/.lib/knew.py'), 'practice', '--manual', '-p', 'a,b,c'],
            cwd=self.root, env=self.env, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'practice\n')

    def test_help_and_invalid_arguments(self):
        result = self.cli('--help')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('usage: kls', result.stdout)
        self.assertEqual(self.cli('unexpected').returncode, 2)


if __name__ == '__main__':
    unittest.main()
