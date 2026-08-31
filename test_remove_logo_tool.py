import os
import sys
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import remove_logo_tool
import remove_logo_tool_launcher
from remove_logo_tool import (
    IMAGE_EXTENSIONS,
    TOOL_EXPIRES_ON,
    VIDEO_EXTENSIONS,
    ensure_not_expired,
    logo_box,
    media_files,
    output_path,
)


class FakeMediaPath:
    def __init__(self, name):
        self.name = name
        self.suffix = Path(name).suffix

    def is_file(self):
        return True

    def __str__(self):
        return self.name


class FakeFolder:
    def glob(self, _pattern):
        return [FakeMediaPath("z.PNG"), FakeMediaPath("ignore.txt"), FakeMediaPath("a.MP4")]


class RemoveLogoToolTests(unittest.TestCase):
    def test_logo_box_is_bottom_right_and_even(self):
        x, y, width, height = logo_box(3840, 2160, 15, 10)
        self.assertLess(x + width, 3840)
        self.assertLess(y + height, 2160)
        self.assertEqual((x % 2, y % 2, width % 2, height % 2), (0, 0, 0, 0))


    def test_media_files_filters_and_sorts_case_insensitively(self):
        folder = FakeFolder()
        self.assertEqual([path.name for path in media_files(folder)], ["a.MP4", "z.PNG"])
        self.assertTrue(IMAGE_EXTENSIONS and VIDEO_EXTENSIONS)


    def test_output_path_has_stable_default_name(self):
        self.assertEqual(
            output_path(Path("clip.mp4"), Path("." )).name,
            "clip_remove-logo.mp4",
        )

    def test_expiry_allows_last_day_and_exits_after_expiry(self):
        ensure_not_expired(TOOL_EXPIRES_ON)
        with self.assertRaises(SystemExit) as error:
            ensure_not_expired(date(2027, 3, 1))
        self.assertEqual(error.exception.code, 0)

    def test_qt_runtime_keeps_dll_handles_and_sets_platform_plugin(self):
        with TemporaryDirectory() as directory:
            bundle = Path(directory)
            qt_dir = bundle / "PySide6"
            shiboken_dir = bundle / "shiboken6"
            platforms_dir = qt_dir / "plugins" / "platforms"
            platforms_dir.mkdir(parents=True)
            shiboken_dir.mkdir()

            qt_handle, shiboken_handle = object(), object()
            remove_logo_tool._DLL_DIRECTORY_HANDLES.clear()
            remove_logo_tool._DLL_DIRECTORY_PATHS.clear()
            with (
                patch.object(sys, "frozen", True, create=True),
                patch.object(sys, "_MEIPASS", str(bundle), create=True),
                patch.dict(os.environ, {"PATH": ""}, clear=True),
                patch.object(
                    remove_logo_tool.os,
                    "add_dll_directory",
                    side_effect=[qt_handle, shiboken_handle],
                    create=True,
                ) as add_directory,
            ):
                remove_logo_tool._prepare_qt_runtime()
                self.assertEqual(add_directory.call_count, 2)
                self.assertEqual(
                    remove_logo_tool._DLL_DIRECTORY_HANDLES,
                    [qt_handle, shiboken_handle],
                )
                self.assertEqual(os.environ["QT_PLUGIN_PATH"], str(qt_dir / "plugins"))
                self.assertEqual(
                    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"],
                    str(platforms_dir),
                )

    def test_launcher_bootstraps_qt_before_importing_compiled_module(self):
        with TemporaryDirectory() as directory:
            bundle = Path(directory)
            qt_dir = bundle / "_internal" / "PySide6"
            shiboken_dir = bundle / "_internal" / "shiboken6"
            (qt_dir / "plugins" / "platforms").mkdir(parents=True)
            shiboken_dir.mkdir(parents=True)

            remove_logo_tool_launcher._DLL_DIRECTORY_HANDLES.clear()
            with (
                patch.object(sys, "frozen", True, create=True),
                patch.object(sys, "_MEIPASS", str(bundle / "_internal"), create=True),
                patch.dict(os.environ, {"PATH": ""}, clear=True),
                patch.object(
                    remove_logo_tool_launcher.os,
                    "add_dll_directory",
                    side_effect=[object(), object()],
                    create=True,
                ) as add_directory,
            ):
                remove_logo_tool_launcher._bootstrap_packaged_runtime()
                self.assertEqual(add_directory.call_count, 2)
                self.assertEqual(len(remove_logo_tool_launcher._DLL_DIRECTORY_HANDLES), 2)
                self.assertEqual(
                    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"],
                    str(qt_dir / "plugins" / "platforms"),
                )


if __name__ == "__main__":
    unittest.main()
