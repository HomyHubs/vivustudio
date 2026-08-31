"""Standalone batch remover for the bottom-right Gemini/Veo-style logo.

The existing VoiceOverStudio application keeps its production pipeline intact;
this module is a small, independent PySide6 tool for images and videos.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from datetime import date
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
TOOL_EXPIRES_ON = date(2027, 2, 28)

# os.add_dll_directory() returns a handle whose lifetime controls whether the
# directory remains active. Keep every handle alive for the whole process.
_DLL_DIRECTORY_HANDLES: list[object] = []
_DLL_DIRECTORY_PATHS: set[str] = set()


def ensure_not_expired(today: date | None = None) -> None:
    """Fail closed after the fixed six-month evaluation period."""
    if (today or date.today()) > TOOL_EXPIRES_ON:
        raise SystemExit(0)


def media_files(folder: Path, recursive: bool = False) -> list[Path]:
    """Return supported media files in stable, case-insensitive name order."""
    iterator = folder.rglob("*") if recursive else folder.glob("*")
    return sorted(
        (path for path in iterator if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS),
        key=lambda path: str(path).lower(),
    )


def logo_box(width: int, height: int, logo_percent: int = 15, margin_percent: int = 10) -> tuple[int, int, int, int]:
    """Calculate the even-pixel bottom-right selection used by the old tool."""
    size = max(24, round(min(width, height) * max(1, logo_percent) / 100))
    padding = max(4, round(size * 0.16))
    box_w = min(max(8, width - 2), max(8, (size + padding * 2) // 2 * 2))
    box_h = min(max(8, height - 2), max(8, (size + padding * 2) // 2 * 2))
    margin_x = max(2, round(width * max(0, margin_percent) / 100))
    margin_y = max(2, round(height * (max(0, margin_percent) + 3) / 100))
    x = max(0, width - margin_x - box_w)
    y = max(0, height - margin_y - box_h)
    return x // 2 * 2, y // 2 * 2, box_w, box_h


def output_path(source: Path, output_dir: Path) -> Path:
    """Build a non-overwriting output name while preserving the source suffix."""
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate = output_dir / f"{source.stem}_remove-logo{source.suffix}"
    number = 2
    while candidate.exists():
        candidate = output_dir / f"{source.stem}_remove-logo_{number}{source.suffix}"
        number += 1
    return candidate


def ffmpeg_executable() -> str:
    locations = [Path(__file__).with_name("ffmpeg.exe")]
    if getattr(sys, "frozen", False):
        locations.insert(0, Path(sys.executable).with_name("ffmpeg.exe"))
    locations.append(Path(__file__).with_name("vendor") / "ffmpeg" / "ffmpeg.exe")
    for bundled in locations:
        if bundled.is_file():
            return str(bundled)
    return shutil.which("ffmpeg") or "ffmpeg"


def _require_cv2():
    try:
        import cv2
        return cv2
    except ImportError as exc:
        raise RuntimeError("Ảnh cần OpenCV (cv2) để khử logo.") from exc


def _prepare_qt_runtime() -> None:
    """Prefer the packaged PySide6 runtime and platform plugin on Windows."""
    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        bundle_root = getattr(sys, "_MEIPASS", None)
        if bundle_root:
            roots.append(Path(bundle_root))
        roots.append(Path(sys.executable).resolve().parent)
    else:
        roots.append(Path(__file__).resolve().parent)

    for root in roots:
        candidates = (root / "PySide6", root / "_internal" / "PySide6")
        qt_dir = next((path for path in candidates if path.is_dir()), None)
        if qt_dir is None:
            continue

        shiboken_dir = qt_dir.parent / "shiboken6"
        dll_directories = [qt_dir]
        if shiboken_dir.is_dir():
            dll_directories.append(shiboken_dir)

        path_entries = [entry for entry in os.environ.get("PATH", "").split(os.pathsep) if entry]
        known_path_entries = {os.path.normcase(os.path.abspath(entry)) for entry in path_entries}
        for directory in dll_directories:
            normalized = os.path.normcase(os.path.abspath(str(directory)))
            if normalized not in _DLL_DIRECTORY_PATHS:
                try:
                    handle = os.add_dll_directory(str(directory))
                except (AttributeError, OSError):
                    handle = None
                if handle is not None:
                    _DLL_DIRECTORY_HANDLES.append(handle)
                _DLL_DIRECTORY_PATHS.add(normalized)
            if normalized not in known_path_entries:
                path_entries.insert(0, str(directory))
                known_path_entries.add(normalized)
        os.environ["PATH"] = os.pathsep.join(path_entries)

        plugins_dir = qt_dir / "plugins"
        platforms_dir = plugins_dir / "platforms"
        if plugins_dir.is_dir():
            os.environ["QT_PLUGIN_PATH"] = str(plugins_dir)
        if platforms_dir.is_dir():
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(platforms_dir)
        return


def remove_image_logo(source: Path, destination: Path, box: tuple[int, int, int, int]) -> None:
    """Remove a logo from one image with OpenCV's edge-aware inpainting."""
    cv2 = _require_cv2()
    image = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"Không đọc được ảnh: {source}")
    height, width = image.shape[:2]
    x, y, box_w, box_h = box
    mask = __import__("numpy").zeros((height, width), dtype="uint8")
    mask[max(0, y):min(height, y + box_h), max(0, x):min(width, x + box_w)] = 255
    cleaned = cv2.inpaint(image, mask, max(3, round(min(box_w, box_h) * 0.12)), cv2.INPAINT_TELEA)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(destination), cleaned):
        raise RuntimeError(f"Không ghi được ảnh: {destination}")


