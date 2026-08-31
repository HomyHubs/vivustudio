from __future__ import annotations

import csv
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QGroupBox, QHeaderView, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QRadioButton,
    QScrollArea, QSpinBox, QSplitter, QStyle, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)


class TranslatedLogEdit(QPlainTextEdit):
    """Keep raw log messages so EN/VI can be switched without losing details."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._source_paragraphs: list[str] = []

    def _display(self, text: str) -> str:
        translator = getattr(self.window(), "translated_log_text", None)
        return translator(text) if callable(translator) else text

    def appendPlainText(self, text: str) -> None:
        source = str(text)
        self._source_paragraphs.append(source)
        super().appendPlainText(self._display(source))

    def setPlainText(self, text: str) -> None:
        source = str(text)
        self._source_paragraphs = [source] if source else []
        super().setPlainText(self._display(source))

    def clear(self) -> None:
        self._source_paragraphs.clear()
        super().clear()

    def retranslate(self) -> None:
        super().setPlainText("\n".join(self._display(text) for text in self._source_paragraphs))

from core import parse_input


SUPPORTED_LANGUAGES = {
    "ar": "Arabic", "da": "Danish", "de": "German", "el": "Greek",
    "en": "English", "es": "Spanish", "fi": "Finnish", "fr": "French",
    "he": "Hebrew", "hi": "Hindi", "it": "Italian", "ja": "Japanese",
    "ko": "Korean", "ms": "Malay", "nl": "Dutch", "no": "Norwegian",
    "pl": "Polish", "pt": "Portuguese", "ru": "Russian", "sv": "Swedish",
    "sw": "Swahili", "tr": "Turkish", "zh": "Chinese",
}

_CHATTERBOX_MODEL_CACHE: dict[str, object] = {}
_CHATTERBOX_ASR_CACHE: dict[tuple[int, int], object] = {}
BUSY_FILE_RETRY_SECONDS = 5.0


class AudioFileBusyError(PermissionError):
    """The rendered replacement is safe, but the destination is open in another app."""


class InvalidAudioFilesError(ValueError):
    """One or more inputs cannot be decoded or measured safely."""


def ensure_chatterbox_source() -> Path:
    """Prefer the selected GitHub source over a possibly stale PyPI wheel."""
    source = Path(__file__).resolve().parent / "vendor" / "chatterbox" / "src"
    if source.is_dir() and str(source) not in sys.path:
        sys.path.insert(0, str(source))
    return source


def import_chatterbox_multilingual():
    """Import vendored source without requiring conflicting distribution metadata."""
    ensure_chatterbox_source()
    import importlib.metadata

    original_version = importlib.metadata.version

    def compatible_version(distribution_name: str) -> str:
        if distribution_name == "chatterbox-tts":
            try:
                return original_version(distribution_name)
            except importlib.metadata.PackageNotFoundError:
                return "git-master"
        return original_version(distribution_name)

    importlib.metadata.version = compatible_version
    try:
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        return ChatterboxMultilingualTTS
    finally:
        importlib.metadata.version = original_version


def _words(text: str) -> str:
    return " ".join(re.findall(r"[\w]+(?:['’][\w]+)?", text.lower(), re.UNICODE))


def _expected_duration(text: str) -> float:
    words = re.findall(r"[\w]+(?:['’][\w]+)?", text, re.UNICODE)
    punctuation = 0.12 * len(re.findall(r"[,;:]", text))
    punctuation += 0.24 * len(re.findall(r"[.!?]", text))
    return max(0.8, len(words) / 2.5 + punctuation)


def _ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def validate_audio_file(path: Path) -> None:
    """Decode the complete audio stream and fail on even recoverable FFmpeg errors."""
    if not path.is_file() or path.stat().st_size < 128:
        raise InvalidAudioFilesError("file is missing or too small")
    result = subprocess.run(
        [
            _ffmpeg(), "-v", "error", "-xerror", "-i", str(path),
            "-map", "0:a:0", "-f", "null", "-",
        ],
        capture_output=True, text=True, creationflags=0x08000000,
    )
    if result.returncode:
        details = " ".join(result.stderr.strip().split())
        raise InvalidAudioFilesError(details[-500:] or "audio decode failed")


def measure_speech_rms_db(path: Path, threshold_db: float = -45.0) -> float | None:
    import numpy as np

    result = subprocess.run(
        [_ffmpeg(), "-v", "error", "-i", str(path), "-ac", "1", "-ar", "24000", "-f", "f32le", "-"],
        capture_output=True, creationflags=0x08000000,
    )
    if result.returncode:
        raise RuntimeError("Could not measure audio loudness:\n" + result.stderr[-1000:].decode(errors="replace"))
    audio = np.frombuffer(result.stdout, dtype=np.float32)
    frame_size = 480
    frame_count = len(audio) // frame_size
    if not frame_count:
        return None
    frames = audio[: frame_count * frame_size].reshape(frame_count, frame_size)
    frame_rms = np.sqrt(np.mean(frames * frames, axis=1))
    active = frames[frame_rms > 10 ** (threshold_db / 20)]
    if not len(active):
        return None
    rms = float(np.sqrt(np.mean(active * active)))
    return 20 * float(np.log10(max(rms, 1e-9)))


def apply_constant_gain(path: Path, gain_db: float) -> None:
    temporary = path.with_name(f".{path.stem}.batch-normalized{path.suffix}")
    codec = ["-codec:a", "pcm_s16le"] if path.suffix.lower() == ".wav" else [
        "-codec:a", "libmp3lame", "-b:a", "192k"
    ]
    result = subprocess.run(
        [_ffmpeg(), "-y", "-i", str(path), "-af",
         f"volume={gain_db:.3f}dB,alimiter=limit=0.891:level=false:latency=true",
         *codec, str(temporary)],
        capture_output=True, text=True, creationflags=0x08000000,
    )
    if result.returncode:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("Batch audio normalization failed:\n" + result.stderr[-1000:])
    try:
        os.replace(temporary, path)
    except PermissionError as exc:
        temporary.unlink(missing_ok=True)
        raise PermissionError(
            f"Cannot update '{path.name}' because it is open. Close the audio player, "
            "then click Retry batch normalization."
        ) from exc


def normalize_completed_batch(
    files: list[Path], progress=None, target_db: float = -20.0,
) -> list[dict]:
    """Run OmniVoice's archive-all, measure-all, then write-all loudness pass."""
    progress = progress or (lambda _message: None)
    if not files:
        return []
    measurements: list[tuple[Path, float]] = []
    invalid: list[str] = []
    for index, path in enumerate(files, 1):
        progress(f"Validating audio {index}/{len(files)}: {path.name}")
        try:
            validate_audio_file(path)
            progress(f"Measuring speech loudness {index}/{len(files)}: {path.name}")
            level = measure_speech_rms_db(path)
            if level is None:
                raise InvalidAudioFilesError("no measurable speech audio")
            measurements.append((path, level))
        except (InvalidAudioFilesError, OSError, RuntimeError) as exc:
            invalid.append(f"{path.name}: {exc}")
    if invalid:
        raise InvalidAudioFilesError(
            "Normalization stopped. Invalid audio file(s):\n- " + "\n- ".join(invalid)
        )
    originals = files[0].parent / "_original_chatterbox_v3"
    originals.mkdir(parents=True, exist_ok=True)
    for index, path in enumerate(files, 1):
        archived = originals / path.name
        if not archived.is_file():
            progress(f"Saving original file {index}/{len(files)}: {path.name}")
            shutil.copy2(path, archived)
    report: list[dict] = []
    for index, (path, before) in enumerate(measurements, 1):
        gain_db = max(-12.0, min(12.0, target_db - before))
        applied = 0.0
        status = "already near target"
        if abs(gain_db) >= 0.75:
            progress(
                f"Writing normalized audio {index}/{len(measurements)}: "
                f"{path.name} ({gain_db:+.1f} dB)"
            )
            apply_constant_gain(path, gain_db)
            applied = gain_db
            status = "normalized"
        else:
            progress(
                f"Already near target {index}/{len(measurements)}: {path.name}"
            )
        report.append({
            "file": path.name, "before_speech_rms_db": round(before, 3),
            "gain_db": round(applied, 3),
            "after_speech_rms_db": round(measure_speech_rms_db(path), 3),
            "target_speech_rms_db": target_db, "status": status,
            "original_file": str(originals / path.name),
        })
    report_path = files[0].parent / "loudness_before_after.csv"
    with report_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(report[0]) if report else ["file"])
        writer.writeheader()
        writer.writerows(report)
    progress(f"Loudness report saved: {report_path.name}")
    return report


