import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.lib'))
import mcheck
import releases


class McheckTests(unittest.TestCase):
    def test_global_dependencies_are_check_only_even_when_installing(self):
        result = mcheck.CheckResult()
        with patch.object(mcheck.check, 'apt_global_package_exists', return_value=False), patch.object(mcheck, 'run_quiet') as run:
            mcheck.check_system_packages({'check': {'packages': ['g++']}, 'system': {'packages': ['legacy']}}, install=True, result=result)
        run.assert_not_called()
        self.assertEqual(result.ng, 2)

    def test_check_only_missing_commands_do_not_suggest_mcheck_install(self):
        with patch.object(mcheck.check, 'find_command', return_value=None), redirect_stdout(io.StringIO()) as out:
            mcheck.check_commands(Path('/tmp/env'), {'check': {'commands': ['g++']}}, venv_rel='.venv', result=mcheck.CheckResult())
        self.assertIn('manually', out.getvalue())
        self.assertNotIn('--install', out.getvalue())

    def test_local_path_rejects_absolute_parent_and_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); env = root / 'env'; env.mkdir()
            for path in ('/tmp/external', '../other', '.'):
                with self.assertRaises(ValueError): releases.validate_local_venv(env, path)
            (env / '.venv').symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError): releases.validate_local_venv(env, '.venv')

    def test_fake_venv_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp); (env / '.venv/bin').mkdir(parents=True)
            (env / '.venv/bin/python').symlink_to(sys.executable)
            with self.assertRaises(ValueError): releases.validate_local_venv(env, '.venv')
            (env / '.venv/pyvenv.cfg').write_text('include-system-site-packages = true\n')
            with self.assertRaises(ValueError): releases.validate_local_venv(env, '.venv')

    def test_tools_symlink_escape_rejected_before_hooks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); env = root / 'env'; env.mkdir()
            (env / '.tools').mkdir(); (env / '.tools/tool').symlink_to(root)
            with patch.object(mcheck, 'load_toml', return_value={}), patch.object(mcheck, 'check_tools') as hooks:
                with self.assertRaises(ValueError): mcheck.check_env(env, install=True)
                hooks.assert_not_called()

    def test_github_version_prefix_and_request(self):
        response = io.BytesIO(json.dumps({'tag_name': 'v2026.08.19', 'draft': False, 'prerelease': False}).encode())
        with patch('urllib.request.urlopen', return_value=response) as get:
            self.assertEqual(releases.latest_release('https://github.com/yt-dlp/yt-dlp'), '2026.08.19')
        self.assertEqual(get.call_args.args[0].full_url, 'https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest')

    def test_bad_repo_and_tag_rejected(self):
        with self.assertRaises(ValueError): releases.latest_release('https://example.com/a/b')
        response = io.BytesIO(b'{"tag_name":"--target=/usr/lib", "draft":false}')
        with patch('urllib.request.urlopen', return_value=response):
            with self.assertRaises(ValueError): releases.latest_release('https://github.com/a/b')

    def github_case(self, *, update, newer=True, fail=False):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp); (env / '.venv/bin').mkdir(parents=True); (env / '.venv/bin/python').touch()
            conf = {'venv': {'packages': ['yt-dlp']}, 'update': {'github': [{'package': 'yt-dlp', 'repository': 'https://github.com/yt-dlp/yt-dlp'}]}}
            result = mcheck.CheckResult()
            with patch.object(releases, 'validate_local_venv', return_value=env / '.venv'), patch.object(releases, 'latest_release', side_effect=OSError('offline') if fail else None, return_value='2026.08.19'), patch.object(releases, 'package_versions', side_effect=[('2026.01.01', newer), ('2026.8.19', False)]), patch.object(releases, 'run_quiet', return_value=True) as run:
                releases.check_github_updates(env, conf, venv_rel='.venv', update=update, result=result)
                return result, run.call_args_list

    def test_github_check_does_not_install(self):
        result, calls = self.github_case(update=False)
        self.assertEqual(result.ng, 1); self.assertEqual(calls, [])

    def test_github_update_installs_exact_version_locally(self):
        result, calls = self.github_case(update=True)
        self.assertEqual(result.ng, 0)
        command = calls[0].args[1]
        self.assertIn('yt-dlp==2026.08.19', command)
        self.assertIn('--no-user', command)
        self.assertTrue(command[0].endswith('.venv/bin/python'))

    def test_github_same_or_newer_version_skips_install(self):
        result, calls = self.github_case(update=True, newer=False)
        self.assertEqual(result.ng, 0); self.assertEqual(calls, [])

    def test_github_network_error_never_installs(self):
        result, calls = self.github_case(update=True, fail=True)
        self.assertEqual(result.ng, 1); self.assertEqual(calls, [])

    def test_bootstrap_without_python_never_attempts_global_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                ['/bin/bash', str(ROOT / '.bin/mcheck'), '--sync'],
                env={'PATH': tmp, 'MENV_ROOT': str(ROOT)}, capture_output=True, text=True,
            )
        self.assertEqual(completed.returncode, 1)
        self.assertIn('install it manually', completed.stderr)
        self.assertNotIn('sudo', completed.stderr)

    def test_sync_preserves_check_only_boundary_in_complete_run(self):
        conf = {'check': {'packages': ['g++'], 'commands': ['g++']}}
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mcheck, 'load_toml', return_value=conf), patch.object(mcheck.check, 'apt_global_package_exists', return_value=False), patch.object(mcheck.check, 'find_command', return_value=None), patch.object(mcheck, 'run_quiet') as run:
                self.assertFalse(mcheck.check_env(Path(tmp), install=True, update=True))
                run.assert_not_called()

    def test_real_local_venv_ignores_pip_target_and_compares_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp); venv = env / '.venv'
            subprocess.run([sys.executable, '-m', 'venv', str(venv)], check=True)
            self.assertEqual(releases.validate_local_venv(env, '.venv'), venv)
            current, newer = releases.package_versions(venv, 'pip', '999.0')
            self.assertTrue(newer)
            target = env / 'external'
            with patch.dict(os.environ, {'PIP_TARGET': str(target), 'PIP_PREFIX': '/usr', 'PIP_USER': 'true'}):
                command = releases.pip_command(venv, 'config', 'debug')
                output = subprocess.run(command, capture_output=True, text=True, check=True).stdout
            self.assertNotIn('PIP_TARGET', output); self.assertNotIn('PIP_PREFIX', output)
            self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
