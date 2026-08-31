from __future__ import annotations

import ctypes
import os
import subprocess
import threading
from ctypes import wintypes
from pathlib import Path

from environment_manager import choose_cuda_variant, detect_gpu_name, ensure_runtime


APP_NAME = "VIVU STUDIO v1.0"
WM_CLOSE, WM_DESTROY, WM_PAINT, WM_ERASEBKGND = 0x0010, 0x0002, 0x000F, 0x0014
WM_NCHITTEST, WM_TIMER, WM_SETICON = 0x0084, 0x0113, 0x0080
HTCAPTION, WS_POPUP, WS_VISIBLE, SW_SHOW = 2, 0x80000000, 0x10000000, 5
IMAGE_ICON, LR_LOADFROMFILE, ICON_BIG, ICON_SMALL = 1, 0x0010, 1, 0
DT_LEFT, DT_VCENTER, DT_SINGLELINE, DT_END_ELLIPSIS = 0, 4, 0x20, 0x8000

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
gdi32 = ctypes.windll.gdi32
WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_longlong, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)

# ctypes assumes a 32-bit integer return value unless told otherwise. Window and
# drawing handles are pointer-sized, so explicit result types are required on x64.
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    wintypes.HMENU,
    wintypes.HINSTANCE,
    ctypes.c_void_p,
]
user32.CreateWindowExW.restype = wintypes.HWND
user32.DefWindowProcW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.DefWindowProcW.restype = ctypes.c_longlong
user32.LoadIconW.restype = wintypes.HICON
user32.LoadCursorW.restype = wintypes.HANDLE
user32.LoadImageW.restype = wintypes.HANDLE
user32.BeginPaint.restype = wintypes.HDC
gdi32.CreateSolidBrush.restype = wintypes.HBRUSH
gdi32.CreateFontW.restype = wintypes.HANDLE
gdi32.CreateRoundRectRgn.restype = wintypes.HANDLE
gdi32.SelectObject.restype = wintypes.HANDLE


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


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [
        ("hdc", wintypes.HDC),
        ("fErase", wintypes.BOOL),
        ("rcPaint", wintypes.RECT),
        ("fRestore", wintypes.BOOL),
        ("fIncUpdate", wintypes.BOOL),
        ("rgbReserved", ctypes.c_byte * 32),
    ]


user32.BeginPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
user32.EndPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
user32.FillRect.argtypes = [
    wintypes.HDC,
    ctypes.POINTER(wintypes.RECT),
    wintypes.HBRUSH,
]
user32.SetWindowRgn.argtypes = [wintypes.HWND, wintypes.HANDLE, wintypes.BOOL]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UpdateWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.InvalidateRect.argtypes = [
    wintypes.HWND,
    ctypes.POINTER(wintypes.RECT),
    wintypes.BOOL,
]
user32.DrawTextW.argtypes = [
    wintypes.HDC,
    wintypes.LPCWSTR,
    ctypes.c_int,
    ctypes.POINTER(wintypes.RECT),
    wintypes.UINT,
]
user32.SendMessageW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.PostMessageW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
gdi32.RoundRect.argtypes = [
    wintypes.HDC,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
]
gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
gdi32.SetBkMode.argtypes = [wintypes.HDC, ctypes.c_int]
gdi32.SetTextColor.argtypes = [wintypes.HDC, wintypes.DWORD]


def color(value: str) -> int:
    value = value.lstrip("#")
    red, green, blue = (int(value[index : index + 2], 16) for index in (0, 2, 4))
    return red | green << 8 | blue << 16


def show_error(message: str) -> None:
    user32.MessageBoxW(None, message, APP_NAME, 0x10)


