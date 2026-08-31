from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import threading
from ctypes import wintypes
from pathlib import Path

from environment_manager import choose_cuda_variant, detect_gpu_name, ensure_runtime


APP_NAME = "VIVU STUDIO v1.0"
WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
WM_ERASEBKGND = 0x0014
WM_SETFONT = 0x0030
WM_SETICON = 0x0080
WM_CTLCOLORSTATIC = 0x0138
ICON_BIG = 1
ICON_SMALL = 0
WS_OVERLAPPED = 0x00000000
WS_CAPTION = 0x00C00000
WS_SYSMENU = 0x00080000
WS_VISIBLE = 0x10000000
WS_CHILD = 0x40000000
SS_LEFT = 0x00000000
PBS_MARQUEE = 0x00000008
PBM_SETBARCOLOR = 0x0409
PBM_SETMARQUEE = 0x040A
PBM_SETBKCOLOR = 0x2001
TRANSPARENT = 1
SW_SHOW = 5
CW_USEDEFAULT = 0x80000000
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
IDI_APPLICATION = 32512


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
comctl32 = ctypes.windll.comctl32
gdi32 = ctypes.windll.gdi32
try:
    dwmapi = ctypes.windll.dwmapi
except Exception:
    dwmapi = None


WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_longlong, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


def show_error(message: str) -> None:
    user32.MessageBoxW(None, message, APP_NAME, 0x10)