class ChatterboxRenderWorker(QObject):
    progress = Signal(int, int, str)
    timing = Signal(int, int, float, float)
    pipeline_phase = Signal(str, int, int)
    segment_status = Signal(int, str)
    completed = Signal(str)
    failed = Signal(str)
    cancelled = Signal(str)

    def __init__(
        self, profile: dict, script: Path, output_dir: Path, language: str,
        device: str, output_format: str, exaggeration: float, cfg_weight: float,
        temperature: float, repetition_penalty: float, min_p: float, top_p: float,
        auto_qa: bool, qa_retries: int, asr_workers: int, overwrite: bool,
        positions: list[int] | None = None, normalize_audio: bool = True,
    ) -> None:
        super().__init__()
        self.profile = profile
        self.script = script
        self.output_dir = output_dir
        self.language = language
        self.device = device
        self.output_format = output_format
        self.exaggeration = exaggeration
        self.cfg_weight = cfg_weight
        self.temperature = temperature
        self.repetition_penalty = repetition_penalty
        self.min_p = min_p
        self.top_p = top_p
        self.auto_qa = auto_qa
        self.qa_retries = qa_retries
        self.asr_workers = asr_workers
        self.overwrite = overwrite
        self.positions = positions
        self.normalize_audio = normalize_audio
        self.cancel_event = threading.Event()

    def request_cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        global _CHATTERBOX_MODEL_CACHE, _CHATTERBOX_ASR_CACHE
        model = asr = torch = None
        run_started = time.monotonic()
        try:
            import soundfile as sf
            import torch as torch_module
            ChatterboxMultilingualTTS = import_chatterbox_multilingual()

            torch = torch_module
            if self.device == "cuda" and not torch.cuda.is_available():
                raise RuntimeError("CUDA is selected, but PyTorch cannot find a CUDA GPU.")
            segments = parse_input(self.script)
            if not segments:
                raise ValueError("The script contains no valid segments.")
            reference = Path(self.profile.get("reference_audio", ""))
            if not reference.is_file():
                raise ValueError("The voice profile reference audio does not exist.")
            if self.language not in SUPPORTED_LANGUAGES:
                raise ValueError(
                    f"Chatterbox Multilingual V3 does not support language_id '{self.language}'."
                )
            self.output_dir.mkdir(parents=True, exist_ok=True)
            cache_key = f"v3:{self.device}"
            model = _CHATTERBOX_MODEL_CACHE.get(cache_key)
            if model is None:
                self.progress.emit(0, len(segments), "Loading Chatterbox Multilingual V3...")
                model = ChatterboxMultilingualTTS.from_pretrained(
                    device=self.device, t3_model="v3"
                )
                _CHATTERBOX_MODEL_CACHE.clear()
                _CHATTERBOX_MODEL_CACHE[cache_key] = model
            else:
                self.progress.emit(0, len(segments), "Reusing the loaded Chatterbox V3 model...")
            model.prepare_conditionals(str(reference), exaggeration=self.exaggeration)
            if self.auto_qa:
                from faster_whisper import WhisperModel
                cpu_threads = max(1, (os.cpu_count() or 4) // max(1, self.asr_workers))
                asr_key = (cpu_threads, max(1, self.asr_workers))
                asr = _CHATTERBOX_ASR_CACHE.get(asr_key)
                if asr is None:
                    asr = WhisperModel(
                        "small", device="cpu", compute_type="int8",
                        cpu_threads=cpu_threads, num_workers=max(1, self.asr_workers),
                    )
                    _CHATTERBOX_ASR_CACHE.clear()
                    _CHATTERBOX_ASR_CACHE[asr_key] = asr
            selected = [
                (index, segment) for index, segment in enumerate(segments, 1)
                if self.positions is None or index in self.positions
            ]
            if not selected:
                raise ValueError("The selected render range contains no segments.")
            if self.positions is not None:
                selected_numbers = ", ".join(str(index) for index, _segment in selected)
                self.progress.emit(
                    0, len(selected),
                    f"Scoped rerender · only segment(s) {selected_numbers} will be rendered and checked",
                )
            width = max(3, len(str(len(segments))))
            states: dict[int, dict] = {}

            def render_audio(state: dict) -> None:
                index = state["index"]
                segment = state["segment"]
                destination = state["destination"]
                pending_replacement = state.get("pending_replacement")
                if pending_replacement:
                    try:
                        os.replace(pending_replacement, destination)
                    except PermissionError as exc:
                        raise AudioFileBusyError(str(destination)) from exc
                    state.pop("pending_replacement", None)
                    return
                attempt = state["attempts"]
                retry = attempt - 1
                temperature = max(0.55, self.temperature - retry * 0.12)
                cfg_weight = max(0.0, self.cfg_weight - retry * 0.10)
                repetition = min(2.0, self.repetition_penalty + retry * 0.08)
                with torch.inference_mode():
                    wav = model.generate(
                        segment.text, language_id=self.language,
                        exaggeration=self.exaggeration, cfg_weight=cfg_weight,
                        temperature=temperature, repetition_penalty=repetition,
                        min_p=self.min_p, top_p=self.top_p,
                    )
                audio = wav.squeeze().detach().float().cpu().numpy()
                state["duration"] = len(audio) / float(model.sr)
                wav_temp = self.output_dir / f".{index:0{width}d}.render.wav"
                sf.write(wav_temp, audio, model.sr)
                if self.output_format == "wav":
                    try:
                        os.replace(wav_temp, destination)
                    except PermissionError as exc:
                        state["pending_replacement"] = wav_temp
                        raise AudioFileBusyError(str(destination)) from exc
                    return
                encoded_temp = self.output_dir / f".{index:0{width}d}.render.mp3"
                result = subprocess.run(
                    [_ffmpeg(), "-y", "-i", str(wav_temp), "-codec:a", "libmp3lame",
                     "-b:a", "192k", str(encoded_temp)],
                    capture_output=True, text=True, creationflags=0x08000000,
                )
                wav_temp.unlink(missing_ok=True)
                if result.returncode:
                    encoded_temp.unlink(missing_ok=True)
                    raise RuntimeError("MP3 conversion failed:\n" + result.stderr[-1000:])
                try:
                    os.replace(encoded_temp, destination)
                except PermissionError as exc:
                    state["pending_replacement"] = encoded_temp
                    raise AudioFileBusyError(str(destination)) from exc

            def check_audio(state: dict) -> tuple[str, float, list[str]]:
                index = state["index"]
                self.segment_status.emit(index, "ASR checking")
                reasons: list[str] = []
                duration = float(state.get("duration", 0.0))
                expected = _expected_duration(state["segment"].text)
                if duration > max(8.0, expected * 3.0):
                    reasons.append(f"duration {duration:.1f}s / expected ~{expected:.1f}s")
                elif duration < max(0.25, expected * 0.28):
                    reasons.append(f"audio is too short ({duration:.1f}s)")
                transcript = ""
                similarity = 1.0
                if not reasons:
                    decoded, _ = asr.transcribe(
                        str(state["destination"]), language=self.language,
                        vad_filter=True, beam_size=3,
                    )
                    transcript = " ".join(item.text.strip() for item in decoded).strip()
                    similarity = difflib.SequenceMatcher(
                        None, _words(state["segment"].text), _words(transcript)
                    ).ratio()
                    if similarity < 0.58:
                        reasons.append(f"ASR match {similarity:.0%}")
                return transcript, similarity, reasons

            # Phase 1: render every selected segment once. ASR never blocks this pass.
            self.pipeline_phase.emit("Initial render", 0, len(selected))
            initially_blocked: list[dict] = []
            for rendered_count, (index, segment) in enumerate(selected, 1):
                if self.cancel_event.is_set():
                    self.cancelled.emit(
                        f"Stopped safely; kept {len(states)} rendered file(s)."
                    )
                    return
                destination = self.output_dir / f"{index:0{width}d}.{self.output_format}"
                state = {
                    "index": index, "segment": segment, "destination": destination,
                    "attempts": 0, "started": time.monotonic(), "duration": 0.0,
                    "transcript": "", "similarity": 1.0, "reasons": [],
                }
                states[index] = state
                if destination.is_file() and not self.overwrite:
                    state["duration"] = float(sf.info(destination).duration)
                    self.segment_status.emit(
                        index, "Existing · Waiting for ASR" if self.auto_qa else "Completed · Existing"
                    )
                    self.progress.emit(
                        rendered_count, len(selected), f"Initial render {rendered_count}/{len(selected)}"
                        f" · kept existing {destination.name}"
                    )
                    self.pipeline_phase.emit("Initial render", rendered_count, len(selected))
                    continue
                state["attempts"] = 1
                self.segment_status.emit(index, "Initial rendering")
                self.progress.emit(
                    rendered_count - 1, len(selected),
                    f"Initial render {rendered_count}/{len(selected)} · {destination.name}",
                )
                try:
                    render_audio(state)
                except AudioFileBusyError:
                    state["busy_retry_at"] = time.monotonic() + BUSY_FILE_RETRY_SECONDS
                    initially_blocked.append(state)
                    self.segment_status.emit(index, "File open · Replacement queued")
                    self.progress.emit(
                        rendered_count, len(selected),
                        f"{destination.name} is open in another app · retry queued",
                    )
                else:
                    self.segment_status.emit(
                        index, "Rendered · Waiting for ASR" if self.auto_qa else "Completed"
                    )
                self.progress.emit(
                    rendered_count, len(selected),
                    f"Initial render completed {rendered_count}/{len(selected)} · {destination.name}",
                )
                self.pipeline_phase.emit("Initial render", rendered_count, len(selected))
                if not self.auto_qa and not state.get("pending_replacement"):
                    self.timing.emit(
                        rendered_count, len(selected), time.monotonic() - run_started,
                        time.monotonic() - state["started"],
                    )

            # Phase 2: ASR checks run concurrently. Failed files enter one GPU regeneration queue.
            if self.auto_qa:
                regenerate = deque()
                blocked = deque(initially_blocked)
                verified_count = 0
                self.pipeline_phase.emit("ASR verification", 0, len(selected))
                executor = ThreadPoolExecutor(
                    max_workers=max(1, self.asr_workers), thread_name_prefix="chatterbox-v3-asr"
                )
                pending = {
                    executor.submit(check_audio, state): state for state in states.values()
                    if not state.get("pending_replacement")
                }
                try:
                    while pending or regenerate or blocked:
                        if self.cancel_event.is_set():
                            for future in pending:
                                future.cancel()
                            self.cancelled.emit(
                                f"Stopped safely; kept {len(states)} rendered file(s)."
                            )
                            return
                        now = time.monotonic()
                        for _ in range(len(blocked)):
                            state = blocked.popleft()
                            if state.get("busy_retry_at", 0.0) <= now:
                                regenerate.append(state)
                            else:
                                blocked.append(state)
                        ready = {future for future in pending if future.done()}
                        if not ready and not regenerate and pending:
                            ready, _ = wait(pending, timeout=0.15, return_when=FIRST_COMPLETED)
                        elif not ready and not regenerate and blocked:
                            next_retry = min(state["busy_retry_at"] for state in blocked)
                            self.cancel_event.wait(min(0.5, max(0.01, next_retry - time.monotonic())))
                        for future in ready:
                            state = pending.pop(future)
                            transcript, similarity, reasons = future.result()
                            state.update({
                                "transcript": transcript, "similarity": similarity,
                                "reasons": reasons,
                            })
                            if reasons and state["attempts"] <= self.qa_retries:
                                regenerate.append(state)
                                reason = "; ".join(reasons)
                                self.segment_status.emit(
                                    state["index"], "Error · Waiting to regenerate"
                                )
                                self.progress.emit(
                                    verified_count, len(selected),
                                    f"ASR found error in {state['destination'].name} · {reason}"
                                    " · queued regeneration",
                                )
                            else:
                                verified_count += 1
                                self.segment_status.emit(
                                    state["index"],
                                    "Review required" if reasons else "Verified · ASR passed",
                                )
                                if reasons:
                                    reason = "; ".join(reasons)
                                    repair_count = max(0, int(state["attempts"]) - 1)
                                    progress_message = (
                                        f"ASR REVIEW REQUIRED · {state['destination'].name} · "
                                        f"using last generated audio · initial + {repair_count} repair(s) · "
                                        f"reason: {reason}"
                                    )
                                else:
                                    progress_message = (
                                        f"ASR verified {verified_count}/{len(selected)} · "
                                        f"{state['destination'].name}"
                                    )
                                self.progress.emit(
                                    verified_count, len(selected),
                                    progress_message,
                                )
                                self.timing.emit(
                                    verified_count, len(selected), time.monotonic() - run_started,
                                    time.monotonic() - state["started"],
                                )
                                self.pipeline_phase.emit(
                                    "ASR verification", verified_count, len(selected)
                                )
                        if regenerate:
                            state = regenerate.popleft()
                            if state.get("pending_replacement"):
                                self.segment_status.emit(state["index"], "Retrying open file")
                                self.progress.emit(
                                    verified_count, len(selected),
                                    f"Retrying replacement of open file {state['destination'].name}",
                                )
                            else:
                                state["attempts"] += 1
                                retry = state["attempts"] - 1
                                self.segment_status.emit(
                                    state["index"],
                                    f"Regenerating · Attempt {retry}/{self.qa_retries}",
                                )
                                self.progress.emit(
                                    verified_count, len(selected),
                                    f"Regenerating {state['destination'].name}"
                                    f" · repair {retry}/{self.qa_retries}",
                                )
                            try:
                                render_audio(state)
                            except AudioFileBusyError:
                                state["busy_retry_at"] = (
                                    time.monotonic() + BUSY_FILE_RETRY_SECONDS
                                )
                                blocked.append(state)
                                self.segment_status.emit(
                                    state["index"],
                                    f"File open · Retry in {BUSY_FILE_RETRY_SECONDS:g}s",
                                )
                                self.progress.emit(
                                    verified_count, len(selected),
                                    f"Skipped open file {state['destination'].name}"
                                    f" · retrying in {BUSY_FILE_RETRY_SECONDS:g}s",
                                )
                                continue
                            self.segment_status.emit(state["index"], "Regenerated · Waiting for ASR")
                            pending[executor.submit(check_audio, state)] = state
                finally:
                    executor.shutdown(wait=True, cancel_futures=True)

            elif initially_blocked:
                # Without ASR, still keep retrying queued replacements until the player releases them.
                blocked = deque(initially_blocked)
                while blocked:
                    if self.cancel_event.wait(0.25):
                        self.cancelled.emit(
                            f"Stopped safely; {len(blocked)} open file(s) remain queued."
                        )
                        return
                    state = blocked[0]
                    if state["busy_retry_at"] > time.monotonic():
                        continue
                    self.segment_status.emit(state["index"], "Retrying open file")
                    try:
                        render_audio(state)
                    except AudioFileBusyError:
                        state["busy_retry_at"] = time.monotonic() + BUSY_FILE_RETRY_SECONDS
                        self.segment_status.emit(
                            state["index"], f"File open · Retry in {BUSY_FILE_RETRY_SECONDS:g}s"
                        )
                        continue
                    blocked.popleft()
                    self.segment_status.emit(state["index"], "Completed")

            manifest: list[dict] = []
            qa_rows: list[dict] = []
            for index, state in sorted(states.items()):
                segment = state["segment"]
                record = asdict(segment)
                record.update({
                    "file": state["destination"].name, "engine": "Chatterbox-Multilingual-V3",
                    "language": self.language, "qa_attempts": state["attempts"],
                })
                manifest.append(record)
                qa_rows.append({
                    "segment": index,
                    "status": (
                        "completed" if not self.auto_qa else
                        "verified" if not state["reasons"] else "needs_review"
                    ),
                    "attempts": state["attempts"],
                    "text_match": f"{state['similarity']:.3f}",
                    "expected_text": segment.text,
                    "asr_transcript": state["transcript"],
                    "reason": "; ".join(state["reasons"]),
                    "audio_file": str(state["destination"]),
                })
            numbered = [
                self.output_dir / f"{index:0{width}d}.{self.output_format}"
                for index in range(1, len(segments) + 1)
            ]
            normalize_targets = (
                numbered if self.positions is None else
                [states[index]["destination"] for index, _segment in selected]
            )
            if self.normalize_audio and normalize_targets and all(
                path.is_file() for path in normalize_targets
            ):
                scope = "completed batch" if self.positions is None else "rerendered file(s) only"
                self.progress.emit(
                    len(selected), len(selected),
                    f"ASR complete · normalizing {scope} ({len(normalize_targets)} file(s))...",
                )
                normalize_completed_batch(
                    normalize_targets,
                    progress=lambda message: self.progress.emit(len(selected), len(selected), message),
                )
            manifest_path = self.output_dir / "manifest.json"
            if self.positions is not None and manifest_path.is_file():
                try:
                    existing_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    merged_manifest = {
                        int(record["index"]): record for record in existing_manifest
                        if isinstance(record, dict) and "index" in record
                    }
                    merged_manifest.update({int(record["index"]): record for record in manifest})
                    manifest = [merged_manifest[index] for index in sorted(merged_manifest)]
                except (OSError, ValueError, TypeError, KeyError):
                    pass
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            if qa_rows:
                report_path = self.output_dir / "chatterbox_v3_asr_report.csv"
                if self.positions is not None and report_path.is_file():
                    try:
                        with report_path.open(encoding="utf-8-sig", newline="") as handle:
                            merged_rows = {
                                int(row["segment"]): row for row in csv.DictReader(handle)
                            }
                        merged_rows.update({int(row["segment"]): row for row in qa_rows})
                        qa_rows = [merged_rows[index] for index in sorted(merged_rows)]
                    except (OSError, ValueError, TypeError, KeyError):
                        pass
                with report_path.open(
                    "w", newline="", encoding="utf-8-sig"
                ) as handle:
                    writer = csv.DictWriter(handle, fieldnames=list(qa_rows[0]))
                    writer.writeheader()
                    writer.writerows(qa_rows)
                review_rows = [
                    row for row in qa_rows if row.get("status") == "needs_review"
                ]
                if review_rows:
                    review_files = ", ".join(
                        Path(str(row["audio_file"])).name for row in review_rows
                    )
                    self.progress.emit(
                        len(selected), len(selected),
                        f"ASR REVIEW SUMMARY · {len(review_rows)} file(s) use the last "
                        f"generated audio: {review_files} · report: {report_path}",
                    )
            self.completed.emit(str(self.output_dir))
        except ModuleNotFoundError as exc:
            self.failed.emit(
                "Chatterbox V3 runtime is missing. Run 'Install Chatterbox V3.ps1' "
                "to install it without downgrading the OmniVoice/MOSS Torch and CUDA stack.\n\n"
                + str(exc)
            )
        except Exception:
            _CHATTERBOX_MODEL_CACHE.clear()
            self.failed.emit(traceback.format_exc())
        finally:
            model = asr = None
            if torch is not None:
                try:
                    import gc
                    gc.collect()
                except Exception:
                    pass


class ChatterboxPreloadWorker(QObject):
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, device: str) -> None:
        super().__init__()
        self.device = device

    def run(self) -> None:
        global _CHATTERBOX_MODEL_CACHE
        try:
            import torch

            if self.device == "cuda" and not torch.cuda.is_available():
                raise RuntimeError("CUDA is selected, but PyTorch cannot find a CUDA GPU.")
            cache_key = f"v3:{self.device}"
            if cache_key not in _CHATTERBOX_MODEL_CACHE:
                model_class = import_chatterbox_multilingual()
                model = model_class.from_pretrained(device=self.device, t3_model="v3")
                _CHATTERBOX_MODEL_CACHE.clear()
                _CHATTERBOX_MODEL_CACHE[cache_key] = model
            self.completed.emit(
                f"Chatterbox Multilingual V3 ready · {self.device.upper()} · 24 kHz"
            )
        except Exception:
            _CHATTERBOX_MODEL_CACHE.clear()
            self.failed.emit(traceback.format_exc())


