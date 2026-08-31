from __future__ import annotations

import ctypes
import os
import sys
import tempfile
import traceback
from pathlib import Path


_DLL_DIRECTORY_HANDLES: list[object] = []


def _bootstrap_packaged_runtime() -> None:
    """Configure bundled Qt DLLs before importing the Cython extension."""
    if not getattr(sys, "frozen", False):
        return

    roots = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        roots.append(Path(bundle_root))
    roots.append(Path(sys.executable).resolve().parent)

    for root in roots:
        candidates = (root / "PySide6", root / "_internal" / "PySide6")
        qt_dir = next((path for path in candidates if path.is_dir()), None)
        if qt_dir is None:
            continue

        shiboken_dir = qt_dir.parent / "shiboken6"
        dll_directories = [qt_dir]
        if shiboken_dir.is_dir():
            dll_directories.append(shiboken_dir)

        current_path = os.environ.get("PATH", "")
        os.environ["PATH"] = os.pathsep.join(
            [str(path) for path in dll_directories] + ([current_path] if current_path else [])
        )
        for directory in dll_directories:
            try:
                handle = os.add_dll_directory(str(directory))
            except (AttributeError, OSError):
                continue
            _DLL_DIRECTORY_HANDLES.append(handle)

        plugins_dir = qt_dir / "plugins"
        platforms_dir = plugins_dir / "platforms"
        if plugins_dir.is_dir():
            os.environ["QT_PLUGIN_PATH"] = str(plugins_dir)
        if platforms_dir.is_dir():
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(platforms_dir)
        return


def _report_startup_error(details: str) -> None:
    log_path = Path(tempfile.gettempdir()) / "RemoveLogoTool-startup.log"
    try:
        log_path.write_text(details, encoding="utf-8")
    except OSError:
        pass
    if os.name == "nt":
        try:
            ctypes.windll.user32.MessageBoxW(
                None,
                f"Remove Logo Tool không thể khởi động.\n\nChi tiết: {log_path}",
                "Remove Logo Tool",
                0x10,
            )
        except (AttributeError, OSError):
            pass


def run() -> int:
    try:
        _bootstrap_packaged_runtime()
        from remove_logo_tool import main
        return main()
    except Exception:
        _report_startup_error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
