"""현재 사용자의 브라우저·Codex만 정상 종료한다. 명령 문자열 검색으로 다른 작업을 죽이지 않는다."""
import os
from pathlib import Path
import signal
import time
from dataclasses import dataclass


@dataclass
class Process:
    pid: int
    parent: int
    name: str
    started: str
    tty: int = 0
    session: int = 0


def read_process(pid):
    directory = Path(f"/proc/{pid}")
    try:
        if directory.stat().st_uid != os.getuid():
            return None
        stat = (directory / "stat").read_text().rsplit(") ", 1)[1].split()
        name = Path(os.readlink(directory / "exe")).name
        return Process(pid, int(stat[1]), name, stat[19], int(stat[4]), int(stat[3]))
    except (OSError, ValueError, IndexError):
        return None


def process_snapshot():
    result = {}
    for directory in Path("/proc").iterdir():
        if directory.name.isdigit():
            process = read_process(int(directory.name))
            if process is not None:
                result[process.pid] = process
    return result


def select_processes(processes, own_pid):
    # 직접 개발 실행을 잘못 선택해도 자신과 부모 실행기를 종료하지 않는다.
    protected = {own_pid}
    parent = processes.get(own_pid)
    while parent and parent.parent not in protected:
        protected.add(parent.parent)
        parent = processes.get(parent.parent)
    names = {"chrome", "chromium", "chromium-browser", "firefox", "firefox-esr",
             "ChatGPT", "chatgpt", "Codex", "codex"}
    # 개발 실행의 부모 앱은 자식 프로세스도 함께 보호한다.
    families = {pid for pid in protected if pid in processes and processes[pid].name in names}
    while True:
        children = {pid for pid, proc in processes.items() if proc.parent in families}
        added = children - families
        if not added:
            break
        families.update(added)
    protected.update(families)
    selected = {pid for pid, proc in processes.items()
                if proc.name in names and pid not in protected}
    # 서버/렌더러처럼 별도 이름을 가진 자식도 함께 정리한다.
    while True:
        children = {pid for pid, proc in processes.items()
                    if proc.parent in selected and pid not in protected}
        added = children - selected
        if not added:
            break
        selected.update(added)
    # CLI의 대화형 셸만 닫는다. 여러 탭을 가진 터미널 서버는 종료하지 않는다.
    for pid in list(selected):
        proc = processes[pid]
        parent = processes.get(proc.parent)
        if (proc.name == "codex" and parent and parent.name in {"bash", "zsh", "fish"}
                and parent.tty and parent.tty == proc.tty and parent.pid not in protected):
            siblings = [p for p in processes.values() if p.parent == parent.pid]
            if all(p.pid in selected for p in siblings):
                selected.add(parent.pid)
    return [processes[pid] for pid in sorted(selected)]


def stop_development_tools(cancelled=lambda: False, grace_seconds=3):
    targets = select_processes(process_snapshot(), os.getpid())
    for target in targets:
        if cancelled():
            return 0
        current = read_process(target.pid)
        if current is None or current.started != target.started:
            continue  # PID를 재사용한 새 프로세스는 종료하지 않는다.
        try:
            # 대화형 셸은 SIGTERM을 무시할 수 있어 터미널 탭을 닫는 SIGHUP을 쓴다.
            exit_signal = signal.SIGHUP if target.name in {"bash", "zsh", "fish"} else signal.SIGTERM
            os.kill(target.pid, exit_signal)
        except (ProcessLookupError, PermissionError):
            pass
    deadline = time.monotonic() + grace_seconds
    remaining = targets
    while remaining and not cancelled():
        remaining = [target for target in remaining
                     if (current := read_process(target.pid)) is not None
                     and current.started == target.started]
        if not remaining or time.monotonic() >= deadline:
            break
        time.sleep(0.1)
    # 정상 종료에 응답하지 않는 앱은 강제 종료하지 않고 준비를 계속한다.
    return len(remaining)
