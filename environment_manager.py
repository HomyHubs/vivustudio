from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable


Progress = Callable[[str], None]


def detect_gpu_name() -> str:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.splitlines()[0].strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def choose_cuda_variant(gpu_name: str) -> str:
    if not gpu_name:
        return "cpu"
    match = re.search(r"RTX\s*(\d{2})\d{2}", gpu_name, re.IGNORECASE)
    series = int(match.group(1)) if match else 0
    if not series:
        return "cpu"
    return "cu130" if series >= 50 else "cu128"


def environment_path(root: Path, variant: str) -> Path:
    preferred = root / f".conda-env-{variant}"
    legacy = root / ".conda-env"
    if variant == "cu130" and not preferred.exists() and (legacy / "python.exe").is_file():
        return legacy
    return preferred


def find_conda() -> Path | None:
    conda_exe = os.environ.get("CONDA_EXE", "").strip()
    candidates = [
        Path(conda_exe) if conda_exe else None,
        Path.home() / "miniconda3" / "Scripts" / "conda.exe",
        Path.home() / "anaconda3" / "Scripts" / "conda.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "miniconda3" / "Scripts" / "conda.exe",
    ]
    located = shutil.which("conda.exe")
    if located:
        candidates.insert(0, Path(located))
    return next((path for path in candidates if path and path.is_file()), None)


def local_cache_environment(root: Path, environment: dict[str, str] | None = None) -> dict[str, str]:
    values = dict(os.environ if environment is None else environment)
    cache_root = root / "cache"
    values.setdefault("PIP_CACHE_DIR", str(cache_root / "pip"))
    values.setdefault("TORCH_HOME", str(cache_root / "torch"))
    values.setdefault("XDG_CACHE_HOME", str(cache_root))
    values.setdefault("HF_HUB_DISABLE_XET", "1")
    values.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")
    return values


def find_or_install_conda(root: Path, progress: Progress) -> Path:
    conda = find_conda()
    if conda is not None:
        return conda
    if not shutil.which("winget.exe"):
        raise RuntimeError(
            "Conda was not found and winget is unavailable. Install Miniconda, then start "
            "VoiceOverStudio again."
        )
    progress("Conda was not found. Installing Miniconda...")
    run_streamed(
        [
            "winget",
            "install",
            "--id",
            "Anaconda.Miniconda3",
            "-e",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ],
        root,
        progress,
    )
    conda = find_conda()
    if conda is None:
        raise RuntimeError(
            "Miniconda installation finished, but conda.exe was not found. Restart Windows "
            "and open VoiceOverStudio again."
        )
    return conda


def run_streamed(command: list[str], root: Path, progress: Progress) -> None:
    process = subprocess.Popen(
        command,
        cwd=root,
        env=local_cache_environment(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert process.stdout is not None
    for line in process.stdout:
        message = line.strip()
        if message:
            progress(message)
    if process.wait() != 0:
        raise RuntimeError(f"Setup command failed with exit code {process.returncode}.")


def ensure_runtime(root: Path, variant: str, progress: Progress) -> Path:
    env_path = environment_path(root, variant)
    python = env_path / "python.exe"
    if not python.is_file():
        conda = find_or_install_conda(root, progress)
        runtime_label = "CPU" if variant == "cpu" else f"CUDA {variant[2:]}"
        progress(f"Creating Python environment for {runtime_label}...")
        run_streamed(
            [
                str(conda),
                "create",
                "--override-channels",
                "-c",
                "conda-forge",
                "--prefix",
                str(env_path),
                "python=3.12",
                "pip",
                "git",
                "-y",
            ],
            root,
            progress,
        )
    runtime_label = "CPU" if variant == "cpu" else f"CUDA {variant[2:]}"
    progress(f"Checking dependencies for {runtime_label}...")
    environment = local_cache_environment(root)
    environment["VOICEOVER_CUDA_VARIANT"] = variant
    process = subprocess.Popen(
        [str(python), str(root / "bootstrap.pyc"), "--setup-only"],
        cwd=root,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert process.stdout is not None
    for line in process.stdout:
        message = line.strip()
        if message:
            progress(message)
    if process.wait() != 0:
        raise RuntimeError("Dependency setup failed. See the latest loading message for details.")
    return env_path

