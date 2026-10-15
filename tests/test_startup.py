"""다른 팀원의 터미널 작업을 보존하고 종료 대상과 PID 재사용을 확인한다."""
import os
from pathlib import Path
import signal
import subprocess
import shutil
import sys
import tempfile
import time
import json
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from startup import Process, select_processes, stop_development_tools, read_process


class StartupTests(unittest.TestCase):
    def processes(self, *items):
        return {p.pid: p for p in items}

    def test_exact_executable_and_children_only(self):
        processes = self.processes(Process(10, 1, 'ChatGPT', '1'),
            Process(11, 10, 'node_repl', '2'), Process(20, 1, 'codex', '3'),
            Process(30, 1, 'firefox', '4'), Process(40, 1, 'bash', '5'),
            Process(50, 1, 'gnome-terminal-server', '6'), Process(99, 1, 'python', '7'))
        self.assertEqual({p.pid for p in select_processes(processes, 99)}, {10, 11, 20, 30})

    def test_own_ancestor_app_and_all_its_children_are_protected(self):
        processes = self.processes(Process(10, 1, 'ChatGPT', '1'),
            Process(11, 10, 'codex', '2'), Process(12, 10, 'ChatGPT', '3'),
            Process(99, 11, 'python', '4'), Process(20, 1, 'codex', '5'))
        self.assertEqual({p.pid for p in select_processes(processes, 99)}, {20})

    def test_only_dedicated_cli_shell_closes_not_terminal_server(self):
        processes = self.processes(Process(10, 1, 'gnome-terminal-server', '1'),
            Process(11, 10, 'bash', '2', tty=5, session=11),
            Process(12, 11, 'codex', '3', tty=5, session=11),
            Process(20, 10, 'bash', '4', tty=6, session=20),
            Process(21, 20, 'codex', '5', tty=6, session=20),
            Process(22, 20, 'python', '6', tty=6, session=20),
            Process(99, 1, 'python', '7'))
        self.assertEqual({p.pid for p in select_processes(processes, 99)}, {11, 12, 21})

    def test_reused_pid_never_receives_signal(self):
        target = Process(10, 1, 'codex', '1')
        with patch('startup.process_snapshot', return_value={10: target}), \
             patch('startup.read_process', return_value=Process(10, 1, 'python', '2')), \
             patch('startup.os.kill') as kill:
            self.assertEqual(stop_development_tools(grace_seconds=0), 0)
        kill.assert_not_called()

    def test_unresponsive_process_gets_only_sigterm_and_bounded_wait(self):
        target = Process(10, 1, 'codex', '1')
        with patch('startup.process_snapshot', return_value={10: target}), \
             patch('startup.read_process', return_value=target), patch('startup.os.kill') as kill:
            self.assertEqual(stop_development_tools(grace_seconds=0), 1)
        kill.assert_called_once_with(10, signal.SIGTERM)

    def test_cancelled_cleanup_does_not_send_signals(self):
        target = Process(10, 1, 'codex', '1')
        with patch('startup.process_snapshot', return_value={10: target}), patch('startup.os.kill') as kill:
            stop_development_tools(cancelled=lambda: True)
        kill.assert_not_called()

    def test_dedicated_terminal_shell_gets_hangup_without_forced_kill(self):
        shell = Process(10, 1, 'bash', '1', tty=5)
        cli = Process(11, 10, 'codex', '2', tty=5)
        with patch('startup.process_snapshot', return_value={10: shell, 11: cli}), \
             patch('startup.read_process', side_effect=lambda pid: {10: shell, 11: cli}[pid]), \
             patch('startup.os.kill') as kill:
            stop_development_tools(grace_seconds=0)
        kill.assert_any_call(10, signal.SIGHUP)
        kill.assert_any_call(11, signal.SIGTERM)

    def test_real_controlled_child_is_terminated_without_touching_other_apps(self):
        child = subprocess.Popen(['sleep', '30'])
        try:
            current = read_process(child.pid)
            target = Process(current.pid, current.parent, 'codex', current.started)
            with patch('startup.process_snapshot', return_value={child.pid: target}):
                stop_development_tools(grace_seconds=0.1)
            self.assertEqual(child.wait(timeout=2), -signal.SIGTERM)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()

    def test_launcher_detaches_before_parent_exits_and_supports_development_mode(self):
        source = Path(__file__).resolve().parents[1] / 'scripts/소리봄-실행.sh'
        with tempfile.TemporaryDirectory(prefix='소리봄 실행 시험 ') as directory:
            root = Path(directory)
            (root / 'scripts').mkdir()
            (root / '.venv/bin').mkdir(parents=True)
            shutil.copy(source, root / 'scripts/소리봄-실행.sh')
            interpreter = root / '.venv/bin/python'
            interpreter.write_text('''#!/usr/bin/env python3
import os, sys, time, json
from pathlib import Path
root = Path(__file__).resolve().parents[2]
(root / 'started.json').write_text(json.dumps({'pid': os.getpid(), 'sid': os.getsid(0), 'args': sys.argv[1:], 'parent': Path(f'/proc/{os.getppid()}/comm').read_text().strip()}))
time.sleep(0.3)
(root / 'finished').touch()
''')
            interpreter.chmod(0o700)
            for flags in ([], ['--keep-development-tools']):
                (root / 'started.json').unlink(missing_ok=True)
                (root / 'finished').unlink(missing_ok=True)
                subprocess.run(['bash', str(root / 'scripts/소리봄-실행.sh'), *flags], check=True, timeout=2)
                deadline = time.monotonic() + 3
                while not (root / 'finished').exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue((root / 'finished').exists())
                started = json.loads((root / 'started.json').read_text())
                self.assertEqual(started['pid'], started['sid'])
                self.assertEqual(started['parent'], 'systemd')
                self.assertEqual('--close-development-tools' in started['args'], not flags)