class ChatterboxNormalizeWorker(QObject):
    progress = Signal(str)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, files: list[Path]) -> None:
        super().__init__()
        self.files = files

    def run(self) -> None:
        try:
            normalize_completed_batch(self.files, progress=self.progress.emit)
            self.completed.emit(str(self.files[0].parent))
        except InvalidAudioFilesError as exc:
            self.failed.emit(str(exc))
        except Exception:
            self.failed.emit(traceback.format_exc())


class ChatterboxFolderNormalizeWorker(QObject):
    progress = Signal(str)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, source: Path, destination: Path) -> None:
        super().__init__()
        self.source = source
        self.destination = destination

    def run(self) -> None:
        try:
            sources = sorted(
                path for path in self.source.iterdir()
                if path.is_file() and path.suffix.lower() in {".wav", ".mp3"}
            )
            if not sources:
                raise ValueError("The selected folder contains no WAV or MP3 files.")
            invalid = []
            for index, source in enumerate(sources, 1):
                self.progress.emit(
                    f"Validating source audio {index}/{len(sources)}: {source.name}"
                )
                try:
                    validate_audio_file(source)
                    if measure_speech_rms_db(source) is None:
                        raise InvalidAudioFilesError("no measurable speech audio")
                except (InvalidAudioFilesError, OSError, RuntimeError) as exc:
                    invalid.append(f"{source.name}: {exc}")
            if invalid:
                raise InvalidAudioFilesError(
                    "No output folder was created. Invalid source audio file(s):\n- "
                    + "\n- ".join(invalid)
                )
            self.destination.mkdir(parents=True, exist_ok=False)
            copies = []
            for index, source in enumerate(sources, 1):
                destination = self.destination / source.name
                self.progress.emit(
                    f"Copying audio {index}/{len(sources)}: {source.name}"
                )
                shutil.copy2(source, destination)
                copies.append(destination)
            normalize_completed_batch(copies, progress=self.progress.emit)
            self.completed.emit(str(self.destination))
        except InvalidAudioFilesError as exc:
            self.failed.emit(str(exc))
        except Exception:
            self.failed.emit(traceback.format_exc())


