import importlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'envs/kyopro/.lib'))
import knew
from contest import Problem, load_contest
from sites import SiteError
from sites import local


class KnewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = dict(os.environ, MENV_ROOT=str(self.root / 'menv'))

    def cli(self, *args, command='knew', cwd=None):
        return subprocess.run(
            [sys.executable, str(ROOT / f'envs/kyopro/.lib/{command}.py'), *map(str, args)],
            cwd=cwd or self.root, env=self.env, capture_output=True, text=True,
        )

    def test_manual_cli_preserves_labels_and_creates_only_metadata_and_directories(self):
        # Manual creation must not load config or any online site module.
        with patch.object(sys, 'argv', ['knew', 'practice', '--manual', '--problems', 'a', 'B', 'ex', '-d', str(self.root)]), patch.object(knew, 'load_config', side_effect=AssertionError('config loaded')), patch('importlib.import_module', wraps=importlib.import_module) as imported, redirect_stdout(io.StringIO()):
            knew.main()
        imported.assert_called_once_with('sites.local')
        root = self.root / 'practice'
        contest = load_contest(root)
        self.assertEqual((contest.version, contest.site, contest.id, contest.url), (1, 'local', 'practice', 'local://practice'))
        self.assertEqual([(p.label, p.id, p.url) for p in contest.problems], [(label, label, f'local://practice/{label}') for label in ('a', 'B', 'ex')])
        self.assertEqual({p.name for p in root.iterdir()}, {'.contest', 'a', 'B', 'ex'})
        for label in ('a', 'B', 'ex'):
            self.assertEqual(list((root / label).iterdir()), [])

    def test_invalid_argument_combinations_create_nothing(self):
        for args in (
            ('--manual',), ('--manual', '--problems'),
            ('--problems', 'a'),
            ('--manual', '--problems', 'a', '--site', 'local'),
            ('--manual', '--problems', 'a', '--download'),
            ('--manual', '--problems', 'a', '--no-download'),
        ):
            with self.subTest(args=args):
                result = self.cli('practice', *args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse((self.root / 'practice').exists())

    def test_invalid_names_and_duplicate_labels_are_checked_before_creation(self):
        for name in ('', ' ', '.', '..', '../escape', '/absolute', 'a/b', 'a\\b', 'a\0b'):
            with self.subTest(contest=name), self.assertRaises(SiteError):
                local.create_contest(name, destination=self.root / 'parent', labels=['a'])
            with self.subTest(problem=name), self.assertRaises(SiteError):
                local.create_contest('practice', destination=self.root / 'parent', labels=['a', name])
        for labels in ([], ['a', 'a'], ['a', '.contest'], ['a', '.build']):
            with self.subTest(labels=labels), self.assertRaises(SiteError):
                local.create_contest('practice', destination=self.root / 'parent', labels=labels)
        self.assertFalse((self.root / 'parent').exists())

    def test_existing_directory_file_and_dangling_symlink_are_preserved(self):
        target = self.root / 'practice'
        target.mkdir()
        marker = target / 'keep'
        marker.write_text('unchanged')
        result = self.cli('practice', '--manual', '--problems', 'a')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(marker.read_text(), 'unchanged')
        self.assertEqual(list(target.iterdir()), [marker])
        marker.unlink()
        target.rmdir()
        target.write_text('unchanged')
        with self.assertRaises(SiteError):
            local.create_contest('practice', destination=self.root, labels=['a'])
        self.assertEqual(target.read_text(), 'unchanged')
        target.unlink()
        target.symlink_to(self.root / 'missing')
        with self.assertRaises(SiteError):
            local.create_contest('practice', destination=self.root, labels=['a'])
        self.assertTrue(target.is_symlink())

    def test_manual_workspace_supports_testing_building_and_submission_fallback(self):
        (self.root / 'menv').mkdir()
        (self.root / 'menv/.lib').symlink_to(ROOT / '.lib', target_is_directory=True)
        parent = self.root / 'contests'
        result = self.cli('practice', '--manual', '--problems', 'a', '-d', parent)
        self.assertEqual(result.returncode, 0, result.stderr)
        root = parent / 'practice'
        source = root / 'a.py'
        source.write_text('print(int(input()) * 2)\n')
        (root / 'a/in1').write_text('21\n')
        (root / 'a/out1').write_text('42\n')
        result = self.cli('a', command='ktest', cwd=root / 'a')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('all tests passed', result.stdout)
        result = self.cli('a.py', command='kbuild', cwd=root)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = root / '.build/a/sol.py'
        self.assertEqual(output.read_bytes(), source.read_bytes())

        config = self.root / 'menv/envs/kyopro/.config'
        config.parent.mkdir(parents=True)
        copied = self.root / 'copied.py'
        writer = 'import pathlib,sys; pathlib.Path(sys.argv[1]).write_bytes(sys.stdin.buffer.read())'
        config.write_text('[clipboard]\nmethod = "command"\ncommand = ' + json.dumps([sys.executable, '-c', writer, str(copied)]) + '\n')
        result = self.cli('a', '--test', command='ksub', cwd=root)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('automatic submission unavailable', result.stderr)
        self.assertEqual(copied.read_bytes(), output.read_bytes())

    def test_online_creation_keeps_fetch_download_and_config_defaults(self):
        problem = Problem('a', 'abc001_1', 'https://example.com/a')
        site = SimpleNamespace(fetch_problems=Mock(return_value=(problem,)), contest_url=Mock(return_value='https://example.com/abc001'), download_testcases=Mock())
        config = SimpleNamespace(defaults=SimpleNamespace(site='atcoder'), knew=SimpleNamespace(download_samples=True))
        for name, options, download in (('abc001', [], True), ('abc002', ['--no-download'], False)):
            with self.subTest(options=options), patch.object(sys, 'argv', ['knew', name, '-d', str(self.root), *options]), patch.object(knew, 'load_config', return_value=config) as load, patch.object(knew, 'get_site', return_value=site) as get, redirect_stdout(io.StringIO()):
                site.download_testcases.reset_mock()
                knew.main()
                load.assert_called_once_with()
                get.assert_called_once_with('atcoder')
                site.fetch_problems.assert_called_with(name)
                self.assertEqual(load_contest(self.root / name).site, 'atcoder')
                self.assertEqual(site.download_testcases.called, download)


if __name__ == '__main__':
    unittest.main()
