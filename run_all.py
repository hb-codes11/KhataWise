#!/usr/bin/env python3
"""Supervise both local services; keep the healer alive across app crashes."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def run_services():
    processes = {}
    stopping = False
    commands = {
        'healer': [sys.executable, str(BASE_DIR / 'server.py')],
        'django': [sys.executable, str(BASE_DIR / 'manage.py'), 'runserver', '127.0.0.1:8000'],
    }
    restart_at = {name: 0 for name in commands}
    failures = {name: 0 for name in commands}

    def shutdown(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    print(f"KhaataWise: http://localhost:8000 | Healer: http://localhost:{os.getenv('SERVER_PORT', '8080')}", flush=True)
    try:
        while not stopping:
            for name, command in commands.items():
                process = processes.get(name)
                if process is not None and process.poll() is not None:
                    failures[name] += 1
                    delay = min(30, 2 ** min(failures[name], 5))
                    restart_at[name] = time.monotonic() + delay
                    entry = f'ERROR supervised service {name} exited with {process.returncode}; restarting in {delay}s\n'
                    (BASE_DIR / 'logs').mkdir(exist_ok=True)
                    with (BASE_DIR / 'logs/error.log').open('a') as log:
                        log.write(entry)
                    processes.pop(name)
                if name not in processes and time.monotonic() >= restart_at[name]:
                    processes[name] = subprocess.Popen(command, cwd=BASE_DIR, start_new_session=True)
            time.sleep(0.5)
    finally:
        # Include Django's autoreloader child in graceful shutdown.
        for process in processes.values():
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for process in processes.values():
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()


if __name__ == '__main__':
    run_services()