class ChatterboxV3Tab(QWidget):
    """Self-contained Chatterbox V3 batch UI using the shared Voice List profiles."""

    preload_finished = Signal()

    def __init__(self, profile_store, selected_profile, data_dir: Path, parent=None) -> None:
        super().__init__(parent)
        self.profile_store = profile_store
        self.selected_profile = selected_profile
        self.config_path = data_dir / "voice_clone_v3_config.json"
        self.rows: list[dict] = []
        self.current_row: dict | None = None
        self.queue: list[dict] = []
        self.queue_index = 0
        self.batch_task_total = 0
        self.rerender_queue: list[dict] = []
        self.rerender_queue_keys: set[tuple[int, int]] = set()
        self.delete_queue: list[dict] = []
        self.delete_queue_keys: set[tuple[int, int]] = set()
        self.edited_segment_keys: set[tuple[int, int]] = set()
        self.queued_rerender_active = False
        self.single_segment_render = False
        self.active_selected_positions: list[int] = []
        self.active_render_row: dict | None = None
        self.render_succeeded = False
        self.thread: QThread | None = None
        self.worker: ChatterboxRenderWorker | None = None
        self.preload_thread: QThread | None = None
        self.preload_worker: ChatterboxPreloadWorker | None = None
        self.normalize_thread: QThread | None = None
        self.normalize_worker: ChatterboxNormalizeWorker | None = None
        self.last_output: Path | None = None
        self.timing_started_at: float | None = None
        self.timing_total_segments = 0
        self.timing_completed_segments = 0
        self.timing_task_base = 0
        self.timing_last_segment = 0.0
        self.timing_mode = "idle"
        self.pipeline_phase_name = ""
        self.pipeline_phase_done = 0
        self.pipeline_phase_total = 0
        self.pipeline_phase_started_at: float | None = None
        self.settings = self._load_settings()
        self._build_ui()
        self.refresh_profiles()

    def start_preload(self) -> None:
        """Load Multilingual V3 after the app opens so the first render starts quickly."""
        if self.preload_thread and self.preload_thread.isRunning():
            return
        device = str(self.device.currentData() or "cuda")
        if f"v3:{device}" in _CHATTERBOX_MODEL_CACHE:
            self.status.setText(
                f"Chatterbox Multilingual V3 ready · {device.upper()} · 24 kHz"
            )
            self.preload_finished.emit()
            return
        self.preload_worker = ChatterboxPreloadWorker(device)
        self.preload_thread = QThread(self)
        self.preload_worker.moveToThread(self.preload_thread)
        self.preload_thread.started.connect(self.preload_worker.run)
        self.preload_worker.completed.connect(self.on_preload_completed)
        self.preload_worker.failed.connect(self.on_preload_failed)
        self.preload_worker.completed.connect(self.preload_thread.quit)
        self.preload_worker.failed.connect(self.preload_thread.quit)
        self.preload_thread.finished.connect(self.on_preload_finished)
        self.render_button.setEnabled(False)
        self.status.setText("Preloading Chatterbox Multilingual V3 on startup...")
        self.log.appendPlainText(
            f"Startup preload · Chatterbox Multilingual V3 · t3_model=v3 · {device.upper()}"
        )
        self.preload_thread.start()

    def on_preload_completed(self, message: str) -> None:
        self.status.setText(message)
        self.log.appendPlainText(message)

    def on_preload_failed(self, details: str) -> None:
        message = "Chatterbox V3 preload failed; Render will try loading it again."
        self.status.setText(message)
        self.log.appendPlainText(message + "\n" + details)

    def on_preload_finished(self) -> None:
        self.preload_worker = None
        self.preload_thread = None
        self.render_button.setEnabled(True)
        self.preload_finished.emit()

    def _load_settings(self) -> dict:
        defaults = {
            "profile": "", "language": "en", "device": "cuda", "format": "wav",
            "exaggeration": 0.5, "cfg_weight": 0.5, "temperature": 0.8,
            "repetition_penalty": 1.2, "min_p": 0.05, "top_p": 1.0,
            "auto_qa": True, "qa_retries": 2, "asr_workers": 2,
            "normalize_audio": True, "merge_pause": 0.45,
        }
        try:
            loaded = json.loads(self.config_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                defaults.update(loaded)
        except (OSError, json.JSONDecodeError):
            pass
        return defaults

    def _button(self, text, callback) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("_i18n_text", text)
        translator = getattr(self.parent(), "translated_ui_text", None)
        if callable(translator):
            button.setText(translator(text))
        button.clicked.connect(callback)
        return button

    def _spin(self, low, high, value, step=0.05) -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setRange(low, high)
        widget.setDecimals(2)
        widget.setSingleStep(step)
        widget.setValue(float(value))
        return widget

    @staticmethod
    def _paired(left: QWidget, middle_label: str, right: QWidget) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(left, 1)
        if middle_label:
            layout.addWidget(QLabel(middle_label))
        layout.addWidget(right, 1)
        return container

    def _build_ui(self) -> None:
        self.profile = QComboBox()
        self.copy_button = self._button("Copy Voice", self.copy_from_voice_clone)
        self.copy_button.setToolTip("Copy the selected profile from the Voice Clone tab.")
        self.unload_model_button = self._button("Unload Model", self.unload_model)
        self.unload_model_button.setToolTip(
            "Release the cached Chatterbox V3 GPU model and ASR model memory. "
            "The next render loads them again automatically."
        )
        self.language = QComboBox()
        for code, name in SUPPORTED_LANGUAGES.items():
            self.language.addItem(f"{name} ({code})", code)
        self.language.setCurrentIndex(max(0, self.language.findData(self.settings["language"])))
        self.device = QComboBox()
        self.device.addItem("CPU", "cpu")
        runtime_device = os.environ.get("VOICEOVER_DEFAULT_DEVICE", "cuda").lower()
        if runtime_device != "cpu":
            self.device.insertItem(0, "CUDA GPU", "cuda")
        self.device.setToolTip("CUDA GPU is recommended. CPU rendering is very slow.")
        saved_device = str(self.settings["device"])
        if self.device.findData(saved_device) < 0:
            saved_device = runtime_device
        self.device.setCurrentIndex(max(0, self.device.findData(saved_device)))
        self.output_format = QComboBox()
        self.output_format.addItems(["wav", "mp3"])
        self.output_format.setCurrentText(self.settings["format"])
        self.merge_pause = QDoubleSpinBox()
        self.merge_pause.setRange(0.0, 10.0)
        self.merge_pause.setDecimals(2)
        self.merge_pause.setSingleStep(0.05)
        self.merge_pause.setValue(float(self.settings["merge_pause"]))
        self.merge_pause.setSuffix(" sec")
        self.normalize_audio = QCheckBox("Normalize completed batch after all segments render")
        self.normalize_audio.setChecked(bool(self.settings["normalize_audio"]))
        self.normalize_audio.setToolTip(
            "After all rendering, ASR checks, and automatic repairs finish: archive every "
            "original, measure every file, then write the normalized batch at OmniVoice's "
            "-20 dB active-speech RMS target."
        )
        self.retry_normalize_button = self._button(
            "Retry batch normalization", self.retry_batch_normalization
        )
        self.normalize_folder_button = self._button(
            "Normalize audio folder", self.normalize_audio_folder
        )
        self.normalize_folder_button.setToolTip(
            "Copy WAV/MP3 files into a new folder, then match OmniVoice loudness."
        )
        self.exaggeration = self._spin(0.0, 2.0, self.settings["exaggeration"], 0.05)
        self.cfg_weight = self._spin(0.0, 1.0, self.settings["cfg_weight"], 0.05)
        self.temperature = self._spin(0.1, 2.0, self.settings["temperature"], 0.05)
        self.repetition = self._spin(1.0, 2.0, self.settings["repetition_penalty"], 0.05)
        self.min_p = self._spin(0.0, 1.0, self.settings["min_p"], 0.01)
        self.top_p = self._spin(0.1, 1.0, self.settings["top_p"], 0.05)
        self.auto_qa = QCheckBox("Auto ASR repair")
        self.auto_qa.setToolTip("Transcribe every segment and rerender failed matches automatically.")
        self.auto_qa.setChecked(bool(self.settings["auto_qa"]))
        self.qa_retries = QSpinBox()
        self.qa_retries.setRange(0, 5)
        self.qa_retries.setValue(int(self.settings["qa_retries"]))
        self.asr_workers = QSpinBox()
        self.asr_workers.setRange(1, 8)
        self.asr_workers.setValue(int(self.settings["asr_workers"]))
        self.overwrite = QCheckBox("Overwrite existing")
        self.overwrite.setToolTip("Replace existing numbered segment files.")

        voice_controls = QWidget()
        voice_controls_layout = QHBoxLayout(voice_controls)
        voice_controls_layout.setContentsMargins(0, 0, 0, 0)
        voice_controls_layout.setSpacing(8)
        voice_controls_layout.addWidget(self.profile, 1)
        voice_controls_layout.addWidget(self.copy_button)
        voice_controls_layout.addWidget(self.unload_model_button)
        voice_form = QFormLayout()
        voice_form.addRow("Voice", voice_controls)
        voice_group = QGroupBox("Voice Clone V3")
        voice_group.setLayout(voice_form)
        parameter_form = QFormLayout()
        parameter_form.addRow("Runtime", self._paired(self.device, "Language", self.language))
        parameter_form.addRow(
            "Expression", self._paired(self.exaggeration, "CFG", self.cfg_weight)
        )
        parameter_form.addRow(
            "Sampling", self._paired(self.temperature, "Repeat", self.repetition)
        )
        parameter_form.addRow("Probability", self._paired(self.min_p, "Top P", self.top_p))
        parameter_group = QGroupBox("Chatterbox Multilingual V3 Parameters")
        parameter_group.setLayout(parameter_form)
        qa_form = QFormLayout()
        qa_form.addRow("Options", self._paired(self.auto_qa, "", self.overwrite))
        qa_form.addRow("Repair", self._paired(self.qa_retries, "ASR workers", self.asr_workers))
        qa_group = QGroupBox("ASR Quality Control")
        qa_group.setLayout(qa_form)
        output_form = QFormLayout()
        output_form.addRow(
            "Output", self._paired(self.output_format, "Merge pause", self.merge_pause)
        )
        output_form.addRow("", self.normalize_audio)
        output_form.addRow("", self.retry_normalize_button)
        output_form.addRow("", self.normalize_folder_button)
        output_group = QGroupBox("Output and Audio")
        output_group.setLayout(output_form)

        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(3, 3, 3, 3)
        self.rows_scroll = QScrollArea()
        self.rows_scroll.setWidgetResizable(True)
        self.rows_scroll.setWidget(self.rows_container)
        self.rows_scroll.setFixedHeight(150)
        self.add_row()
        batch_layout = QVBoxLayout()
        batch_layout.addWidget(self.rows_scroll)
        batch_layout.addWidget(self._button("+ Add batch task", self.add_row))
        batch_group = QGroupBox("Batch Processing Queue")
        batch_group.setLayout(batch_layout)

        note = QLabel(
            "V3 officially supports 23 languages, but Vietnamese (vi) is not currently included. "
            "A Vietnamese reference can still provide voice timbre for cross-language cloning, "
            "but output must use a supported language ID and may retain the reference accent."
        )
        note.setWordWrap(True)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(voice_group)
        left_layout.addWidget(batch_group)
        left_layout.addWidget(parameter_group)
        left_layout.addWidget(qa_group)
        left_layout.addWidget(output_group)
        left_layout.addWidget(note)
        left_layout.addStretch()
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setWidget(left)
        left_scroll.setMinimumWidth(520)

        self.log = TranslatedLogEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(120)
        self.segment_text_input = QPlainTextEdit()
        self.segment_text_input.setPlaceholderText(
            "Paste one or more segments here. Separate segments with a blank line."
        )
        self.segment_text_input.setMaximumHeight(110)
        self.add_segments_button = self._button("Add text segments", self.add_text_segments)
        self.segment_table = QTableWidget(0, 6)
        self.segment_table.setHorizontalHeaderLabels(
            ["#", "Time", "Text", "Status", "Direction", "Actions"]
        )
        self.segment_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.segment_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.segment_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked |
            QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.segment_table.itemChanged.connect(self.on_segment_text_changed)
        self.status_filter = QComboBox()
        self.status_filter.addItem("All files", "all")
        self.status_filter.addItem("Failed / Review", "attention")
        self.status_filter.addItem("Review required", "review")
        self.status_filter.addItem("Failed / Errors", "failed")
        self.status_filter.addItem("Pending / Processing", "processing")
        self.status_filter.addItem("Verified / Completed", "verified")
        self.status_filter.currentIndexChanged.connect(self.apply_status_filter)
        self.status_filter_count = QLabel("0 / 0 files")
        self.render_selected_button = self._button(
            "Render selected", self.render_selected_segments
        )
        self.render_selected_button.setToolTip(
            "Rerender the selected row(s). Use Ctrl or Shift to select multiple rows."
        )
        self.delete_selected_button = self._button(
            "Delete selected", self.delete_selected_segments
        )
        self.delete_selected_button.setToolTip(
            "Remove selected text rows from the source script. A backup is created first."
        )
        self.clear_list_button = self._button("Clear list", self.clear_segment_list)
        self.clear_list_button.setToolTip(
            "Detach the current script from this panel without deleting source or audio files."
        )
        filter_bar = QWidget()
        filter_layout = QHBoxLayout(filter_bar)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.addWidget(QLabel("Status filter"))
        filter_layout.addWidget(self.status_filter)
        filter_layout.addWidget(self.status_filter_count)
        filter_layout.addWidget(self.render_selected_button)
        filter_layout.addWidget(self.delete_selected_button)
        filter_layout.addWidget(self.clear_list_button)
        filter_layout.addStretch()
        self.segment_table.verticalHeader().setVisible(False)
        table_header = self.segment_table.horizontalHeader()
        for column in (0, 1, 3, 4, 5):
            table_header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        table_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.progress = QProgressBar()
        self.status = QLabel("Ready · Chatterbox Multilingual V3")
        self.status.setWordWrap(True)
        self.timing_label = QLabel("Elapsed 00:00:00 · ETA waiting for the first segment")
        self.timing_label.setWordWrap(True)
        self.timing_timer = QTimer(self)
        self.timing_timer.setInterval(1000)
        self.timing_timer.timeout.connect(self.update_timing_clock)
        self.delete_retry_timer = QTimer(self)
        self.delete_retry_timer.setInterval(round(BUSY_FILE_RETRY_SECONDS * 1000))
        self.delete_retry_timer.timeout.connect(self.process_delete_queue)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("Voice-over segments"))
        right_layout.addWidget(self.segment_text_input)
        right_layout.addWidget(self.add_segments_button)
        right_layout.addWidget(filter_bar)
        right_layout.addWidget(self.segment_table, 1)
        right_layout.addWidget(self.progress)
        right_layout.addWidget(self.status)
        right_layout.addWidget(self.timing_label)
        right_layout.addWidget(QLabel("Processing and model log"))
        right_layout.addWidget(self.log)
        splitter = QSplitter()
        splitter.addWidget(left_scroll)
        splitter.addWidget(right)
        splitter.setSizes([560, 720])
        actions = QHBoxLayout()
        self.render_button = self._button("Render batch V3", self.start_batch)
        self.stop_button = self._button("Stop", self.stop)
        self.stop_button.setEnabled(False)
        actions.addWidget(self.render_button)
        actions.addWidget(self.stop_button)
        actions.addWidget(self._button("Save Settings", self.save_settings))
        actions.addWidget(self._button("Open output", self.open_output))
        layout = QVBoxLayout(self)
        layout.addWidget(splitter)
        layout.addLayout(actions)

    def add_row(self) -> dict:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        view = QRadioButton()
        view.setToolTip("Select this batch row in the segment panel.")
        script = QLineEdit()
        script.setPlaceholderText("TXT/SRT input")
        output = QLineEdit()
        output.setPlaceholderText("Output root (auto: <script folder>/vo)")
        translator = getattr(self.parent(), "translated_ui_text", lambda value: value)
        script.setProperty("_i18n_placeholder", "TXT/SRT input")
        output.setProperty("_i18n_placeholder", "Output folder")
        script.setPlaceholderText(translator("TXT/SRT input"))
        output.setPlaceholderText(translator("Output folder"))
        browse_script = self._button("Browse", lambda: self.pick_script(script, output))
        browse_output = self._button("Output", lambda: self.pick_output(output))
        remove = self._button("X", lambda: self.remove_row(row))
        for item, stretch in (
            (view, 0), (script, 3), (browse_script, 0),
            (output, 3), (browse_output, 0), (remove, 0),
        ):
            layout.addWidget(item, stretch)
        row = {
            "widget": widget, "view": view, "script": script, "output": output,
            "last_output": None,
        }
        self.rows.append(row)
        self.rows_layout.addWidget(widget)
        view.toggled.connect(lambda checked: self.select_row(row) if checked else None)
        script.textChanged.connect(lambda _text: self.refresh_segments() if row is self.current_row else None)
        output.textChanged.connect(lambda _text: self.refresh_segments() if row is self.current_row else None)
        if len(self.rows) == 1:
            view.setChecked(True)
            self.current_row = row
        return row

    def remove_row(self, row: dict) -> None:
        if len(self.rows) == 1:
            return
        was_current = row is self.current_row
        self.rows.remove(row)
        row["widget"].deleteLater()
        if was_current:
            self.rows[0]["view"].setChecked(True)
            self.select_row(self.rows[0])

    def select_row(self, row: dict) -> None:
        if row not in self.rows:
            return
        self.current_row = row
        self.last_output = Path(row["last_output"]) if row.get("last_output") else None
        self.refresh_segments()

    def pick_script(self, edit: QLineEdit, output: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Chatterbox V3 script", "", "Script (*.txt *.srt)")
        if path:
            edit.setText(path)
            source = Path(path)
            output.setText(str(source.parent / "vo"))
            self.refresh_segments()

    def pick_output(self, edit: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, "Chatterbox V3 output")
        if path:
            edit.setText(path)
            self.refresh_segments()

    def add_text_segments(self) -> None:
        try:
            row = self.current_row
            if row is None:
                raise ValueError("Select a batch row first.")
            script_text = row["script"].text().strip()
            if not script_text:
                raise ValueError("Choose a TXT/SRT script path first.")
            script = Path(script_text)
            if script.suffix.lower() not in {".txt", ".srt"}:
                raise ValueError("The script path must end in .txt or .srt.")
            blocks = [
                " ".join(block.split())
                for block in re.split(r"\n\s*\n", self.segment_text_input.toPlainText().strip())
                if block.strip()
            ]
            if not blocks:
                raise ValueError("Paste at least one text segment.")
            script.parent.mkdir(parents=True, exist_ok=True)
            existing = script.read_text(encoding="utf-8").rstrip() if script.is_file() else ""
            addition = "\n\n".join(blocks)
            script.write_text(
                (existing + "\n\n" + addition if existing else addition) + "\n",
                encoding="utf-8",
            )
            self.segment_text_input.clear()
            self.refresh_segments()
            self.status.setText(f"Added {len(blocks)} text segment(s).")
        except Exception as exc:
            QMessageBox.warning(self, "Cannot add text segments", str(exc))

    @staticmethod
    def _srt_timestamp(seconds: float) -> str:
        milliseconds = max(0, round(seconds * 1000))
        hours, remainder = divmod(milliseconds, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        seconds, milliseconds = divmod(remainder, 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    def _write_segments(self, script: Path, segments: list) -> None:
        if script.suffix.lower() == ".srt":
            blocks = []
            for number, segment in enumerate(segments, 1):
                blocks.append(
                    f"{number}\n{self._srt_timestamp(segment.start_seconds or 0.0)} --> "
                    f"{self._srt_timestamp(segment.end_seconds or 0.0)}\n{segment.text}"
                )
            content = "\n\n".join(blocks) + ("\n" if blocks else "")
        else:
            content = "\n".join(segment.text for segment in segments)
            if segments:
                content += "\n"
        script.write_text(content, encoding="utf-8")

    def on_segment_text_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 2 or self.current_row is None:
            return
        script = Path(self.current_row["script"].text().strip())
        if not script.is_file():
            return
        try:
            position_item = self.segment_table.item(item.row(), 0)
            position = int(position_item.text()) if position_item else item.row() + 1
            segments = parse_input(script)
            if not 1 <= position <= len(segments):
                return
            new_text = " ".join(item.text().split()).strip()
            if not new_text:
                raise ValueError("Segment text cannot be empty.")
            if segments[position - 1].text == new_text:
                return
            segments[position - 1].text = new_text
            self._write_segments(script, segments)
            item.setText(new_text)
            key = self._rerender_key(self.current_row, position)
            self.edited_segment_keys.add(key)
            self.on_segment_status(position, "Text changed · Rerender required")
            self.log.appendPlainText(
                f"Updated source text for segment {position}; rerender uses the new text."
            )
        except Exception as exc:
            QMessageBox.warning(self, "Cannot update segment text", str(exc))
            self.refresh_segments()

    def segment_audio_path(self, position: int, row: dict | None = None) -> Path:
        row = row or self.current_row or {}
        script = Path(row.get("script").text()) if row.get("script") else Path()
        try:
            total = len(parse_input(script)) if script.is_file() else 1
        except Exception:
            total = 1
        width = max(3, len(str(total)))
        output_root = row.get("output").text() if row.get("output") else ""
        session = Path(row.get("last_output") or output_root)
        stem = f"{position:0{width}d}"
        preferred = session / f"{stem}.{self.output_format.currentText()}"
        if preferred.is_file():
            return preferred
        for extension in ("wav", "mp3"):
            candidate = session / f"{stem}.{extension}"
            if candidate.is_file():
                return candidate
        return preferred

    def refresh_segments(self) -> None:
        if not hasattr(self, "segment_table"):
            return
        row = self.current_row
        script = Path(row["script"].text().strip()) if row else Path()
        if not script.is_file():
            self.segment_table.setRowCount(0)
            self.apply_status_filter()
            return
        try:
            segments = parse_input(script)
        except Exception:
            self.segment_table.setRowCount(0)
            self.apply_status_filter()
            return
        saved_status: dict[int, str] = {}
        if row and row.get("last_output"):
            report_path = Path(row["last_output"]) / "chatterbox_v3_asr_report.csv"
            try:
                with report_path.open(encoding="utf-8-sig", newline="") as handle:
                    for report_row in csv.DictReader(handle):
                        status = report_row.get("status", "")
                        label = {
                            "verified": "Verified · ASR passed",
                            "needs_review": "Review required",
                            "completed": "Completed",
                        }.get(status)
                        if label:
                            saved_status[int(report_row["segment"])] = label
            except (OSError, ValueError, KeyError):
                pass
        self.segment_table.setRowCount(len(segments))
        for table_row, segment in enumerate(segments):
            position = table_row + 1
            audio = self.segment_audio_path(position, row)
            completed = audio.is_file() and audio.stat().st_size > 0
            timing = ""
            if segment.start_seconds is not None:
                timing = f"{segment.start_seconds:.2f}-{segment.end_seconds:.2f}"
            number_item = QTableWidgetItem(str(position))
            number_item.setFlags(number_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            time_item = QTableWidgetItem(timing)
            time_item.setFlags(time_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            text_item = QTableWidgetItem(segment.text)
            text_item.setToolTip("Double-click or press F2 to edit, then click ↻ to rerender.")
            self.segment_table.setItem(table_row, 0, number_item)
            self.segment_table.setItem(table_row, 1, time_item)
            self.segment_table.setItem(table_row, 2, text_item)
            key = self._rerender_key(row, position)
            if key in self.delete_queue_keys:
                row_status = "Delete queued · Click 🗑 to remove"
            elif key in self.rerender_queue_keys:
                row_status = "Rerender queued · Click ↻ to remove"
            elif key in self.edited_segment_keys:
                row_status = "Text changed · Rerender required"
            else:
                row_status = saved_status.get(position, "Completed") if completed else "Pending"
            status_item = QTableWidgetItem(row_status)
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.segment_table.setItem(
                table_row, 3, status_item
            )
            direction = QTableWidgetItem("Default")
            direction.setToolTip("Uses the shared Chatterbox V3 settings.")
            direction.setFlags(direction.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.segment_table.setItem(table_row, 4, direction)
            actions = QWidget()
            action_layout = QHBoxLayout(actions)
            action_layout.setContentsMargins(0, 0, 0, 0)
            play = QPushButton()
            play.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
            play.setToolTip("Play segment")
            play.setEnabled(completed)
            play.clicked.connect(lambda _checked=False, p=position: self.play_segment(p))
            rerender = QPushButton()
            queued = self._rerender_key(row, position) in self.rerender_queue_keys
            rerender.setIcon(self.style().standardIcon(
                QStyle.StandardPixmap.SP_DialogCancelButton
                if queued else QStyle.StandardPixmap.SP_BrowserReload
            ))
            rerender.setToolTip(
                "Remove this segment from the rerender queue"
                if queued else "Rerender and overwrite segment"
            )
            rerender.clicked.connect(
                lambda _checked=False, p=position: self.start_segment_render(p)
            )
            delete = QPushButton()
            delete_queued = key in self.delete_queue_keys
            delete.setIcon(self.style().standardIcon(
                QStyle.StandardPixmap.SP_DialogCancelButton
                if delete_queued else QStyle.StandardPixmap.SP_TrashIcon
            ))
            delete.setToolTip(
                "Remove this file from the delete queue"
                if delete_queued else "Delete segment audio (queued safely while processing)"
            )
            delete.setEnabled(completed or delete_queued)
            delete.clicked.connect(lambda _checked=False, p=position: self.delete_segment(p))
            for button in (play, rerender, delete):
                button.setFixedWidth(30)
                action_layout.addWidget(button)
            self.segment_table.setCellWidget(table_row, 5, actions)
        self.apply_status_filter()

    @staticmethod
    def _status_group(status: str) -> str:
        value = status.casefold()
        if "review" in value:
            return "review"
        if any(word in value for word in ("failed", "error", "file open", "stopped")):
            return "failed"
        if any(word in value for word in (
            "pending", "render", "waiting", "checking", "queued", "retrying",
            "initial", "text changed", "repair",
        )):
            return "processing"
        if any(word in value for word in ("verified", "completed", "passed")):
            return "verified"
        return "processing"

    def apply_status_filter(self, *_args) -> None:
        if not hasattr(self, "status_filter"):
            return
        selected = str(self.status_filter.currentData() or "all")
        shown = 0
        total = self.segment_table.rowCount()
        for row in range(total):
            item = self.segment_table.item(row, 3)
            group = self._status_group(item.text() if item else "Pending")
            visible = (
                selected == "all" or group == selected or
                selected == "attention" and group in {"failed", "review"}
            )
            self.segment_table.setRowHidden(row, not visible)
            shown += int(visible)
        self.status_filter_count.setText(f"{shown} / {total} files")

    def play_segment(self, position: int) -> None:
        path = self.segment_audio_path(position)
        if path.is_file():
            os.startfile(path)

    @staticmethod
    def _rerender_key(row: dict | None, position: int) -> tuple[int, int]:
        return id(row), position

    def _set_rerender_button_queued(self, position: int, queued: bool) -> None:
        for table_row in range(self.segment_table.rowCount()):
            item = self.segment_table.item(table_row, 0)
            if not item or item.text() != str(position):
                continue
            actions = self.segment_table.cellWidget(table_row, 5)
            if actions and actions.layout():
                button = actions.layout().itemAt(1).widget()
                if button:
                    button.setIcon(self.style().standardIcon(
                        QStyle.StandardPixmap.SP_DialogCancelButton
                        if queued else QStyle.StandardPixmap.SP_BrowserReload
                    ))
                    button.setToolTip(
                        "Remove this segment from the rerender queue"
                        if queued else "Rerender and overwrite segment"
                    )
            break

    def toggle_rerender_queue(self, row: dict, position: int) -> None:
        key = self._rerender_key(row, position)
        if key in self.rerender_queue_keys:
            self.rerender_queue_keys.remove(key)
            self.rerender_queue = [
                item for item in self.rerender_queue
                if self._rerender_key(item["row"], item["position"]) != key
            ]
            if row is self.current_row:
                self._set_rerender_button_queued(position, False)
                self.refresh_segments()
            self.log.appendPlainText(f"Removed segment {position} from rerender queue.")
            return
        if key in self.delete_queue_keys:
            self.delete_queue_keys.remove(key)
            self.delete_queue = [
                item for item in self.delete_queue
                if self._rerender_key(item["row"], item["position"]) != key
            ]
        self.rerender_queue_keys.add(key)
        self.rerender_queue.append({"row": row, "position": position})
        if row is self.current_row:
            self._set_rerender_button_queued(position, True)
            self.on_segment_status(position, "Rerender queued · Click ↻ to remove")
        self.log.appendPlainText(
            f"Queued segment {position} for rerender ({len(self.rerender_queue)} waiting)."
        )

    def _set_delete_button_queued(self, position: int, queued: bool) -> None:
        for table_row in range(self.segment_table.rowCount()):
            item = self.segment_table.item(table_row, 0)
            if not item or item.text() != str(position):
                continue
            actions = self.segment_table.cellWidget(table_row, 5)
            if actions and actions.layout():
                button = actions.layout().itemAt(2).widget()
                if button:
                    button.setIcon(self.style().standardIcon(
                        QStyle.StandardPixmap.SP_DialogCancelButton
                        if queued else QStyle.StandardPixmap.SP_TrashIcon
                    ))
                    button.setToolTip(
                        "Remove this file from the delete queue"
                        if queued else "Delete segment audio (queued safely while processing)"
                    )
            break

    def delete_segment(self, position: int) -> None:
        row = self.current_row
        if row is None:
            return
        key = self._rerender_key(row, position)
        if key in self.delete_queue_keys:
            self.delete_queue_keys.remove(key)
            self.delete_queue = [
                item for item in self.delete_queue
                if self._rerender_key(item["row"], item["position"]) != key
            ]
            self._set_delete_button_queued(position, False)
            self.refresh_segments()
            self.log.appendPlainText(f"Removed segment {position} from delete queue.")
            if not self.delete_queue:
                self.delete_retry_timer.stop()
            return
        if key in self.rerender_queue_keys:
            self.rerender_queue_keys.remove(key)
            self.rerender_queue = [
                item for item in self.rerender_queue
                if self._rerender_key(item["row"], item["position"]) != key
            ]
        self.delete_queue_keys.add(key)
        self.delete_queue.append({"row": row, "position": position})
        self._set_delete_button_queued(position, True)
        self.on_segment_status(position, "Delete queued · Click 🗑 to remove")
        self.log.appendPlainText(
            f"Queued segment {position} audio for deletion ({len(self.delete_queue)} waiting)."
        )
        self.process_delete_queue()

    def process_delete_queue(self) -> None:
        if self.thread and self.thread.isRunning():
            if self.delete_queue:
                self.delete_retry_timer.start()
            return
        remaining = []
        for item in self.delete_queue:
            row = item["row"]
            position = item["position"]
            key = self._rerender_key(row, position)
            path = self.segment_audio_path(position, row)
            try:
                path.unlink(missing_ok=True)
                self.delete_queue_keys.discard(key)
                self.log.appendPlainText(f"Deleted segment audio: {path}")
            except PermissionError:
                remaining.append(item)
                if row is self.current_row:
                    self.on_segment_status(
                        position,
                        f"File open · Delete retry in {BUSY_FILE_RETRY_SECONDS:g}s",
                    )
                self.log.appendPlainText(
                    f"Delete deferred; file is open: {path.name}. Retrying in "
                    f"{BUSY_FILE_RETRY_SECONDS:g}s."
                )
            except OSError as exc:
                remaining.append(item)
                self.log.appendPlainText(f"Delete failed for {path.name}: {exc}")
        self.delete_queue = remaining
        if remaining:
            self.delete_retry_timer.start()
        else:
            self.delete_retry_timer.stop()
        self.refresh_segments()

    def retry_batch_normalization(self) -> None:
        if self.thread and self.thread.isRunning():
            QMessageBox.information(self, "Output and Audio", "Wait for rendering to finish first.")
            return
        if self.normalize_thread and self.normalize_thread.isRunning():
            return
        try:
            row = self.current_row
            if row is None or not row.get("last_output"):
                raise ValueError("Select a batch row with a completed V3 render session.")
            session = Path(row["last_output"])
            script = Path(row["script"].text().strip())
            if not session.is_dir() or not script.is_file():
                raise ValueError("The selected render session or source script is missing.")
            total = len(parse_input(script))
            width = max(3, len(str(total)))
            files = [
                session / f"{position:0{width}d}.{self.output_format.currentText()}"
                for position in range(1, total + 1)
            ]
            if not files or not all(path.is_file() for path in files):
                raise ValueError("Every numbered segment must exist before batch normalization.")
            self.normalize_worker = ChatterboxNormalizeWorker(files)
            self.normalize_thread = QThread(self)
            self.normalize_worker.moveToThread(self.normalize_thread)
            self.normalize_thread.started.connect(self.normalize_worker.run)
            self.normalize_worker.progress.connect(self.on_normalize_progress)
            self.normalize_worker.completed.connect(self.on_normalize_completed)
            self.normalize_worker.failed.connect(self.on_normalize_failed)
            self.normalize_worker.completed.connect(self.normalize_thread.quit)
            self.normalize_worker.failed.connect(self.normalize_thread.quit)
            self.normalize_thread.finished.connect(self.on_normalize_finished)
            self.retry_normalize_button.setEnabled(False)
            self.status.setText("Matching V3 output loudness to OmniVoice...")
            self.reset_timing(len(files), "normalizing")
            self.normalize_thread.start()
        except Exception as exc:
            QMessageBox.warning(self, "Cannot normalize batch", str(exc))

    def normalize_audio_folder(self) -> None:
        if self.thread and self.thread.isRunning():
            QMessageBox.information(
                self, "Normalize audio folder", "Wait for rendering to finish first."
            )
            return
        if self.normalize_thread and self.normalize_thread.isRunning():
            return
        source_text = QFileDialog.getExistingDirectory(
            self, "Select a WAV/MP3 folder to normalize"
        )
        if not source_text:
            return
        source = Path(source_text)
        destination = source.with_name(source.name + "_normalized")
        suffix = 1
        while destination.exists():
            destination = source.with_name(f"{source.name}_normalized_{suffix:02d}")
            suffix += 1
        self.normalize_worker = ChatterboxFolderNormalizeWorker(source, destination)
        self.normalize_thread = QThread(self)
        self.normalize_worker.moveToThread(self.normalize_thread)
        self.normalize_thread.started.connect(self.normalize_worker.run)
        self.normalize_worker.progress.connect(self.on_normalize_progress)
        self.normalize_worker.completed.connect(self.on_normalize_completed)
        self.normalize_worker.failed.connect(self.on_normalize_failed)
        self.normalize_worker.completed.connect(self.normalize_thread.quit)
        self.normalize_worker.failed.connect(self.normalize_thread.quit)
        self.normalize_thread.finished.connect(self.on_normalize_finished)
        self.retry_normalize_button.setEnabled(False)
        self.normalize_folder_button.setEnabled(False)
        self.status.setText(f"Copying and normalizing folder: {source.name}")
        file_count = sum(
            1 for path in source.iterdir()
            if path.is_file() and path.suffix.lower() in {".wav", ".mp3"}
        )
        self.reset_timing(file_count, "normalizing")
        self.normalize_thread.start()

    def on_normalize_progress(self, message: str) -> None:
        self.status.setText(message)
        self.timing_mode = "normalizing"
        self.update_timing_clock()
        self.log.appendPlainText(message)

    def on_normalize_completed(self, session: str) -> None:
        self.last_output = Path(session)
        self.status.setText(f"Batch normalization completed: {session}")
        self.timing_completed_segments = self.timing_total_segments
        elapsed = (
            time.monotonic() - self.timing_started_at if self.timing_started_at is not None else 0
        )
        self.timing_label.setText(
            f"Normalization completed · Elapsed {self._duration(elapsed)}"
        )
        self.log.appendPlainText(self.status.text())

    def on_normalize_failed(self, details: str) -> None:
        self.status.setText("Batch normalization failed.")
        self.log.appendPlainText(details)
        QMessageBox.critical(self, "Batch normalization failed", details[-4000:])

    def on_normalize_finished(self) -> None:
        self.timing_timer.stop()
        self.normalize_worker = None
        self.normalize_thread = None
        self.retry_normalize_button.setEnabled(True)
        self.normalize_folder_button.setEnabled(True)
        self.refresh_segments()

    def refresh_profiles(self) -> None:
        selected = str(self.profile.currentData() or self.settings.get("profile", ""))
        self.profile.clear()
        for name in self.profile_store.names():
            self.profile.addItem(name, name)
        index = self.profile.findData(selected)
        if index >= 0:
            self.profile.setCurrentIndex(index)

    def copy_from_voice_clone(self) -> None:
        self.refresh_profiles()
        name = str(self.selected_profile() or "")
        index = self.profile.findData(name)
        if index < 0:
            QMessageBox.warning(
                self, "Copy Voice Clone", "No voice profile is selected on the Voice Clone tab."
            )
            return
        self.profile.setCurrentIndex(index)
        profile = self.profile_store.load(name)
        language = str(profile.get("language", ""))
        if language in SUPPORTED_LANGUAGES:
            self.language.setCurrentIndex(self.language.findData(language))
        else:
            self.log.appendPlainText(
                f"Copied voice '{name}'. Reference language '{language}' is not natively "
                "supported by V3; the current output language was preserved."
            )
        self.status.setText(f"Copied voice profile from Voice Clone: {name}")

    def unload_model(self) -> None:
        if self.thread and self.thread.isRunning():
            QMessageBox.information(
                self, "Unload Chatterbox V3", "Wait for the current render to finish first."
            )
            return
        if self.preload_thread and self.preload_thread.isRunning():
            QMessageBox.information(
                self, "Unload Chatterbox V3", "Wait for startup model loading to finish first."
            )
            return
        had_tts = bool(_CHATTERBOX_MODEL_CACHE)
        had_asr = bool(_CHATTERBOX_ASR_CACHE)
        _CHATTERBOX_MODEL_CACHE.clear()
        _CHATTERBOX_ASR_CACHE.clear()
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                try:
                    torch.cuda.ipc_collect()
                except RuntimeError:
                    pass
        except (ImportError, RuntimeError):
            pass
        released = []
        if had_tts:
            released.append("Chatterbox GPU model")
        if had_asr:
            released.append("ASR model")
        detail = ", ".join(released) if released else "no cached model was loaded"
        message = f"Model memory released · {detail}. The next render reloads automatically."
        self.status.setText(message)
        self.log.appendPlainText(message)

    def save_settings(self) -> None:
        values = {
            "profile": str(self.profile.currentData() or ""),
            "language": str(self.language.currentData()), "device": str(self.device.currentData()),
            "format": self.output_format.currentText(), "exaggeration": self.exaggeration.value(),
            "cfg_weight": self.cfg_weight.value(), "temperature": self.temperature.value(),
            "repetition_penalty": self.repetition.value(), "min_p": self.min_p.value(),
            "top_p": self.top_p.value(), "auto_qa": self.auto_qa.isChecked(),
            "qa_retries": self.qa_retries.value(), "asr_workers": self.asr_workers.value(),
            "normalize_audio": self.normalize_audio.isChecked(),
            "merge_pause": self.merge_pause.value(),
        }
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(values, indent=2), encoding="utf-8")
        self.settings = values
        self.status.setText(f"Settings saved: {self.config_path}")

    def start_batch(self) -> None:
        if self.preload_thread and self.preload_thread.isRunning():
            QMessageBox.information(
                self, "Voice Clone V3", "Chatterbox Multilingual V3 is preloading. Please wait."
            )
            return
        if self.thread and self.thread.isRunning():
            QMessageBox.warning(self, "Voice Clone V3", "A Voice Clone V3 task is already running.")
            return
        try:
            name = str(self.profile.currentData() or "")
            if not name:
                raise ValueError("Select or copy a voice profile first.")
            queue = []
            for row in self.rows:
                script_text = row["script"].text().strip()
                output_text = row["output"].text().strip()
                script = Path(script_text)
                if not script_text:
                    continue
                if not script.is_file():
                    raise ValueError(f"Script does not exist: {script}")
                if not output_text:
                    raise ValueError(f"Select an output folder for {script.name}")
                output = Path(output_text)
                queue.append({"script": script, "output": output, "row": row})
            if not queue:
                raise ValueError("The batch contains no valid tasks.")
            self.save_settings()
            self.queue = queue
            self.queue_index = 0
            self.batch_task_total = len(queue)
            self.reset_timing(sum(len(parse_input(job["script"])) for job in queue), "batch")
            self.render_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self._start_next()
        except Exception as exc:
            QMessageBox.critical(self, "Cannot run Voice Clone V3", str(exc))

    def _start_next(self) -> None:
        job = self.queue[self.queue_index]
        session = self._new_session(job["output"])
        job["row"]["last_output"] = session
        self.active_render_row = job["row"]
        self.current_row = job["row"]
        job["row"]["view"].setChecked(True)
        self.last_output = session
        self.refresh_segments()
        self.single_segment_render = False
        self._launch_worker(job, session)

    @staticmethod
    def _new_session(root: Path) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session = root / timestamp
        suffix = 1
        while session.exists():
            session = root / f"{timestamp}_{suffix:02d}"
            suffix += 1
        return session

    def _launch_worker(
        self, job: dict, session: Path, positions: list[int] | None = None,
        overwrite: bool | None = None,
    ) -> None:
        self.render_succeeded = False
        self.worker = ChatterboxRenderWorker(
            self.profile_store.load(str(self.profile.currentData())), job["script"], session,
            str(self.language.currentData()), str(self.device.currentData()),
            self.output_format.currentText(), self.exaggeration.value(), self.cfg_weight.value(),
            self.temperature.value(), self.repetition.value(), self.min_p.value(), self.top_p.value(),
            self.auto_qa.isChecked(), self.qa_retries.value(), self.asr_workers.value(),
            self.overwrite.isChecked() if overwrite is None else overwrite,
            positions, self.normalize_audio.isChecked(),
        )
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.on_progress)
        self.worker.timing.connect(self.on_timing)
        self.worker.pipeline_phase.connect(self.on_pipeline_phase)
        self.worker.segment_status.connect(self.on_segment_status)
        self.worker.completed.connect(self.on_completed)
        self.worker.failed.connect(self.on_failed)
        self.worker.cancelled.connect(self.on_cancelled)
        self.worker.completed.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.worker.cancelled.connect(self.thread.quit)
        self.thread.finished.connect(self.on_thread_finished)
        self.timing_task_base = self.timing_completed_segments
        if self.single_segment_render:
            if positions and len(positions) > 1:
                self.status.setText(f"Rerendering {len(positions)} selected segments...")
            else:
                self.status.setText(f"Rerendering segment {positions[0]}...")
        else:
            self.status.setText(
                f"Batch {self.queue_index + 1}/{len(self.queue)} · loading/rendering..."
            )
        self.thread.start()

    def start_segment_render(self, position: int) -> None:
        self._start_positions_render([position], toggle_when_busy=True)

    def _selected_visible_positions(self) -> list[int]:
        return sorted({
            index.row() + 1 for index in self.segment_table.selectionModel().selectedRows()
            if not self.segment_table.isRowHidden(index.row())
        })

    def render_selected_segments(self) -> None:
        positions = self._selected_visible_positions()
        if not positions:
            QMessageBox.information(
                self, "Render selected", "Select one or more visible rows first."
            )
            return
        self._start_positions_render(positions, toggle_when_busy=False)

    def _clear_row_runtime_state(self, row: dict) -> None:
        row_id = id(row)
        self.rerender_queue = [item for item in self.rerender_queue if item["row"] is not row]
        self.delete_queue = [item for item in self.delete_queue if item["row"] is not row]
        self.rerender_queue_keys = {
            key for key in self.rerender_queue_keys if key[0] != row_id
        }
        self.delete_queue_keys = {
            key for key in self.delete_queue_keys if key[0] != row_id
        }
        self.edited_segment_keys = {
            key for key in self.edited_segment_keys if key[0] != row_id
        }
        row["last_output"] = None
        if row is self.current_row:
            self.last_output = None

    def delete_selected_segments(self) -> None:
        if self.thread and self.thread.isRunning():
            QMessageBox.information(
                self, "Delete selected", "Stop or wait for rendering to finish first."
            )
            return
        positions = self._selected_visible_positions()
        if not positions:
            QMessageBox.information(
                self, "Delete selected", "Select one or more visible rows first."
            )
            return
        row = self.current_row
        if row is None:
            return
        script = Path(row["script"].text().strip())
        try:
            segments = parse_input(script)
            backup = script.with_name(
                f"{script.name}.before_delete_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
            )
            shutil.copy2(script, backup)
            selected = set(positions)
            remaining = [
                segment for position, segment in enumerate(segments, 1)
                if position not in selected
            ]
            self._write_segments(script, remaining)
            self._clear_row_runtime_state(row)
            self.refresh_segments()
            message = (
                f"Deleted {len(positions)} segment(s). Source backup: {backup.name}. "
                "The previous audio session was preserved but detached."
            )
            self.status.setText(message)
            self.log.appendPlainText(message)
        except Exception as exc:
            QMessageBox.warning(self, "Cannot delete selected segments", str(exc))

    def clear_segment_list(self) -> None:
        if self.thread and self.thread.isRunning():
            QMessageBox.information(
                self, "Clear list", "Stop or wait for rendering to finish first."
            )
            return
        row = self.current_row
        if row is None:
            return
        old_script = row["script"].text().strip()
        self._clear_row_runtime_state(row)
        row["script"].clear()
        self.segment_text_input.clear()
        self.refresh_segments()
        message = "List cleared. Source and rendered audio files were not deleted."
        if old_script:
            message += f" Previous source: {old_script}"
        self.status.setText(message)
        self.log.appendPlainText(message)

    def _start_positions_render(
        self, positions: list[int], toggle_when_busy: bool = False,
    ) -> None:
        if self.preload_thread and self.preload_thread.isRunning():
            QMessageBox.information(
                self, "Voice Clone V3", "Chatterbox Multilingual V3 is preloading. Please wait."
            )
            return
        if self.thread and self.thread.isRunning():
            if self.current_row is not None:
                for position in positions:
                    key = self._rerender_key(self.current_row, position)
                    if toggle_when_busy or key not in self.rerender_queue_keys:
                        self.toggle_rerender_queue(self.current_row, position)
            return
        try:
            row = self.current_row
            if row is None:
                raise ValueError("Select a batch row first.")
            script = Path(row["script"].text().strip())
            if not script.is_file():
                raise ValueError("Choose a valid TXT/SRT script first.")
            output_text = row["output"].text().strip()
            if not output_text:
                raise ValueError("Choose an output folder first.")
            session = Path(row["last_output"]) if row.get("last_output") else self._new_session(Path(output_text))
            row["last_output"] = session
            self.last_output = session
            self.active_render_row = row
            self.queue = []
            self.single_segment_render = True
            self.active_selected_positions = list(positions)
            self.reset_timing(len(positions), "segment")
            self.render_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self._launch_worker(
                {"script": script, "output": Path(output_text), "row": row},
                session, positions, True,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Cannot rerender segment", str(exc))

    def _start_queued_rerender(self) -> bool:
        while self.rerender_queue:
            item = self.rerender_queue.pop(0)
            row = item["row"]
            position = item["position"]
            self.rerender_queue_keys.discard(self._rerender_key(row, position))
            script = Path(row["script"].text().strip())
            output_text = row["output"].text().strip()
            if not script.is_file() or not output_text:
                self.log.appendPlainText(
                    f"Skipped queued segment {position}: script or output folder is missing."
                )
                continue
            session = (
                Path(row["last_output"]) if row.get("last_output")
                else self._new_session(Path(output_text))
            )
            row["last_output"] = session
            self.current_row = row
            self.active_render_row = row
            self.last_output = session
            row["view"].setChecked(True)
            self.refresh_segments()
            self.single_segment_render = True
            self.active_selected_positions = [position]
            self.queued_rerender_active = True
            self.reset_timing(1, "segment")
            self.render_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.on_segment_status(position, "Queued rerender · Starting")
            self._launch_worker(
                {"script": script, "output": Path(output_text), "row": row},
                session, [position], True,
            )
            return True
        return False

    def on_progress(self, done: int, total: int, message: str) -> None:
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(done)
        if self.single_segment_render:
            self.status.setText(message)
        else:
            self.status.setText(f"Batch {self.queue_index + 1}/{len(self.queue)} · {message}")
        if "normaliz" in message.lower() or "loudness" in message.lower():
            self.timing_mode = "normalizing"
            self.update_timing_clock()
        self.log.appendPlainText(message)

    @staticmethod
    def _duration(seconds: float) -> str:
        seconds = max(0, round(seconds))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def reset_timing(self, total_segments: int, mode: str) -> None:
        self.timing_started_at = time.monotonic()
        self.timing_total_segments = max(0, total_segments)
        self.timing_completed_segments = 0
        self.timing_task_base = 0
        self.timing_last_segment = 0.0
        self.timing_mode = mode
        self.pipeline_phase_name = ""
        self.pipeline_phase_done = 0
        self.pipeline_phase_total = 0
        self.pipeline_phase_started_at = None
        self.timing_timer.start()
        self.update_timing_clock()

    def on_timing(
        self, completed: int, _task_total: int, _worker_elapsed: float,
        segment_seconds: float,
    ) -> None:
        self.timing_completed_segments = min(
            self.timing_total_segments, self.timing_task_base + completed
        )
        if segment_seconds > 0:
            self.timing_last_segment = segment_seconds
        self.update_timing_clock()

    def on_segment_status(self, position: int, status: str) -> None:
        for row in range(self.segment_table.rowCount()):
            item = self.segment_table.item(row, 0)
            if item and item.text() == str(position):
                queued = (
                    self._rerender_key(self.current_row, position) in self.rerender_queue_keys
                )
                delete_queued = (
                    self._rerender_key(self.current_row, position) in self.delete_queue_keys
                )
                status_item = QTableWidgetItem(
                    "Delete queued · Click 🗑 to remove" if delete_queued else
                    "Rerender queued · Click ↻ to remove" if queued else status
                )
                if queued or delete_queued:
                    status_item.setToolTip(f"Current pipeline status: {status}")
                self.segment_table.setItem(row, 3, status_item)
                audio_ready = self.segment_audio_path(position).is_file()
                replacing_audio = status.startswith((
                    "Error · Waiting", "Regenerating", "Initial rendering",
                    "File open", "Retrying open file",
                ))
                actions = self.segment_table.cellWidget(row, 5)
                if actions and actions.layout():
                    play = actions.layout().itemAt(0).widget()
                    delete = actions.layout().itemAt(2).widget()
                    if play:
                        play.setEnabled(audio_ready and not replacing_audio)
                    if delete:
                        delete.setEnabled(audio_ready or delete_queued)
                break
        self.apply_status_filter()

    def on_pipeline_phase(self, phase: str, done: int, total: int) -> None:
        if not self.single_segment_render and self.queue:
            phase = f"Task {self.queue_index + 1}/{len(self.queue)} · {phase}"
        if phase != self.pipeline_phase_name:
            self.pipeline_phase_name = phase
            self.pipeline_phase_started_at = time.monotonic()
        self.pipeline_phase_done = done
        self.pipeline_phase_total = total
        self.update_timing_clock()

    def update_timing_clock(self) -> None:
        if self.timing_started_at is None:
            return
        elapsed = time.monotonic() - self.timing_started_at
        done = self.timing_completed_segments
        total = self.timing_total_segments
        if self.timing_mode == "normalizing":
            self.timing_label.setText(
                f"Post-processing · Elapsed {self._duration(elapsed)} · Normalizing loudness"
            )
            return
        if self.pipeline_phase_name and self.pipeline_phase_total:
            phase_elapsed = time.monotonic() - (
                self.pipeline_phase_started_at or self.timing_started_at
            )
            phase_done = self.pipeline_phase_done
            phase_total = self.pipeline_phase_total
            if phase_done <= 0:
                phase_eta = "ETA waiting for the first completed file"
            elif phase_done >= phase_total:
                phase_eta = "ETA 00:00:00"
            else:
                remaining = (phase_elapsed / phase_done) * (phase_total - phase_done)
                finish = datetime.fromtimestamp(time.time() + remaining).strftime("%H:%M:%S")
                phase_eta = f"ETA {self._duration(remaining)} · Est. finish {finish}"
            self.timing_label.setText(
                f"{self.pipeline_phase_name} {phase_done}/{phase_total} · "
                f"Total elapsed {self._duration(elapsed)} · {phase_eta}"
            )
            return
        prefix = "Batch" if self.timing_mode == "batch" else "Segment"
        if done <= 0:
            eta_text = "ETA waiting for the first completed segment"
        elif done >= total:
            eta_text = "Render ETA 00:00:00"
        else:
            average = elapsed / done
            eta = average * (total - done)
            finish = datetime.fromtimestamp(time.time() + eta).strftime("%H:%M:%S")
            eta_text = (
                f"ETA {self._duration(eta)} · Est. finish {finish} · "
                f"Avg {average:.1f}s/segment"
            )
        last = (
            f" · Last {self.timing_last_segment:.1f}s" if self.timing_last_segment > 0 else ""
        )
        self.timing_label.setText(
            f"{prefix} {done}/{total} · Elapsed {self._duration(elapsed)} · {eta_text}{last}"
        )

    def on_completed(self, output: str) -> None:
        self.render_succeeded = True
        self.last_output = Path(output)
        if self.active_render_row is not None:
            self.active_render_row["last_output"] = self.last_output
            row_id = id(self.active_render_row)
            if self.worker and self.worker.positions is not None:
                for position in self.worker.positions:
                    self.edited_segment_keys.discard((row_id, position))
            else:
                self.edited_segment_keys = {
                    key for key in self.edited_segment_keys if key[0] != row_id
                }
        self.log.appendPlainText(f"Completed: {output}")
        self.refresh_segments()

    def on_failed(self, details: str) -> None:
        self.render_succeeded = False
        self.status.setText("Voice Clone V3 failed.")
        self.log.appendPlainText(details)
        self.queue = []
        QMessageBox.critical(self, "Voice Clone V3 failed", details[-4000:])

    def on_cancelled(self, message: str) -> None:
        self.render_succeeded = False
        self.status.setText("Voice Clone V3 stopped.")
        self.log.appendPlainText(message)
        self.queue = []

    def on_thread_finished(self) -> None:
        self.worker = None
        self.thread = None
        if self.delete_queue:
            self.process_delete_queue()
        if self.single_segment_render:
            self.timing_timer.stop()
            self.timing_mode = "segment"
            self.update_timing_clock()
            self.single_segment_render = False
            was_queued = self.queued_rerender_active
            selected_count = len(self.active_selected_positions)
            self.active_selected_positions = []
            self.queued_rerender_active = False
            self.status.setText(
                f"Selected rerender completed: {selected_count} segment(s)."
                if self.render_succeeded else "Selected rerender stopped or failed."
            )
            self.refresh_segments()
            if self.render_succeeded and self._start_queued_rerender():
                return
            self.render_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            if was_queued and self.render_succeeded:
                self.status.setText("Rerender queue completed.")
                QApplication.beep()
            return
        if self.queue and self.queue_index + 1 < len(self.queue):
            self.queue_index += 1
            self._start_next()
            return
        if self.render_succeeded and self.rerender_queue:
            self.queue = []
            if self._start_queued_rerender():
                return
        self.timing_timer.stop()
        self.timing_mode = "batch"
        self.update_timing_clock()
        elapsed = (
            time.monotonic() - self.timing_started_at if self.timing_started_at is not None else 0
        )
        self.queue = []
        self.render_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        if self.render_succeeded:
            self.status.setText(
                f"V3 batch completed: {self.batch_task_total} task(s) in "
                f"{self._duration(elapsed)}."
            )
            QApplication.beep()
        elif "failed" not in self.status.text().lower():
            self.status.setText(f"V3 batch stopped after {self._duration(elapsed)}.")

    def stop(self) -> None:
        if self.worker:
            self.worker.request_cancel()
            self.queue = []
            self.rerender_queue = []
            self.rerender_queue_keys.clear()
            self.queued_rerender_active = False
            self.stop_button.setEnabled(False)
            self.status.setText("Stop requested; waiting for the current operation...")
            self.refresh_segments()

    def open_output(self) -> None:
        if self.last_output and self.last_output.is_dir():
            os.startfile(self.last_output)
        else:
            QMessageBox.information(self, "Output", "No Voice Clone V3 output is available yet.")