def video_size(source: Path) -> tuple[int, int]:
    cv2 = _require_cv2()
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise RuntimeError(f"Không mở được video: {source}")
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    capture.release()
    if width < 2 or height < 2:
        raise RuntimeError(f"Không đọc được kích thước video: {source}")
    return width, height


def remove_video_logo(source: Path, destination: Path, box: tuple[int, int, int, int]) -> None:
    """Run FFmpeg's compatible delogo filter and preserve the original audio."""
    x, y, width, height = box
    command = [
        ffmpeg_executable(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
        "-vf", f"delogo=x={x}:y={y}:w={width}:h={height}:show=0",
        "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-c:a", "copy", "-movflags", "+faststart", str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True, creationflags=0x08000000 if os.name == "nt" else 0)
    if result.returncode or not destination.is_file():
        raise RuntimeError(f"Khử logo video thất bại:\n{result.stderr[-3000:]}")


def process_media(source: Path, destination: Path, logo_percent: int, margin_percent: int) -> tuple[int, int, int, int]:
    width, height = (video_size(source) if source.suffix.lower() in VIDEO_EXTENSIONS else _image_size(source))
    box = logo_box(width, height, logo_percent, margin_percent)
    if source.suffix.lower() in IMAGE_EXTENSIONS:
        remove_image_logo(source, destination, box)
    else:
        remove_video_logo(source, destination, box)
    return box


def _image_size(source: Path) -> tuple[int, int]:
    cv2 = _require_cv2()
    image = cv2.imread(str(source), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise RuntimeError(f"Không đọc được ảnh: {source}")
    height, width = image.shape[:2]
    return width, height


class BatchWorker:
    """Small synchronous worker abstraction, also useful for headless callers."""
    def __init__(self, sources: list[Path], output_dir: Path, logo_percent: int, margin_percent: int, progress):
        self.sources, self.output_dir = sources, output_dir
        self.logo_percent, self.margin_percent, self.progress = logo_percent, margin_percent, progress
        self.cancelled = False

    def run(self) -> tuple[int, int]:
        completed = 0
        for index, source in enumerate(self.sources, 1):
            if self.cancelled:
                break
            destination = output_path(source, self.output_dir)
            self.progress(index - 1, len(self.sources), f"Đang xử lý {index}/{len(self.sources)} · {source.name}")
            process_media(source, destination, self.logo_percent, self.margin_percent)
            completed += 1
            self.progress(index, len(self.sources), f"Đã xong {index}/{len(self.sources)} · {destination.name}")
        return completed, len(self.sources)


def build_ui():
    _prepare_qt_runtime()
    from PySide6.QtCore import QObject, QThread, Qt, Signal
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QApplication, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton, QSpinBox, QVBoxLayout, QWidget

    class Worker(QObject):
        progress = Signal(int, int, str)
        done = Signal(int, int)
        failed = Signal(str)

        def __init__(self, *args):
            super().__init__()
            self.batch = BatchWorker(*args, self.progress.emit)

        def run(self):
            try:
                self.done.emit(*self.batch.run())
            except Exception:
                self.failed.emit(traceback.format_exc())

    class Window(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Remove Gemini Logo from anmd0711@gmail.com")
            self.resize(1100, 720)
            self.thread = None
            self.worker = None
            self.preview_before, self.preview_after = QLabel("Trước"), QLabel("Sau")
            for label in (self.preview_before, self.preview_after):
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setMinimumHeight(340)
                label.setStyleSheet("border: 1px solid #2d4058; background: #080d14; color: #9fb3c9;")
            self.input_file, self.input_dir, self.output_dir = QLineEdit(), QLineEdit(), QLineEdit()
            self.logo_percent, self.margin_percent = QSpinBox(), QSpinBox()
            self.logo_percent.setRange(1, 50); self.logo_percent.setValue(15); self.logo_percent.setSuffix(" %")
            self.margin_percent.setRange(0, 30); self.margin_percent.setValue(10); self.margin_percent.setSuffix(" %")
            self.analyze = QPushButton("Analyze & Preview"); self.run_button = QPushButton("Run Batch"); self.stop_button = QPushButton("Stop"); self.stop_button.setEnabled(False)
            self.progress = QProgressBar(); self.status = QLabel("Sẵn sàng · chọn thư mục ảnh hoặc video")
            form = QFormLayout()
            form.addRow("Input file", self._browse_file(self.input_file))
            form.addRow("Input folder", self._browse_folder(self.input_dir))
            form.addRow("Output folder", self._browse_folder(self.output_dir))
            row = QHBoxLayout(); row.addWidget(QLabel("Logo region")); row.addWidget(self.logo_percent); row.addWidget(QLabel("Inner margin")); row.addWidget(self.margin_percent); row.addStretch(); form.addRow(row)
            actions = QHBoxLayout(); actions.addWidget(self.analyze); actions.addWidget(self.run_button); actions.addWidget(self.stop_button); form.addRow("Actions", actions)
            group = QGroupBox("Gemini trailer · Remove bottom-right logo"); group.setLayout(form)
            previews = QHBoxLayout(); previews.addWidget(self.preview_before); previews.addWidget(self.preview_after)
            preview_group = QGroupBox("Preview · Before / After"); preview_layout = QVBoxLayout(preview_group); preview_layout.addLayout(previews)
            root = QWidget(); layout = QVBoxLayout(root); layout.addWidget(group); layout.addWidget(preview_group, 1); layout.addWidget(self.progress); layout.addWidget(self.status); self.setCentralWidget(root)
            self.analyze.clicked.connect(self.analyze_preview); self.run_button.clicked.connect(self.run_batch); self.stop_button.clicked.connect(self.stop_batch)
            self.setStyleSheet("QMainWindow, QWidget { background: #080d14; color: #dbeafe; } QGroupBox { border: 1px solid #2d4058; margin-top: 8px; padding: 10px; color: #39d8ff; } QLineEdit, QSpinBox { background: #111927; border: 1px solid #2d4058; padding: 6px; color: #e5f3ff; } QPushButton { background: #1b2a40; border: 1px solid #385273; padding: 7px 12px; color: #e5f3ff; } QPushButton:hover { border-color: #39d8ff; }")

        def _browse_folder(self, field):
            button = QPushButton("Browse")
            button.clicked.connect(lambda: self._choose_folder(field))
            container = QWidget(); row = QHBoxLayout(container); row.setContentsMargins(0, 0, 0, 0); row.addWidget(field); row.addWidget(button); return container

        def _browse_file(self, field):
            button = QPushButton("Browse")
            button.clicked.connect(lambda: self._choose_file(field))
            container = QWidget(); row = QHBoxLayout(container); row.setContentsMargins(0, 0, 0, 0); row.addWidget(field); row.addWidget(button); return container

        def _choose_folder(self, field):
            path = QFileDialog.getExistingDirectory(self, "Select folder", field.text())
            if path: field.setText(path)

        def _choose_file(self, field):
            path, _ = QFileDialog.getOpenFileName(
                self, "Select image or video", field.text(),
                "Media (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff *.mp4 *.mov *.mkv *.avi *.webm *.m4v)",
            )
            if path: field.setText(path)

        def _sources(self):
            selected_file = Path(self.input_file.text().strip())
            if self.input_file.text().strip():
                if not selected_file.is_file() or selected_file.suffix.lower() not in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS:
                    raise ValueError("Input file không tồn tại hoặc không được hỗ trợ.")
                return selected_file.parent, [selected_file]
            folder = Path(self.input_dir.text().strip())
            if not folder.is_dir(): raise ValueError("Input folder không tồn tại.")
            sources = media_files(folder)
            if not sources: raise ValueError("Không tìm thấy ảnh/video được hỗ trợ trong thư mục.")
            return folder, sources

        def analyze_preview(self):
            try:
                _, sources = self._sources(); source = sources[0]
                if source.suffix.lower() in IMAGE_EXTENSIONS:
                    before = _require_cv2().imread(str(source)); box = logo_box(before.shape[1], before.shape[0], self.logo_percent.value(), self.margin_percent.value())
                    with tempfile.TemporaryDirectory() as temp:
                        after_path = Path(temp) / source.name; remove_image_logo(source, after_path, box); self._set_preview(self.preview_before, source); self._set_preview(self.preview_after, after_path)
                else:
                    width, height = video_size(source); box = logo_box(width, height, self.logo_percent.value(), self.margin_percent.value())
                    with tempfile.TemporaryDirectory() as temp:
                        before_path, after_path = Path(temp) / "before.png", Path(temp) / "after.png"
                        subprocess.run([ffmpeg_executable(), "-y", "-loglevel", "error", "-i", str(source), "-frames:v", "1", str(before_path)], check=True)
                        remove_image_logo(before_path, after_path, box); self._set_preview(self.preview_before, before_path); self._set_preview(self.preview_after, after_path)
                self.status.setText(f"Preview: {source.name} · mask x={box[0]}, y={box[1]}, {box[2]}×{box[3]}px")
            except Exception as exc: QMessageBox.warning(self, "Preview failed", str(exc))

        def _set_preview(self, label, path):
            pixmap = QPixmap(str(path)); label.setPixmap(pixmap.scaled(label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

        def run_batch(self):
            try:
                ensure_not_expired()
                input_root, sources = self._sources()
                output = Path(self.output_dir.text().strip()) if self.output_dir.text().strip() else (input_root if self.input_file.text().strip() else input_root / "no_logo_output")
                self.worker = Worker(sources, output, self.logo_percent.value(), self.margin_percent.value()); self.thread = QThread(); self.worker.moveToThread(self.thread); self.thread.started.connect(self.worker.run); self.worker.progress.connect(self.on_progress); self.worker.done.connect(self.on_done); self.worker.failed.connect(self.on_failed); self.worker.done.connect(self.thread.quit); self.worker.failed.connect(self.thread.quit); self.stop_button.setEnabled(True); self.run_button.setEnabled(False); self.thread.start()
            except Exception as exc: QMessageBox.warning(self, "Cannot run batch", str(exc))

        def stop_batch(self):
            if self.worker: self.worker.batch.cancelled = True; self.status.setText("Đang dừng sau file hiện tại…")

        def on_progress(self, done, total, message): self.progress.setRange(0, total); self.progress.setValue(done); self.status.setText(message)
        def on_done(self, done, total): self.run_button.setEnabled(True); self.stop_button.setEnabled(False); self.status.setText(f"Hoàn tất · {done}/{total} file")
        def on_failed(self, details): self.run_button.setEnabled(True); self.stop_button.setEnabled(False); QMessageBox.critical(self, "Batch failed", details[-5000:])

    return Window


def main() -> int:
    ensure_not_expired()
    _prepare_qt_runtime()
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = build_ui()()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
