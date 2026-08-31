from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path

from config_store import config_dir


def log_dir() -> Path:
    path = config_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_path() -> Path:
    return log_dir() / "voiceover-studio.log"


def log_event(message: str) -> None:
    line = f"{datetime.now().isoformat(timespec='seconds')} | {message}\n"
    try:
        with log_path().open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        # Diagnostic logging is best-effort. A locked/read-only log must never
        # propagate through a Qt signal handler and terminate the application.
        return


def gpu_snapshot() -> str:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total,memory.used,temperature.gpu,power.draw,power.limit",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=0x08000000,
        )
        return result.stdout.strip() or result.stderr.strip() or "nvidia-smi returned no data"
    except Exception as exc:
        return f"nvidia-smi unavailable: {exc}"
