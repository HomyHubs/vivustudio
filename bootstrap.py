from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ENV_PREFIX = Path(sys.prefix).resolve()
PYTHON = Path(sys.executable).resolve()
STAMP = ENV_PREFIX / ".voiceover-dependencies"
CUDA_VARIANT = os.environ.get("VOICEOVER_CUDA_VARIANT", "cu130").lower()
if CUDA_VARIANT not in {"cpu", "cu128", "cu130"}:
    CUDA_VARIANT = "cu130"
TORCH_INDEX = f"https://download.pytorch.org/whl/{CUDA_VARIANT}"
TORCH_SUFFIX = "cpu" if CUDA_VARIANT == "cpu" else CUDA_VARIANT
TORCH_VERSION = f"2.11.0+{TORCH_SUFFIX}"
TORCHVISION_VERSION = f"0.26.0+{TORCH_SUFFIX}"
REQUIRED_PYTHON = (3, 12)
CHATTERBOX_COMMIT = "65b18437192794391a0308a8f705b1e33e633948"
CHATTERBOX_SOURCE = ROOT / "vendor" / "chatterbox" / "src" / "chatterbox"
LAMA_MODEL = ROOT / "models" / "lama" / "big-lama.pt"


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    print("> " + " ".join(command))
    return subprocess.run(command, cwd=ROOT, check=check)


def dependency_hash() -> str:
    digest = hashlib.sha256()
    digest.update((ROOT / "requirements.txt").read_bytes())
    digest.update(Path(__file__).read_bytes())
    digest.update(TORCH_INDEX.encode())
    digest.update(sys.version.encode())
    return digest.hexdigest()


def dependencies_available() -> bool:
    modules = [
        "PySide6",
        "faster_whisper",
        "huggingface_hub",
        "imageio_ffmpeg",
        "soundfile",
        "torch",
        "torchaudio",
        "torchvision",
        "scipy",
        "matplotlib",
        "omnivoice",
        "piper",
        "s3tokenizer",
        "diffusers",
        "conformer",
        "pyloudnorm",
        "omegaconf",
        "perth",
    ]
    check = (
        "import importlib.util,sys;"
        f"m={modules!r};"
        "ok=all(importlib.util.find_spec(x) for x in m);"
        "import torch;"
        "ok=ok and torch.__version__=='" + TORCH_VERSION + "';"
        "import torchvision;"
        "ok=ok and torchvision.__version__=='" + TORCHVISION_VERSION + "';"
        "cap='sm_%d%d'%torch.cuda.get_device_capability(0) if torch.cuda.is_available() else None;"
        "ok=ok and ('" + CUDA_VARIANT + "'=='cpu' or cap is None or cap in torch.cuda.get_arch_list());"
        f"ok=ok and {str(CHATTERBOX_SOURCE)!r} and __import__('pathlib').Path({str(CHATTERBOX_SOURCE)!r}).is_dir();"
        f"ok=ok and __import__('pathlib').Path({str(LAMA_MODEL)!r}).is_file();"
        "sys.exit(0 if ok else 1)"
    )
    return subprocess.run([str(PYTHON), "-c", check], cwd=ROOT).returncode == 0


def ensure_chatterbox_source() -> None:
    if CHATTERBOX_SOURCE.is_dir():
        return
    checkout = ROOT / "vendor" / "chatterbox"
    checkout.parent.mkdir(parents=True, exist_ok=True)
    if checkout.exists():
        raise RuntimeError(
            f"Incomplete Chatterbox folder found at {checkout}. Remove that folder and retry."
        )
    print("Downloading Chatterbox Multilingual V3 runtime...")
    run(
        [
            "git",
            "clone",
            "--filter=blob:none",
            "--no-checkout",
            "https://github.com/resemble-ai/chatterbox.git",
            str(checkout),
        ]
    )
    run(["git", "-C", str(checkout), "checkout", CHATTERBOX_COMMIT])


def ensure_lama_model() -> None:
    if LAMA_MODEL.is_file():
        return
    print("Downloading the LaMa inpainting model for CPU/GPU fallback...")
    from huggingface_hub import hf_hub_download

    LAMA_MODEL.parent.mkdir(parents=True, exist_ok=True)
    hf_hub_download(
        repo_id="smartywu/big-lama",
        filename="big-lama.pt",
        local_dir=str(LAMA_MODEL.parent),
    )


def ensure_environment() -> None:
    if sys.version_info[:2] != REQUIRED_PYTHON:
        raise RuntimeError(
            f"VoiceOver Studio requires its Conda environment to use "
            f"Python {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]}, "
            f"but this environment uses Python {sys.version_info.major}.{sys.version_info.minor}."
        )

    expected = dependency_hash()
    installed = STAMP.read_text(encoding="ascii").strip() if STAMP.exists() else ""
    if expected == installed and dependencies_available():
        print("Dependencies are up to date.")
        return

    print("Installing/updating application dependencies. This may take several minutes...")
    run([str(PYTHON), "-m", "pip", "install", "--upgrade", "pip", "wheel", "setuptools<82"])
    run(
        [
            str(PYTHON),
            "-m",
            "pip",
            "install",
            "--upgrade",
            f"torch=={TORCH_VERSION}",
            f"torchaudio==2.11.0+{TORCH_SUFFIX}",
            f"torchvision=={TORCHVISION_VERSION}",
            "--index-url",
            TORCH_INDEX,
        ]
    )
    run([str(PYTHON), "-m", "pip", "install", "--upgrade", "-r", "requirements.txt"])
    ensure_chatterbox_source()
    ensure_lama_model()
    STAMP.write_text(expected, encoding="ascii")


def main() -> int:
    try:
        print(f"Using Conda environment: {ENV_PREFIX}")
        print(f"Using Python: {PYTHON}")
        ensure_environment()
        if "--setup-only" in sys.argv:
            return 0
        print("Starting VoiceOver app...")
        return run([str(PYTHON), "app.py"], check=False).returncode
    except subprocess.CalledProcessError as exc:
        print(f"\nSetup command failed with exit code {exc.returncode}.")
        return exc.returncode
    except Exception as exc:
        print(f"\nSetup failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
