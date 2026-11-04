"""End-to-end setup tests; installers and remote downloads never reach the network."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'envs/setup/.lib/main.py'
REGISTRY = 'https://example.invalid/registry/'


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='menv setup ')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'repo'
        self.root.mkdir()
        self.env = dict(os.environ, MENV_ROOT=str(self.root),
                        XDG_CACHE_HOME=str(self.base / 'cache'),
                        XDG_STATE_HOME=str(self.base / 'state'),
                        XDG_DATA_HOME=str(self.base / 'data'),
                        MENV_SETUP_REGISTRY=REGISTRY)
        self.state = self.base / 'state/menv/setup'
        self.cache = (self.base / 'cache/menv/setup/registries' /
                      hashlib.sha256(REGISTRY.encode()).hexdigest())

    def cli(self, *args, input=''):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)], env=self.env,
                              input=input, text=True, capture_output=True, timeout=20)

    def isolated(self, code):
        preamble = f'import sys; sys.path.insert(0, {str(CLI.parent)!r})\n'
        return subprocess.run([sys.executable, '-c', preamble + textwrap.dedent(code)],
                              env=self.env, text=True, capture_output=True, timeout=20)

    def definition(self, key='sample', *, init=None, update=None, extra='', steps=None):
        init = init or [[sys.executable, '-c', "from pathlib import Path; Path('initialized').touch()"]]
        update = update or [[sys.executable, '-c', "from pathlib import Path; Path('updated').touch()"]]
        raw = f'name = "{key}"\nversion = 1\ndescription = "test definition"\n{extra}\n'
        raw += '[init]\ndescription = "initialize"\n'
        if steps is not None:
            raw += steps + '\n'
        else:
            raw += 'commands = ' + json.dumps(init) + '\n'
        raw += '[update]\ndescription = "update"\ncommands = ' + json.dumps(update) + '\n'
        return raw.encode()

    def local(self, key='sample', **kwargs):
        folder = self.root / 'envs' / key
        folder.mkdir(parents=True, exist_ok=True)
        (folder / '.toml').write_bytes(self.definition(key, **kwargs))
        return folder

    def remote(self, key='sample', **kwargs):
        raw = self.definition(key, **kwargs)
        digest = hashlib.sha256(raw).hexdigest()
        target = self.cache / 'packages' / (digest + '.toml')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        index = {'packages': {key: {'version': 1, 'path': f'packages/{key}.toml', 'sha256': digest}}}
        (self.cache / 'index.json').write_text(json.dumps(index))
        return target

    def test_preview_and_default_denial_do_not_execute_or_register(self):
        folder = self.local()
        for args in [('init', 'sample', '--dry-run'), ('init', 'sample')]:
            result = self.cli(*args)
            self.assertIn('local:sample', result.stdout)
            self.assertFalse((folder / 'initialized').exists())
            self.assertFalse((self.state / 'installed.json').exists())
        self.assertEqual(self.cli('init', 'sample').returncode, 1)

    def test_confirmation_executes_and_registers(self):
        folder = self.local()
        result = self.cli('init', 'sample', input='y\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((folder / 'initialized').exists())
        state = json.loads((self.state / 'installed.json').read_text())
        self.assertEqual(set(state), {'local:sample'})
        self.assertEqual(state['local:sample']['workdir'], str(folder))

    def test_conditions_are_evaluated_in_sequence_and_init_can_repeat(self):
        steps = '''[[init.steps]]
run = ["{python}", "-c", "from pathlib import Path; Path('exists').touch()"]
[[init.steps]]
run = ["{python}", "-c", "raise SystemExit(41)"]
unless_path = "exists"
'''
        self.local(steps=steps)
        for _ in range(2):
            result = self.cli('init', 'sample', '-y')
            self.assertEqual(result.returncode, 0, result.stderr)
        history = [json.loads(line) for line in (self.state / 'history.jsonl').read_text().splitlines()]
        self.assertTrue(history[1]['skipped'])
        self.assertTrue(history[3]['skipped'])

    def test_failure_stops_commands_and_does_not_register(self):
        folder = self.local(init=[[sys.executable, '-c', 'raise SystemExit(23)'],
                                  [sys.executable, '-c', "from pathlib import Path; Path('bad').touch()"]])
        result = self.cli('init', 'sample', '-y')
        self.assertEqual(result.returncode, 23, result.stderr)
        self.assertIn('step 1', result.stderr)
        self.assertFalse((folder / 'bad').exists())
        self.assertFalse((self.state / 'installed.json').exists())

    def test_option_values_are_literal_single_arguments_and_saved(self):
        extra = '[options.message]\ndescription = "message"\n'
        script = "import sys; from pathlib import Path; Path('value').write_text(sys.argv[1])"
        commands = [[sys.executable, '-c', script, '{message}']]
        folder = self.local(init=commands, update=commands, extra=extra)
        value = "spaces; $(touch injected) ' {unknown} {{literal}}"
        result = self.cli('init', 'sample', '-y', '--set', 'message=' + value)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((folder / 'value').read_text(), value)
        self.assertFalse((folder / 'injected').exists())
        result = self.cli('update', '--all', '-y')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((folder / 'value').read_text(), value)

    def test_all_only_updates_initialized_sources(self):
        folder = self.local()
        other = self.local('unused')
        self.remote()
        remote_work = self.base / 'remote work'
        self.assertEqual(self.cli('init', 'sample', '-y').returncode, 0)
        result = self.cli('init', 'remote:sample', '--offline', '--workdir', remote_work, '-y')
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.cli('update', '--all', '--offline', '-y')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((folder / 'updated').exists())
        self.assertTrue((remote_work / 'updated').exists())
        self.assertFalse((other / 'updated').exists())
        state = json.loads((self.state / 'installed.json').read_text())
        self.assertEqual(state['remote:sample']['registry'], REGISTRY)

    def test_all_preflights_every_target_before_any_execution(self):
        folder = self.local('a')
        second = self.local('b')
        for key in ('a', 'b'):
            self.assertEqual(self.cli('init', key, '-y').returncode, 0)
        (second / '.toml').write_text('invalid toml')
        result = self.cli('update', '--all', '-y')
        self.assertEqual(result.returncode, 1)
        self.assertFalse((folder / 'updated').exists())

    def test_explicit_update_does_not_initialize(self):
        self.local()
        result = self.cli('update', 'sample', '-y')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.state / 'installed.json').exists())
        self.assertIn('No initialized targets', self.cli('update', '--all').stdout)

    def test_remote_cache_validates_hash_revision_and_source(self):
        target = self.remote()
        result = self.cli('info', 'remote:sample', '--offline')
        self.assertEqual(result.returncode, 0, result.stderr)
        target.write_bytes(target.read_bytes() + b'\n')
        result = self.cli('init', 'remote:sample', '--offline', '-y')
        self.assertIn('SHA-256 mismatch', result.stderr)
        self.assertEqual(result.returncode, 1)
        self.remote()
        index = json.loads((self.cache / 'index.json').read_text())
        index['packages']['sample']['version'] = 2
        (self.cache / 'index.json').write_text(json.dumps(index))
        self.assertIn('revision disagrees', self.cli('info', 'remote:sample', '--offline').stderr)
        result = self.cli('info', 'remote:sample', '--offline', '--registry', 'https://different.invalid/')
        self.assertEqual(result.returncode, 1)

    def test_registry_online_fetch_cache_reuse_and_offline_fallback(self):
        raw = self.definition()
        code = f'''
        import hashlib, json, urllib.error
        from pathlib import Path
        from unittest.mock import patch
        from remote import Registry
        raw = {raw!r}
        index = json.dumps({{"packages": {{"sample": {{"version": 1, "path": "packages/sample.toml", "sha256": hashlib.sha256(raw).hexdigest()}}}}}}).encode()
        cache = Path({str(self.base / 'network-cache')!r})
        r = Registry({REGISTRY!r}, cache)
        with patch.object(r, 'fetch', side_effect=[index, raw]) as fetch:
            assert r.load('sample').version == 1
            assert r.load('sample').version == 1
            assert fetch.call_count == 2
        r = Registry({REGISTRY!r}, cache)
        with patch.object(r, 'fetch', side_effect=urllib.error.URLError('offline')):
            assert r.load('sample').version == 1
        r = Registry({REGISTRY!r}, cache)
        with patch.object(r, 'fetch', return_value=b'invalid JSON'):
            try: r.load('sample')
            except ValueError: pass
            else: raise AssertionError('invalid metadata fell back silently')
        '''
        result = self.isolated(code)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('using cached', result.stderr)

    def test_invalid_definitions_inputs_and_traversal_never_run(self):
        folder = self.local()
        for target in ('local:../sample', 'local:/sample', 'other:sample'):
            self.assertEqual(self.cli('init', target, '-y').returncode, 1)
        self.assertEqual(self.cli('init', 'sample', '--set', 'bad=1', '-y').returncode, 1)
        for text in [self.definition().decode().replace('version = 1', 'version = true'),
                     self.definition().decode().replace('commands = ', 'typo = ', 1),
                     self.definition().decode().replace('initialize', '{missing}'),
                     self.definition(extra='[options.root]\ndescription = "reserved"\n').decode()]:
            (folder / '.toml').write_text(text)
            self.assertEqual(self.cli('init', 'sample', '-y').returncode, 1)
        self.assertFalse((folder / 'initialized').exists())

    def test_choice_required_options_and_unknown_placeholders(self):
        self.local(extra='[options.mode]\ndescription = "mode"\nchoices = ["a", "b"]\n')
        self.assertIn('required option', self.cli('init', 'sample', '-y').stderr)
        self.assertIn('invalid mode', self.cli('init', 'sample', '-y', '--set', 'mode=c').stderr)
        self.assertEqual(self.cli('init', 'sample', '-y', '--set', 'mode=b').returncode, 0)

    def test_lock_rejects_concurrent_execution(self):
        import fcntl
        self.local()
        self.state.mkdir(parents=True)
        with (self.state / '.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            result = self.cli('init', 'sample', '-y')
        self.assertIn('another setup', result.stderr)

    def test_approval_does_not_reload_changed_definition(self):
        folder = self.local()
        proc = subprocess.Popen([sys.executable, str(CLI), 'init', 'sample'],
                                env=self.env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: proc.kill() if proc.poll() is None else None)
        while True:
            line = proc.stdout.readline()
            self.assertTrue(line)
            if '1. (cwd ' in line:
                break
        (folder / '.toml').write_bytes(self.definition(init=[[sys.executable, '-c', 'raise SystemExit(39)']]))
        _, stderr = proc.communicate('y\n', timeout=20)
        self.assertEqual(proc.returncode, 0, stderr)
        self.assertTrue((folder / 'initialized').exists())

    def test_bootstrap_reuses_compatible_python_without_downloading(self):
        env = dict(self.env, MENV_ROOT=str(ROOT), MENV_PYTHON=sys.executable)
        result = subprocess.run(['bash', str(ROOT / 'bootstrap.sh')], env=env,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Python available', result.stdout)
        self.assertFalse((self.base / 'data/menv/runtime').exists())

    def test_bootstrap_download_branch_is_scoped_to_dedicated_runtime(self):
        runtime = self.base / 'data/menv/runtime'
        fakebin = self.base / 'fakebin'
        fakebin.mkdir()
        uv = self.base / 'uv-stub'
        uv.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$BOOTSTRAP_TEST_LOG"\n'
                      'case "$*" in *find*) printf "%s\\n" "$BOOTSTRAP_TEST_PYTHON" ;; esac\n')
        uv.chmod(0o755)
        installer = self.base / 'installer'
        installer.write_text('#!/bin/sh\nmkdir -p "$UV_UNMANAGED_INSTALL"\n'
                             'cp "$BOOTSTRAP_TEST_UV" "$UV_UNMANAGED_INSTALL/uv"\n')
        curl = fakebin / 'curl'
        curl.write_text('#!/bin/sh\nwhile [ "$1" != "-o" ]; do shift; done\n'
                        'cp "$BOOTSTRAP_TEST_INSTALLER" "$2"\n')
        curl.chmod(0o755)
        log = self.base / 'uv.log'
        env = dict(self.env, MENV_ROOT=str(ROOT), PATH=str(fakebin) + ':' + os.environ['PATH'],
                   BOOTSTRAP_TEST_LOG=str(log), BOOTSTRAP_TEST_PYTHON=sys.executable,
                   BOOTSTRAP_TEST_UV=str(uv), BOOTSTRAP_TEST_INSTALLER=str(installer))
        result = subprocess.run(['bash', str(ROOT / 'bootstrap.sh'), '--managed', '-y'],
                                env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((runtime / 'bin/python3').resolve(), Path(sys.executable).resolve())
        self.assertIn('python install --upgrade 3.13', log.read_text())

    def test_venv_helper_refuses_system_python_symlink(self):
        venv = self.base / '.venv'
        (venv / 'bin').mkdir(parents=True)
        (venv / 'bin/python').symlink_to(sys.executable)
        result = subprocess.run([sys.executable, str(ROOT / '.lib/venv_tools.py'), 'install', str(venv), 'pip'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('not an isolated venv', result.stderr)

    def test_expansion_escapes_templates_and_preserves_shell_variables(self):
        result = self.isolated('''
            from config import expand
            assert expand('{{value}} ${value} {value}', {'value': '{{user}}'}) == '{value} ${value} {{user}}'
        ''')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_bundled_neovim_installer_repeats_and_switches_versions(self):
        import tarfile
        distribution = self.base / 'nvim-linux-x86_64'
        (distribution / 'bin').mkdir(parents=True)
        binary = distribution / 'bin/nvim'
        binary.write_text('#!/bin/sh\necho mock-nvim\n')
        binary.chmod(0o755)
        archive = self.base / 'neovim.tar.gz'
        def foreign_owner(member):
            member.uid = member.gid = 1001
            member.uname = member.gname = 'release-builder'
            return member
        with tarfile.open(archive, 'w:gz') as output:
            output.add(distribution, arcname='nvim-linux-x86_64', filter=foreign_owner)
        fakebin = self.base / 'neovim-fakebin'
        fakebin.mkdir()
        curl = fakebin / 'curl'
        curl.write_text('#!/bin/sh\ncase "$*" in\n'
                        '  *api.github.com/repos/neovim/neovim/releases/latest*)\n'
                        '    printf \'{"tag_name":"v%s","draft":false,"prerelease":false}\\n\' "$NEOVIM_TEST_LATEST" ;;\n'
                        '  *) while [ "$1" != "-o" ]; do shift; done\n'
                        '     cp "$NEOVIM_TEST_ARCHIVE" "$2" ;;\nesac\n')
        curl.chmod(0o755)
        self.env.update(PATH=str(fakebin) + ':' + os.environ['PATH'],
                        NEOVIM_TEST_ARCHIVE=str(archive), NEOVIM_TEST_LATEST='0.12.6')
        raw = (ROOT / 'registry/packages/neovim.toml').read_bytes()
        import tomllib
        revision = tomllib.loads(raw.decode())['version']
        digest = hashlib.sha256(raw).hexdigest()
        (self.cache / 'packages').mkdir(parents=True)
        (self.cache / 'packages' / (digest + '.toml')).write_bytes(raw)
        (self.cache / 'index.json').write_text(json.dumps({'packages': {'neovim': {
            'version': revision, 'path': 'packages/neovim.toml', 'sha256': digest}}}))
        prefix = self.base / 'neovim install'
        result = self.cli('init', 'remote:neovim', '--offline', '-y', '--set', f'prefix={prefix}')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((prefix / 'bin/nvim').resolve(), prefix / '0.12.6/bin/nvim')
        for action, version in [('init', '0.11.7'), ('init', '0.11.7'), ('update', '0.12.0')]:
            result = self.cli(action, 'remote:neovim', '--offline', '-y',
                              '--set', f'version={version}', '--set', f'prefix={prefix}')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((prefix / 'bin/nvim').resolve(), prefix / version / 'bin/nvim')
            self.assertEqual((prefix / version / 'bin/nvim').stat().st_uid, os.getuid())
        self.assertTrue((prefix / '0.11.7/bin/nvim').exists())
        self.assertTrue((prefix / '0.12.0/bin/nvim').exists())
        result = self.cli('update', 'remote:neovim', '--offline', '-y', '--set', 'version=latest')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Resolved latest stable Neovim: v0.12.6', result.stdout)
        self.assertEqual((prefix / 'bin/nvim').resolve(), prefix / '0.12.6/bin/nvim')
        self.env['NEOVIM_TEST_LATEST'] = '0.12.7'
        result = self.cli('update', '--all', '--offline', '-y')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((prefix / 'bin/nvim').resolve(), prefix / '0.12.7/bin/nvim')
        self.assertTrue((prefix / '0.12.6/bin/nvim').exists())
        self.env['NEOVIM_TEST_LATEST'] = 'invalid'
        result = self.cli('update', '--all', '--offline', '-y')
        self.assertEqual(result.returncode, 1)
        self.assertEqual((prefix / 'bin/nvim').resolve(), prefix / '0.12.7/bin/nvim')
        result = self.cli('update', 'remote:neovim', '--offline', '-y', '--set', 'version=..')
        self.assertEqual(result.returncode, 1)
        self.assertEqual((prefix / 'bin/nvim').resolve(), prefix / '0.12.7/bin/nvim')


if __name__ == '__main__':
    unittest.main()