class LoadingWindow:
    def __init__(self, root_path: Path) -> None:
        self.root_path = root_path
        self.hinstance = kernel32.GetModuleHandleW(None)
        self.class_name = "VoiceOverStudioNativeLoader"
        self.hwnd = None
        self.gpu_label = None
        self.status_label = None
        self.progress = None
        self.font = None
        self.background_brush = gdi32.CreateSolidBrush(0x1B120B)
        self._wndproc = WNDPROC(self.window_proc)

    def window_proc(self, hwnd, message, wparam, lparam):
        if message == WM_ERASEBKGND:
            client = wintypes.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(client))
            user32.FillRect(wparam, ctypes.byref(client), self.background_brush)
            return 1
        if message == WM_CTLCOLORSTATIC:
            gdi32.SetBkMode(wparam, TRANSPARENT)
            gdi32.SetTextColor(wparam, 0xF5EDE7)
            return self.background_brush
        if message == WM_CLOSE:
            user32.DestroyWindow(hwnd)
            return 0
        if message == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, message, wparam, lparam)

    def create(self) -> None:
        comctl32.InitCommonControls()
        window_class = WNDCLASSW()
        window_class.lpfnWndProc = self._wndproc
        window_class.hInstance = self.hinstance
        window_class.hIcon = user32.LoadIconW(None, IDI_APPLICATION)
        window_class.hCursor = user32.LoadCursorW(None, 32512)
        window_class.hbrBackground = self.background_brush
        window_class.lpszClassName = self.class_name
        user32.RegisterClassW(ctypes.byref(window_class))

        width, height = 620, 270
        x = max(0, (user32.GetSystemMetrics(0) - width) // 2)
        y = max(0, (user32.GetSystemMetrics(1) - height) // 2)
        self.hwnd = user32.CreateWindowExW(
            0,
            self.class_name,
            APP_NAME,
            WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_VISIBLE,
            x,
            y,
            width,
            height,
            None,
            None,
            self.hinstance,
            None,
        )
        if dwmapi:
            try:
                rounded = ctypes.c_int(2)
                dwmapi.DwmSetWindowAttribute(self.hwnd, 33, ctypes.byref(rounded), ctypes.sizeof(rounded))
            except Exception:
                pass
        self.font = gdi32.CreateFontW(
            18, 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 5, 0, "Segoe UI"
        )
        title_font = gdi32.CreateFontW(
            32, 0, 0, 0, 700, 0, 0, 0, 1, 0, 0, 5, 0, "Segoe UI"
        )
        accent = self.static("━━━━━━", 32, 24, 130, 22)
        title = self.static(APP_NAME, 32, 50, 540, 46)
        user32.SendMessageW(title, WM_SETFONT, title_font, True)
        user32.SendMessageW(accent, WM_SETFONT, self.font, True)
        self.gpu_label = self.static("Detecting NVIDIA GPU...", 32, 106, 552, 28)
        self.status_label = self.static("Starting workspace...", 32, 142, 552, 42)
        self.progress = user32.CreateWindowExW(
            0,
            "msctls_progress32",
            None,
            WS_CHILD | WS_VISIBLE | PBS_MARQUEE,
            32,
            204,
            552,
            18,
            self.hwnd,
            None,
            self.hinstance,
            None,
        )
        for control in (self.gpu_label, self.status_label):
            user32.SendMessageW(control, WM_SETFONT, self.font, True)
        user32.SendMessageW(self.progress, PBM_SETBARCOLOR, 0, 0xD2D331)
        user32.SendMessageW(self.progress, PBM_SETBKCOLOR, 0, 0x2F2115)
        user32.SendMessageW(self.progress, PBM_SETMARQUEE, True, 20)
        icon_path = self.root_path / "assets" / "voice.ico"
        if icon_path.is_file():
            icon = user32.LoadImageW(
                None, str(icon_path), IMAGE_ICON, 0, 0, LR_LOADFROMFILE
            )
            if icon:
                user32.SendMessageW(self.hwnd, WM_SETICON, ICON_BIG, icon)
                user32.SendMessageW(self.hwnd, WM_SETICON, ICON_SMALL, icon)
        user32.ShowWindow(self.hwnd, SW_SHOW)
        user32.UpdateWindow(self.hwnd)

    def static(self, text: str, x: int, y: int, width: int, height: int):
        return user32.CreateWindowExW(
            0,
            "STATIC",
            text,
            WS_CHILD | WS_VISIBLE | SS_LEFT,
            x,
            y,
            width,
            height,
            self.hwnd,
            None,
            self.hinstance,
            None,
        )

    def update_status(self, message: str) -> None:
        if self.status_label:
            user32.SetWindowTextW(self.status_label, message[-180:])

    def prepare(self) -> None:
        try:
            gpu_name = detect_gpu_name()
            variant = choose_cuda_variant(gpu_name)
            label = "CPU mode" if variant == "cpu" else f"CUDA {variant[2:4]}.{variant[4:]}"
            user32.SetWindowTextW(
                self.gpu_label,
                f"{gpu_name or 'No NVIDIA GPU detected'}  |  Selected {label}",
            )
            env_path = ensure_runtime(self.root_path, variant, self.update_status)
            if variant == "cpu":
                self.update_status("Opening VIVU STUDIO in CPU mode...")
            else:
                self.update_status("Opening VIVU STUDIO. OmniVoice will preload in the background...")
            environment = dict(os.environ)
            cache_root = self.root_path / "cache"
            environment.setdefault("PIP_CACHE_DIR", str(cache_root / "pip"))
            environment.setdefault("TORCH_HOME", str(cache_root / "torch"))
            environment.setdefault("XDG_CACHE_HOME", str(cache_root))
            environment.setdefault("HF_HUB_DISABLE_XET", "1")
            environment.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")
            environment["VOICEOVER_CUDA_VARIANT"] = variant
            environment["VOICEOVER_CUDA_LABEL"] = label
            environment["VOICEOVER_DEFAULT_DEVICE"] = "cpu" if variant == "cpu" else "cuda"
            subprocess.Popen(
                [
                    str(env_path / "pythonw.exe"), "-c",
                    "import app; raise SystemExit(app.main())",
                ],
                cwd=self.root_path,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            user32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)
        except Exception as exc:
            show_error(str(exc))
            user32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)

    def run(self) -> int:
        self.create()
        threading.Thread(target=self.prepare, daemon=True).start()
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
        return 0


def main() -> int:
    root = (
        Path(sys.executable).resolve().parent
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent
    )
    if not any(root.glob("app*.pyd")):
        show_error("The compiled application module was not found beside the launcher.")
        return 1
    from modern_launcher import run_launcher

    return run_launcher(root)


if __name__ == "__main__":
    raise SystemExit(main())