class ModernLoadingWindow:
    WIDTH, HEIGHT = 640, 300

    def __init__(self, root_path: Path) -> None:
        self.root_path = root_path
        self.hinstance = kernel32.GetModuleHandleW(None)
        self.class_name = "VoiceOverStudioModernLoader"
        self.hwnd = None
        self.gpu_text = "Detecting graphics hardware..."
        self.status_text = "Preparing your workspace..."
        self.progress_offset = 0
        self.background_brush = gdi32.CreateSolidBrush(color("#0B1018"))
        self._wndproc = WNDPROC(self.window_proc)

    def window_proc(self, hwnd, message, wparam, lparam):
        if message == WM_PAINT:
            self.paint(hwnd)
            return 0
        if message == WM_ERASEBKGND:
            return 1
        if message == WM_TIMER:
            self.progress_offset = (self.progress_offset + 9) % 500
            user32.InvalidateRect(hwnd, None, False)
            return 0
        if message == WM_NCHITTEST:
            return HTCAPTION
        if message == WM_CLOSE:
            user32.DestroyWindow(hwnd)
            return 0
        if message == WM_DESTROY:
            user32.KillTimer(hwnd, 1)
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, message, wparam, lparam)

    @staticmethod
    def round_rect(hdc, left, top, right, bottom, radius, fill_color):
        brush = gdi32.CreateSolidBrush(color(fill_color))
        previous_brush = gdi32.SelectObject(hdc, brush)
        previous_pen = gdi32.SelectObject(hdc, gdi32.GetStockObject(8))
        gdi32.RoundRect(hdc, left, top, right, bottom, radius, radius)
        gdi32.SelectObject(hdc, previous_pen)
        gdi32.SelectObject(hdc, previous_brush)
        gdi32.DeleteObject(brush)

    @staticmethod
    def text(hdc, value, rect, font, text_color, flags):
        previous_font = gdi32.SelectObject(hdc, font)
        gdi32.SetBkMode(hdc, 1)
        gdi32.SetTextColor(hdc, color(text_color))
        user32.DrawTextW(hdc, value, -1, ctypes.byref(rect), flags)
        gdi32.SelectObject(hdc, previous_font)

    def paint(self, hwnd) -> None:
        paint = PAINTSTRUCT()
        hdc = user32.BeginPaint(hwnd, ctypes.byref(paint))
        client = wintypes.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(client))
        user32.FillRect(hdc, ctypes.byref(client), self.background_brush)
        self.round_rect(hdc, 1, 1, 639, 299, 24, "#111A27")
        self.round_rect(hdc, 34, 30, 118, 38, 8, "#35D6FF")
        self.round_rect(hdc, 122, 30, 158, 38, 8, "#75E6B5")
        self.text(
            hdc, APP_NAME, wintypes.RECT(34, 53, 604, 99), self.title_font,
            "#F4F8FC", DT_LEFT | DT_VCENTER | DT_SINGLELINE,
        )
        self.text(
            hdc, "VOICE CREATION WORKSPACE", wintypes.RECT(36, 103, 604, 128),
            self.small_font, "#35D6FF", DT_LEFT | DT_VCENTER | DT_SINGLELINE,
        )
        self.round_rect(hdc, 34, 145, 606, 210, 14, "#172333")
        self.text(
            hdc, self.gpu_text, wintypes.RECT(52, 154, 588, 178), self.small_font,
            "#75E6B5", DT_LEFT | DT_VCENTER | DT_SINGLELINE | DT_END_ELLIPSIS,
        )
        self.text(
            hdc, self.status_text, wintypes.RECT(52, 178, 588, 202), self.body_font,
            "#D5E0EB", DT_LEFT | DT_VCENTER | DT_SINGLELINE | DT_END_ELLIPSIS,
        )
        self.round_rect(hdc, 34, 237, 606, 249, 10, "#263548")
        segment_left = 34 + self.progress_offset * 722 // 500 - 150
        clipped_left, clipped_right = max(34, segment_left), min(606, segment_left + 150)
        if clipped_right > clipped_left:
            self.round_rect(hdc, clipped_left, 237, clipped_right, 249, 10, "#35D6FF")
        self.text(
            hdc, "Starting application", wintypes.RECT(34, 258, 606, 282),
            self.small_font, "#7F93A8", DT_LEFT | DT_VCENTER | DT_SINGLELINE,
        )
        user32.EndPaint(hwnd, ctypes.byref(paint))

    def create(self) -> None:
        window_class = WNDCLASSW()
        window_class.lpfnWndProc = self._wndproc
        window_class.hInstance = self.hinstance
        window_class.hIcon = user32.LoadIconW(None, 32512)
        window_class.hCursor = user32.LoadCursorW(None, 32512)
        window_class.hbrBackground = self.background_brush
        window_class.lpszClassName = self.class_name
        user32.RegisterClassW(ctypes.byref(window_class))
        x = max(0, (user32.GetSystemMetrics(0) - self.WIDTH) // 2)
        y = max(0, (user32.GetSystemMetrics(1) - self.HEIGHT) // 2)
        self.hwnd = user32.CreateWindowExW(
            0, self.class_name, APP_NAME, WS_POPUP | WS_VISIBLE, x, y,
            self.WIDTH, self.HEIGHT, None, None, self.hinstance, None,
        )
        region = gdi32.CreateRoundRectRgn(0, 0, 641, 301, 26, 26)
        user32.SetWindowRgn(self.hwnd, region, True)
        self.title_font = gdi32.CreateFontW(
            34, 0, 0, 0, 700, 0, 0, 0, 1, 0, 0, 5, 0, "Segoe UI"
        )
        self.body_font = gdi32.CreateFontW(
            17, 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 5, 0, "Segoe UI"
        )
        self.small_font = gdi32.CreateFontW(
            14, 0, 0, 0, 600, 0, 0, 0, 1, 0, 0, 5, 0, "Segoe UI"
        )
        icon_path = self.root_path / "assets" / "voice.ico"
        if icon_path.is_file():
            icon = user32.LoadImageW(None, str(icon_path), IMAGE_ICON, 0, 0, LR_LOADFROMFILE)
            if icon:
                user32.SendMessageW(self.hwnd, WM_SETICON, ICON_BIG, icon)
                user32.SendMessageW(self.hwnd, WM_SETICON, ICON_SMALL, icon)
        user32.SetTimer(self.hwnd, 1, 24, None)
        user32.ShowWindow(self.hwnd, SW_SHOW)
        user32.UpdateWindow(self.hwnd)

    def update_status(self, message: str) -> None:
        self.status_text = message[-180:]
        if self.hwnd:
            user32.InvalidateRect(self.hwnd, None, False)

    def prepare(self) -> None:
        try:
            gpu_name = detect_gpu_name()
            variant = choose_cuda_variant(gpu_name)
            label = "CPU mode" if variant == "cpu" else f"CUDA {variant[2:4]}.{variant[4:]}"
            self.gpu_text = f"{gpu_name or 'No NVIDIA GPU detected'}  |  {label}"
            self.update_status("Checking application runtime...")
            env_path = ensure_runtime(self.root_path, variant, self.update_status)
            self.update_status("Opening VIVU STUDIO...")
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
                cwd=self.root_path, env=environment, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
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


def run_launcher(root_path: Path) -> int:
    return ModernLoadingWindow(root_path).run()
