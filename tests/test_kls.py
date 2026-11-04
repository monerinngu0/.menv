import errno
import fcntl
import os
import pty
import struct
import subprocess
import sys
import tempfile
import termios
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
        self.env = dict(os.environ, MENV_ROOT=str(self.menv), LC_ALL='C')

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

    def test_invalid_old_and_unreadable_metadata_are_skipped(self):
        valid = 'version = 1\nsite = "local"\nid = "test"\nurl = "local://test"\n'
        cases = [
            b'', b'not valid toml',
            valid.replace('version = 1', 'version = 0').encode(),
            valid.replace('version = 1\n', '').encode(),
            valid.replace('url = "local://test"', 'url = ""').encode(),
            (valid + '[[problems]]\nlabel = "a"\nid = "a"\n').encode(),
            (valid + '[[problems]]\nlabel = "a"\nid = "a"\nurl = "local://test/a"\n' * 2).encode(),
            b'\xff\xfe',
        ]
        for index, content in enumerate(cases):
            path = self.root / f'invalid{index}'
            path.mkdir()
            (path / '.contest').write_bytes(content)
        good = self.root / 'valid'
        good.mkdir()
        (good / '.contest').write_text(valid)
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'valid\n')
        self.assertEqual(result.stderr, '')

    def test_terminal_output_uses_multiple_columns_and_rows(self):
        names = [f'contest{i}' for i in range(8)]
        for name in names:
            path = self.root / name
            path.mkdir()
            (path / '.contest').write_text('version = 1\nsite = "local"\nid = "test"\nurl = "local://test"\n')
        master, slave = pty.openpty()
        try:
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 32, 0, 0))
            result = subprocess.run(
                [str(ROOT / 'envs/kyopro/.bin/kls')],
                cwd=self.root, env=dict(self.env, COLUMNS='32'), stdout=slave,
                stderr=subprocess.PIPE, text=True,
            )
        finally:
            os.close(slave)
        output = bytearray()
        try:
            while True:
                try:
                    chunk = os.read(master, 4096)
                except OSError as error:
                    if error.errno == errno.EIO:
                        break
                    raise
                if not chunk:
                    break
                output.extend(chunk)
        finally:
            os.close(master)
        self.assertEqual(result.returncode, 0, result.stderr)
        text = output.decode()
        self.assertEqual(sorted(text.split()), names)
        self.assertGreater(len(text.splitlines()), 1)
        self.assertLess(len(text.splitlines()), len(names))

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
