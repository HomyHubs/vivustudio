import unittest
from pathlib import Path


class ExeLauncherTests(unittest.TestCase):
    def test_batch_launcher_runs_source_instead_of_exe(self):
        source = Path("Start VoiceOver.bat").read_text(encoding="utf-8")
        self.assertIn('pythonw.exe" "%CD%\\launcher.pyw"', source)
        self.assertNotIn('start "" "%CD%\\VoiceOverStudio.exe"', source)

    def test_launcher_uses_pythonw_without_console(self):
        source = Path("launcher.pyw").read_text(encoding="utf-8")
        self.assertIn('env_path / "pythonw.exe"', source)
        self.assertIn("subprocess.CREATE_NO_WINDOW", source)
        self.assertIn("stdout=subprocess.DEVNULL", source)
        self.assertIn("LoadingWindow", source)
        self.assertIn("choose_cuda_variant", source)
        self.assertIn('environment["VOICEOVER_DEFAULT_DEVICE"] = "cpu" if variant == "cpu" else "cuda"', source)
        self.assertNotIn('VOICEOVER_PRELOAD_MODEL', source)
        self.assertNotIn("tkinter", source)
        self.assertIn("CreateWindowExW", source)
        self.assertIn("modern_launcher", source)
        modern_source = Path("modern_launcher.py").read_text(encoding="utf-8")
        self.assertIn("WS_POPUP | WS_VISIBLE", modern_source)
        self.assertIn("CreateRoundRectRgn", modern_source)
        self.assertIn("WM_PAINT", modern_source)
        self.assertNotIn("msctls_progress32", modern_source)

    def test_build_and_app_use_voice_icon(self):
        self.assertTrue(Path("assets/voice.ico").is_file())
        build_source = Path("Build VoiceOverStudio EXE.ps1").read_text(encoding="utf-8")
        self.assertIn("--icon", build_source)
        self.assertIn("--exclude-module torch", build_source)
        self.assertIn("--exclude-module omnivoice", build_source)
        self.assertIn("--exclude-module PySide6", build_source)
        self.assertNotIn("--hidden-import", build_source)
        self.assertNotIn("--add-data", build_source)
        app_source = Path("app.py").read_text(encoding="utf-8")
        self.assertIn("setWindowIcon", app_source)
        self.assertIn("SetCurrentProcessExplicitAppUserModelID", app_source)
        self.assertIn("CreateMutexW", app_source)


if __name__ == "__main__":
    unittest.main()
