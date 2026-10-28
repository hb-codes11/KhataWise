#!/usr/bin/env python3
"""
Launcher script that runs both:
1. KhaataWise Django Server (port 8000)
2. AI Self-Healing Server (port 8080)
"""
import os
import subprocess
import sys
import time
import signal
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def run_services():
    print("=" * 60)
    print("🚀 Starting KhaataWise + Autonomous AI Self-Healing Server")
    print("=" * 60)
    print(f"Base Directory: {BASE_DIR}")
    print(f"Watched Logs:   {BASE_DIR / 'logs'}")
    print("  - error.log")
    print("  - input.log")
    print("  - output.log")
    print("  - server.log")
    print("=" * 60)

    # 1. Start AI Self-Healing Server (port 8080)
    print("[1/2] Launching AI Self-Healing Server on http://localhost:8080...")
    ai_process = subprocess.Popen(
        [sys.executable, str(BASE_DIR / "server.py")],
        cwd=str(BASE_DIR)
    )

    time.sleep(1)

    # 2. Start Django Development Server (port 8000)
    print("[2/2] Launching KhaataWise Django Server on http://localhost:8000...")
    django_process = subprocess.Popen(
        [sys.executable, str(BASE_DIR / "manage.py"), "runserver", "0.0.0.0:8000"],
        cwd=str(BASE_DIR)
    )

    print("\n✅ Both services are running!")
    print("👉 KhaataWise Web App:      http://localhost:8000")
    print("👉 Test Error Route:        http://localhost:8000/test-error/")
    print("👉 AI Healer Status API:    http://localhost:8080/status")
    print("👉 AI Healer Logs API:      http://localhost:8080/logs")
    print("Press Ctrl+C to terminate both servers.\n")

    def shutdown(signum, frame):
        print("\nStopping services...")
        try:
            django_process.terminate()
            ai_process.terminate()
            django_process.wait(timeout=5)
            ai_process.wait(timeout=5)
        except Exception:
            django_process.kill()
            ai_process.kill()
        print("All services stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Wait for processes
    while True:
        if django_process.poll() is not None:
            print("Django process exited.")
            shutdown(None, None)
        if ai_process.poll() is not None:
            print("AI Self-Healing Server process exited.")
            shutdown(None, None)
        time.sleep(1)

if __name__ == "__main__":
    run_services()
