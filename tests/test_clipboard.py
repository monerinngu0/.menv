import base64
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import mock_open, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'envs/kyopro/.lib'))
sys.path.insert(0, str(ROOT / '.lib'))
import clipboard
from config import ClipboardConfig, ConfigError, load_config
import ksub
from sites import SubmissionUnavailable, SubmitResult


class ClipboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / 'sol.cpp'
        self.data = '// 日本語\nint main() {}\n'.encode()
        self.source.write_bytes(self.data)

    def test_auto_tries_all_backends_in_order_then_osc52(self):
        with patch.object(clipboard.shutil, 'which', side_effect=lambda name: name), patch.object(clipboard, '_copy_command', return_value=False) as command, patch.object(clipboard, '_copy_osc52', return_value=True) as osc:
            self.assertTrue(clipboard.copy_to_clipboard(self.source, ClipboardConfig()))
        self.assertEqual([call.args[0] for call in command.call_args_list], list(clipboard.COMMANDS))
        osc.assert_called_once_with(self.data)

    def test_auto_skips_missing_commands_and_stops_on_success(self):
        with patch.object(clipboard.shutil, 'which', side_effect=lambda name: name if name == 'wl-copy' else None), patch.object(clipboard, '_copy_command', return_value=True) as command, patch.object(clipboard, '_copy_osc52') as osc:
            self.assertTrue(clipboard.copy_to_clipboard(self.source, ClipboardConfig()))
        command.assert_called_once_with(('wl-copy',), self.data)
        osc.assert_not_called()

    def test_auto_prefers_configured_command(self):
        config = ClipboardConfig(command=('custom', '--input'))
        with patch.object(clipboard.shutil, 'which', return_value='/bin/custom'), patch.object(clipboard, '_copy_command', return_value=True) as command:
            self.assertTrue(clipboard.copy_to_clipboard(self.source, config))
        command.assert_called_once_with(config.command, self.data)

    def test_command_passes_exact_bytes_and_arguments_without_shell(self):
        config = ClipboardConfig('command', ('custom', 'argument with spaces', '$(literal)'))
        with patch.object(clipboard.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as run, patch.object(clipboard, '_copy_osc52') as osc:
            self.assertTrue(clipboard.copy_to_clipboard(self.source, config))
        self.assertEqual(run.call_args.args, (config.command,))
        self.assertEqual(run.call_args.kwargs['input'], self.data)
        self.assertNotIn('shell', run.call_args.kwargs)
        osc.assert_not_called()

    def test_command_failures_return_false_without_osc52(self):
        for failure in (FileNotFoundError(), OSError('failed'), subprocess.TimeoutExpired('copy', 5)):
            with self.subTest(failure=failure), patch.object(clipboard.subprocess, 'run', side_effect=failure), patch.object(clipboard, '_copy_osc52') as osc:
                self.assertFalse(clipboard.copy_to_clipboard(self.source, ClipboardConfig('command', ('missing',))))
                osc.assert_not_called()
        with patch.object(clipboard.subprocess, 'run', return_value=SimpleNamespace(returncode=1)):
            self.assertFalse(clipboard.copy_to_clipboard(self.source, ClipboardConfig('command', ('false',))))

    def test_osc52_utf8_base64_and_tmux_wrapper(self):
        sequence = b'\x1b]52;c;' + base64.b64encode(self.data) + b'\x07'
        for tmux in ('', '/tmp/tmux'):
            terminal = mock_open()
            expected = b'\x1bPtmux;' + sequence.replace(b'\x1b', b'\x1b\x1b') + b'\x1b\\' if tmux else sequence
            with self.subTest(tmux=tmux), patch.dict(os.environ, {'TMUX': tmux}), patch('builtins.open', terminal), patch.object(clipboard.subprocess, 'run') as run:
                self.assertTrue(clipboard.copy_to_clipboard(self.source, ClipboardConfig('osc52')))
            terminal.assert_called_once_with('/dev/tty', 'wb')
            terminal().write.assert_called_once_with(expected)
            terminal().flush.assert_called_once()
            run.assert_not_called()

    def test_no_terminal_or_unreadable_source_returns_false(self):
        with patch('builtins.open', side_effect=OSError('no tty')):
            self.assertFalse(clipboard.copy_to_clipboard(self.source, ClipboardConfig('osc52')))
        self.assertFalse(clipboard.copy_to_clipboard(self.source.with_name('missing'), ClipboardConfig()))

    def test_default_loads_clipboard_config(self):
        with patch.object(clipboard, 'load_config', return_value=SimpleNamespace(clipboard=ClipboardConfig('osc52'))), patch.object(clipboard, '_copy_osc52', return_value=True):
            self.assertTrue(clipboard.copy_to_clipboard(self.source))


class ClipboardConfigTests(unittest.TestCase):
    def load(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '.config'
            path.write_text(text)
            return load_config(path).clipboard

    def test_defaults_and_legacy_config(self):
        self.assertEqual(self.load(''), ClipboardConfig())
        self.assertEqual(load_config(ROOT / 'envs/kyopro/.config').clipboard, ClipboardConfig())
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_config(Path(tmp) / 'missing').clipboard, ClipboardConfig())

    def test_valid_methods_and_command_array(self):
        for method in ('auto', 'command', 'osc52'):
            with self.subTest(method=method):
                self.assertEqual(self.load(f'[clipboard]\nmethod = "{method}"\ncommand = ["wl-copy", "--type", "text/plain"]'), ClipboardConfig(method, ('wl-copy', '--type', 'text/plain')))

    def test_invalid_values(self):
        for text in ('clipboard = []', '[clipboard]\nmethod = "bad"', '[clipboard]\nmethod = 1', '[clipboard]\nmethod = "command"', '[clipboard]\ncommand = "clip"', '[clipboard]\ncommand = [1]', '[clipboard]\ncommand = [""]', '[clipboard]\ncommand = ["a\\u0000b"]'):
            with self.subTest(text=text), self.assertRaises(ConfigError):
                self.load(text)


class ClipboardIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / '.lib').symlink_to(ROOT / '.lib', target_is_directory=True)
        config_dir = self.root / 'envs/kyopro'
        config_dir.mkdir(parents=True)
        self.config = config_dir / '.config'
        self.copied = self.root / 'copied'
        # A real external process records exactly the stdin received.
        self.writer = self.root / 'copy.py'
        self.writer.write_text('import pathlib, sys\npathlib.Path(sys.argv[1]).write_bytes(sys.stdin.buffer.read())\n')
        import json
        command = json.dumps([sys.executable, str(self.writer), str(self.copied)])
        self.config.write_text(f'[clipboard]\nmethod = "command"\ncommand = {command}\n')
        self.env = dict(os.environ, MENV_ROOT=str(self.root))
        self.source = self.root / 'a.py'
        self.source.write_text('print("日本語")\n')

    def cli(self, name, *args):
        return subprocess.run([sys.executable, str(ROOT / f'envs/kyopro/.lib/{name}.py'), *map(str, args)], cwd=self.root, env=self.env, capture_output=True, text=True)

    def test_kbuild_only_copies_on_request_and_supports_output(self):
        result = self.cli('kbuild', self.source)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.copied.exists())
        output = self.root / 'generated source.py'
        result = self.cli('kbuild', self.source, '--copy', '-o', output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.copied.read_bytes(), output.read_bytes())
        self.assertIn('copied submission source', result.stdout)

    def test_kbuild_cpp_copies_expanded_source(self):
        (self.root / 'header.h').write_text('#pragma once\nint answer() { return 42; }\n')
        source = self.root / 'a.cpp'
        source.write_text('#include "header.h"\nint main() { return answer(); }\n')
        result = self.cli('kbuild', source, '--copy')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.copied.read_bytes(), (self.root / 'sol.cpp').read_bytes())
        self.assertIn(b'int answer()', self.copied.read_bytes())
        self.assertNotIn(b'#include "header.h"', self.copied.read_bytes())

    def test_failed_build_never_copies(self):
        result = self.cli('kbuild', self.root / 'missing.py', '--copy')
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.copied.exists())

    def test_failed_copy_preserves_generated_file_and_reports_failure(self):
        self.config.write_text('[clipboard]\nmethod = "command"\ncommand = ["/nonexistent/clipboard"]\n')
        result = self.cli('kbuild', self.source, '--copy')
        self.assertEqual(result.returncode, 1)
        self.assertIn('clipboard copy failed', result.stderr)
        self.assertEqual((self.root / 'sol.py').read_bytes(), self.source.read_bytes())

    def test_osc52_writes_to_controlling_terminal_not_stdout(self):
        import errno
        import pty
        import select
        self.config.write_text('[clipboard]\nmethod = "osc52"\n')
        pid, master = pty.fork()
        if pid == 0:
            env = dict(self.env, TMUX='')
            # Redirect stdout/stderr while keeping the controlling terminal.
            with open(os.devnull, 'wb') as sink:
                os.dup2(sink.fileno(), 1)
                os.dup2(sink.fileno(), 2)
            os.execve(sys.executable, [sys.executable, str(ROOT / 'envs/kyopro/.lib/kbuild.py'), str(self.source), '--copy'], env)
        data = bytearray()
        try:
            while select.select([master], [], [], 10)[0]:
                try:
                    chunk = os.read(master, 65536)
                except OSError as error:
                    if error.errno == errno.EIO:
                        break
                    raise
                if not chunk:
                    break
                data.extend(chunk)
            else:
                os.kill(pid, 9)
                self.fail('OSC 52 subprocess timed out')
        finally:
            os.close(master)
            _, status = os.waitpid(pid, 0)
        self.assertEqual(os.waitstatus_to_exitcode(status), 0)
        self.assertEqual(bytes(data), b'\x1b]52;c;' + base64.b64encode(self.source.read_bytes()) + b'\x07')

    def test_ksub_unavailable_copies_and_keeps_failure_exit_status(self):
        (self.root / '.contest').write_text('version = 1\nsite = "local"\nid = "test"\nurl = "local"\n[[problems]]\nlabel = "a"\nid = "a"\nurl = "local/a"\n')
        result = self.cli('ksub', 'a', '--no-test')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.copied.read_bytes(), (self.root / '.build/a/sol.py').read_bytes())
        self.assertIn('copied submission source', result.stdout)

    def test_ksub_submission_results_and_unavailable_exception(self):
        problem = SimpleNamespace(label='a', url='local/a')
        contest = SimpleNamespace(id='test', site='local', problem=lambda label: problem)
        for outcome, copies in ((SubmitResult(True, 0, 'submitted'), False), (SubmitResult(False, 1, 'rejected'), True), (SubmissionUnavailable('unavailable'), True)):
            site = SimpleNamespace(SUBMISSION_AVAILABLE=True)
            from unittest.mock import Mock
            site.submit = Mock(side_effect=outcome) if isinstance(outcome, Exception) else Mock(return_value=outcome)
            with self.subTest(outcome=outcome), patch.object(ksub, 'find_contest_root', return_value=self.root), patch.object(ksub, 'load_contest', return_value=contest), patch.object(ksub, 'find_source', return_value=self.source), patch.object(ksub, 'build_source', return_value=self.source), patch.object(ksub, 'get_site', return_value=site), patch.object(ksub, 'get_submission_language', return_value=None), patch.object(ksub, 'copy_to_clipboard', return_value=True) as copy, redirect_stdout(io.StringIO()):
                if copies:
                    with self.assertRaises(ksub.KsubError):
                        ksub.submit('a', include_dirs=(), timeout=2, test=False)
                    copy.assert_called_once_with(self.source)
                else:
                    ksub.submit('a', include_dirs=(), timeout=2, test=False)
                    copy.assert_not_called()


if __name__ == '__main__':
    unittest.main()
