#!/usr/bin/env python3
"""
Auto-Battler Coach App Launcher
Starts both the FastAPI backend and React frontend development servers.
"""

import subprocess
import sys
import os
import time
import signal
from pathlib import Path

# Get the app directory
APP_DIR = Path(__file__).parent
FRONTEND_DIR = APP_DIR / 'frontend'
BACKEND_DIR = APP_DIR / 'api'

processes = []


def cleanup(sig=None, frame=None):
    """Clean up child processes"""
    print("\nShutting down...")
    for p in processes:
        try:
            p.terminate()
            p.wait(timeout=5)
        except:
            p.kill()
    sys.exit(0)


def main():
    # Register cleanup handlers
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    print("=" * 50)
    print("Auto-Battler Coach Companion")
    print("=" * 50)

    # Check if node_modules exists
    if not (FRONTEND_DIR / 'node_modules').exists():
        print("\nInstalling frontend dependencies...")
        subprocess.run(['npm', 'install'], cwd=FRONTEND_DIR, check=True)

    # Start backend
    print("\n[1/2] Starting FastAPI backend on http://127.0.0.1:8000")
    backend_proc = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'server:app', '--reload', '--host', '127.0.0.1', '--port', '8000'],
        cwd=BACKEND_DIR,
        env={**os.environ, 'PYTHONPATH': str(APP_DIR.parent)}
    )
    processes.append(backend_proc)

    # Give backend time to start
    time.sleep(2)

    # Start frontend
    print("[2/2] Starting React frontend on http://localhost:5173")
    frontend_proc = subprocess.Popen(
        ['npm', 'run', 'dev'],
        cwd=FRONTEND_DIR
    )
    processes.append(frontend_proc)

    print("\n" + "=" * 50)
    print("App running!")
    print("  Frontend: http://localhost:5173")
    print("  Backend:  http://127.0.0.1:8000")
    print("  API Docs: http://127.0.0.1:8000/docs")
    print("=" * 50)
    print("\nPress Ctrl+C to stop\n")

    # Wait for processes
    try:
        while True:
            # Check if processes are still running
            if backend_proc.poll() is not None:
                print("Backend stopped unexpectedly!")
                cleanup()
            if frontend_proc.poll() is not None:
                print("Frontend stopped unexpectedly!")
                cleanup()
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()

