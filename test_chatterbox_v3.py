import contextlib
import csv
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import soundfile as sf
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QItemSelectionModel

import chatterbox_v3 as chatterbox_module
from core import parse_input
from chatterbox_v3 import (
    ChatterboxFolderNormalizeWorker, ChatterboxRenderWorker, ChatterboxV3Tab,
    SUPPORTED_LANGUAGES, _expected_duration, _words,
    measure_speech_rms_db, normalize_completed_batch,
)


class FakeProfiles:
    def __init__(self, root: Path):
        self.root = root

    def names(self):
        return ["demo-voice"]

    def load(self, name):
        return {
            "name": name,
            "reference_audio": str(self.root / "reference.wav"),
            "language": "en",
        }


class ChatterboxV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_official_language_set_and_text_normalization(self):
        self.assertIn("en", SUPPORTED_LANGUAGES)
        self.assertNotIn("vi", SUPPORTED_LANGUAGES)
        self.assertEqual(_words("Hello, WORLD!"), "hello world")
        self.assertGreater(_expected_duration("one two three four"), 1.0)

    def test_copy_from_voice_clone_selects_profile_and_language(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "reference.wav").write_bytes(b"placeholder")
            tab = ChatterboxV3Tab(FakeProfiles(root), lambda: "demo-voice", root)
            tab.language.setCurrentIndex(tab.language.findData("fr"))
            tab.copy_from_voice_clone()
            self.assertEqual(tab.profile.currentData(), "demo-voice")
            self.assertEqual(tab.language.currentData(), "en")
            self.assertEqual(len(tab.rows), 1)
            tab.close()

    def test_script_picker_uses_vo_root_and_timestamp_session(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "chapter.txt"
            script.write_text("A segment.\n", encoding="utf-8")
            tab = ChatterboxV3Tab(FakeProfiles(root), lambda: "demo-voice", root)
            row = tab.current_row
            row["output"].setText(str(root / "old-output"))
            with patch.object(
                chatterbox_module.QFileDialog, "getOpenFileName",
                return_value=(str(script), "Script (*.txt *.srt)"),
            ):
                tab.pick_script(row["script"], row["output"])
            self.assertEqual(row["script"].text(), str(script))
            self.assertEqual(Path(row["output"].text()), root / "vo")
            session = tab._new_session(root / "vo")
            self.assertEqual(session.parent, root / "vo")
            self.assertRegex(session.name, r"^\d{8}_\d{6}$")
            session.mkdir(parents=True)
            next_session = tab._new_session(root / "vo")
            self.assertEqual(next_session.name, session.name + "_01")
            tab.close()

    def test_startup_preload_reuses_loaded_v3_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tab = ChatterboxV3Tab(FakeProfiles(root), lambda: "demo-voice", root)
            chatterbox_module._CHATTERBOX_MODEL_CACHE["v3:cuda"] = object()
            completed = []
            tab.preload_finished.connect(lambda: completed.append(True))
            try:
                tab.start_preload()
                self.assertIsNone(tab.preload_thread)
                self.assertIn("ready", tab.status.text())
                self.assertTrue(tab.render_button.isEnabled())
                self.assertEqual(completed, [True])
            finally:
                chatterbox_module._CHATTERBOX_MODEL_CACHE.clear()
                tab.close()

    def test_unload_model_releases_tts_asr_and_cuda_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tab = ChatterboxV3Tab(FakeProfiles(root), lambda: "demo-voice", root)
            chatterbox_module._CHATTERBOX_MODEL_CACHE["v3:cuda"] = object()
            chatterbox_module._CHATTERBOX_ASR_CACHE[(2, 2)] = object()
            calls = []
            fake_torch = types.SimpleNamespace(cuda=types.SimpleNamespace(
                is_available=lambda: True,
                empty_cache=lambda: calls.append("empty_cache"),
                ipc_collect=lambda: calls.append("ipc_collect"),
            ))
            with patch.dict(sys.modules, {"torch": fake_torch}):
                tab.unload_model()
            self.assertEqual(chatterbox_module._CHATTERBOX_MODEL_CACHE, {})
            self.assertEqual(chatterbox_module._CHATTERBOX_ASR_CACHE, {})
            self.assertEqual(calls, ["empty_cache", "ipc_collect"])
            self.assertIn("memory released", tab.status.text())
            tab.close()

    def test_voice_over_segment_panel_adds_and_lists_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tab = ChatterboxV3Tab(FakeProfiles(root), lambda: "demo-voice", root)
            script = root / "segments.txt"
            tab.current_row["script"].setText(str(script))
            tab.segment_text_input.setPlainText("First segment.\n\nSecond segment.")
            tab.add_text_segments()
            self.assertTrue(script.is_file())
            self.assertEqual(tab.segment_table.rowCount(), 2)
            self.assertEqual(tab.segment_table.columnCount(), 6)
            self.assertEqual(tab.segment_table.item(1, 2).text(), "Second segment.")
            self.assertEqual(tab.segment_table.item(1, 4).text(), "Default")
            tab.segment_table.item(1, 2).setText("Updated second segment.")
            self.assertEqual(parse_input(script)[1].text, "Updated second segment.")
            self.assertEqual(
                tab.segment_table.item(1, 3).text(), "Text changed · Rerender required"
            )
            tab.on_segment_status(0 + 1, "Verified · ASR passed")
            tab.on_segment_status(1 + 1, "Review required")
            tab.status_filter.setCurrentIndex(tab.status_filter.findData("attention"))
            self.assertTrue(tab.segment_table.isRowHidden(0))
            self.assertFalse(tab.segment_table.isRowHidden(1))
            self.assertEqual(tab.status_filter_count.text(), "1 / 2 files")
            tab.on_segment_status(1, "Error · Waiting to regenerate")
            self.assertFalse(tab.segment_table.isRowHidden(0))
            self.assertEqual(tab.status_filter_count.text(), "2 / 2 files")
            tab.close()

    def test_editable_srt_text_preserves_timestamps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "captions.srt"
            script.write_text(
                "1\n00:00:01,250 --> 00:00:03,500\nOriginal subtitle.\n",
                encoding="utf-8",
            )
            tab = ChatterboxV3Tab(FakeProfiles(root), lambda: "demo-voice", root)
            tab.current_row["script"].setText(str(script))
            tab.refresh_segments()
            tab.segment_table.item(0, 2).setText("New spoken subtitle.")
            updated = script.read_text(encoding="utf-8")
            self.assertIn("00:00:01,250 --> 00:00:03,500", updated)
            self.assertIn("New spoken subtitle.", updated)
            self.assertEqual(parse_input(script)[0].text, "New spoken subtitle.")
            tab.close()

    def test_output_audio_controls_match_omnivoice_loudness_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audio_path = root / "001.wav"
            sample_rate = 24000
            time_axis = np.arange(sample_rate, dtype=np.float32) / sample_rate
            sf.write(audio_path, 0.05 * np.sin(2 * np.pi * 220 * time_axis), sample_rate)
            before = measure_speech_rms_db(audio_path)
            normalize_completed_batch([audio_path])
            after = measure_speech_rms_db(audio_path)
            self.assertLess(before, -25.0)
            self.assertAlmostEqual(after, -20.0, delta=0.8)
            self.assertTrue((root / "_original_chatterbox_v3" / "001.wav").is_file())
            self.assertTrue((root / "loudness_before_after.csv").is_file())

            tab = ChatterboxV3Tab(FakeProfiles(root), lambda: "demo-voice", root)
            self.assertTrue(tab.normalize_audio.isChecked())
            self.assertAlmostEqual(tab.merge_pause.value(), 0.45)
            self.assertEqual(tab.retry_normalize_button.text(), "Retry batch normalization")
            self.assertEqual(tab.normalize_folder_button.text(), "Normalize audio folder")
            tab.close()

    def test_folder_normalization_copies_to_new_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            destination = root / "source_normalized"
            source.mkdir()
            sample_rate = 24000
            time_axis = np.arange(sample_rate, dtype=np.float32) / sample_rate
            original = source / "clip.wav"
            sf.write(original, 0.04 * np.sin(2 * np.pi * 220 * time_axis), sample_rate)
            original_bytes = original.read_bytes()
            worker = ChatterboxFolderNormalizeWorker(source, destination)
            completed = []
            failures = []
            worker.completed.connect(completed.append)
            worker.failed.connect(failures.append)
            worker.run()
            self.assertFalse(failures)
            self.assertEqual(completed, [str(destination)])
            self.assertEqual(original.read_bytes(), original_bytes)
            self.assertAlmostEqual(
                measure_speech_rms_db(destination / "clip.wav"), -20.0, delta=0.8
            )

    def test_folder_normalization_rejects_corrupt_audio_before_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            destination = root / "source_normalized"
            source.mkdir()
            (source / "broken.mp3").write_bytes(b"not-an-audio-file" * 32)
            worker = ChatterboxFolderNormalizeWorker(source, destination)
            completed = []
            failures = []
            worker.completed.connect(completed.append)
            worker.failed.connect(failures.append)
            worker.run()
            self.assertEqual(completed, [])
            self.assertEqual(len(failures), 1)
            self.assertIn("broken.mp3", failures[0])
            self.assertIn("No output folder was created", failures[0])
            self.assertFalse(destination.exists())

    def test_rerender_queue_can_add_and_remove_waiting_segment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "segments.txt"
            script.write_text("First segment.", encoding="utf-8")
            tab = ChatterboxV3Tab(FakeProfiles(root), lambda: "demo-voice", root)
            tab.current_row["script"].setText(str(script))
            tab.refresh_segments()
            tab.toggle_rerender_queue(tab.current_row, 1)
            self.assertEqual(len(tab.rerender_queue), 1)
            self.assertIn("Rerender queued", tab.segment_table.item(0, 3).text())
            tab.toggle_rerender_queue(tab.current_row, 1)
            self.assertEqual(tab.rerender_queue, [])
            self.assertEqual(tab.rerender_queue_keys, set())
            tab.close()

    def test_render_selected_supports_multiple_visible_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "segments.txt"
            script.write_text("First.\nSecond.\nThird.", encoding="utf-8")
            tab = ChatterboxV3Tab(FakeProfiles(root), lambda: "demo-voice", root)
            tab.current_row["script"].setText(str(script))
            tab.refresh_segments()
            selection = tab.segment_table.selectionModel()
            flags = (
                QItemSelectionModel.SelectionFlag.Select |
                QItemSelectionModel.SelectionFlag.Rows
            )
            selection.select(tab.segment_table.model().index(0, 0), flags)
            selection.select(tab.segment_table.model().index(2, 0), flags)
            with patch.object(tab, "_start_positions_render") as start:
                tab.render_selected_segments()
            start.assert_called_once_with([1, 3], toggle_when_busy=False)
            self.assertEqual(
                tab.segment_table.selectionMode(),
                tab.segment_table.SelectionMode.ExtendedSelection,
            )
            tab.close()

    def test_delete_selected_and_clear_list_preserve_recoverable_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "segments.txt"
            script.write_text("First.\nSecond.\nThird.\n", encoding="utf-8")
            session = root / "old-session"
            session.mkdir()
            (session / "001.wav").write_bytes(b"old audio")
            tab = ChatterboxV3Tab(FakeProfiles(root), lambda: "demo-voice", root)
            tab.current_row["script"].setText(str(script))
            tab.current_row["last_output"] = session
            tab.refresh_segments()
            selection = tab.segment_table.selectionModel()
            flags = (
                QItemSelectionModel.SelectionFlag.Select |
                QItemSelectionModel.SelectionFlag.Rows
            )
            selection.select(tab.segment_table.model().index(0, 0), flags)
            selection.select(tab.segment_table.model().index(2, 0), flags)
            tab.delete_selected_segments()
            self.assertEqual([segment.text for segment in parse_input(script)], ["Second."])
            self.assertEqual(len(list(root.glob("segments.txt.before_delete_*.bak"))), 1)
            self.assertIsNone(tab.current_row["last_output"])
            self.assertTrue((session / "001.wav").is_file())
            source_after_delete = script.read_text(encoding="utf-8")
            tab.clear_segment_list()
            self.assertEqual(tab.current_row["script"].text(), "")
            self.assertEqual(tab.segment_table.rowCount(), 0)
            self.assertEqual(script.read_text(encoding="utf-8"), source_after_delete)
            self.assertTrue((session / "001.wav").is_file())
            tab.close()

    def test_row_delete_button_queues_cancels_and_deletes_when_idle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "segments.txt"
            script.write_text("First segment.\n", encoding="utf-8")
            session = root / "session"
            session.mkdir()
            audio = session / "001.wav"
            audio.write_bytes(b"rendered audio")
            tab = ChatterboxV3Tab(FakeProfiles(root), lambda: "demo-voice", root)
            tab.current_row["script"].setText(str(script))
            tab.current_row["last_output"] = session
            tab.refresh_segments()
            tab.thread = types.SimpleNamespace(isRunning=lambda: True)
            tab.delete_segment(1)
            self.assertTrue(audio.is_file())
            self.assertEqual(len(tab.delete_queue), 1)
            self.assertIn("Delete queued", tab.segment_table.item(0, 3).text())
            tab.delete_segment(1)
            self.assertEqual(tab.delete_queue, [])
            self.assertTrue(audio.is_file())
            tab.delete_segment(1)
            tab.thread = None
            tab.process_delete_queue()
            self.assertFalse(audio.exists())
            self.assertEqual(tab.delete_queue, [])
            self.assertEqual(tab.segment_table.item(0, 3).text(), "Pending")
            tab.delete_retry_timer.stop()
            tab.close()

    def test_process_timing_and_live_segment_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "segments.txt"
            script.write_text("First segment.\n\nSecond segment.", encoding="utf-8")
            tab = ChatterboxV3Tab(FakeProfiles(root), lambda: "demo-voice", root)
            tab.current_row["script"].setText(str(script))
            tab.refresh_segments()
            tab.reset_timing(4, "batch")
            tab.timing_started_at -= 20
            tab.on_timing(1, 4, 20.0, 12.5)
            self.assertIn("Batch 1/4", tab.timing_label.text())
            self.assertIn("ETA", tab.timing_label.text())
            self.assertIn("Est. finish", tab.timing_label.text())
            self.assertIn("Last 12.5s", tab.timing_label.text())
            tab.on_segment_status(2, "Auto repair 1")
            self.assertEqual(tab.segment_table.item(1, 3).text(), "Auto repair 1")
            session = root / "render-session"
            session.mkdir()
            tab.current_row["last_output"] = session
            (session / "001.wav").write_bytes(b"rendered")
            tab.output_format.setCurrentText("mp3")
            tab.on_segment_status(1, "Rendered · Waiting for ASR")
            play = tab.segment_table.cellWidget(0, 5).layout().itemAt(0).widget()
            self.assertTrue(play.isEnabled())
            tab.timing_timer.stop()
            tab.close()

    def test_render_all_then_parallel_asr_queues_regeneration(self):
        class FakeTensor:
            def squeeze(self): return self
            def detach(self): return self
            def float(self): return self
            def cpu(self): return self
            def numpy(self): return np.full(24000, 0.05, dtype=np.float32)

        class FakeModel:
            sr = 24000

            def __init__(self):
                self.generate_calls = 0

            def prepare_conditionals(self, *_args, **_kwargs):
                pass

            def generate(self, *_args, **_kwargs):
                self.generate_calls += 1
                return FakeTensor()

        fake_model = FakeModel()

        class FakeTTS:
            @classmethod
            def from_pretrained(cls, **_kwargs):
                return fake_model

        class FakeWhisper:
            checks = {}

            def __init__(self, *_args, **_kwargs):
                pass

            def transcribe(self, path, **_kwargs):
                stem = Path(path).stem
                self.checks[stem] = self.checks.get(stem, 0) + 1
                if stem == "002" and self.checks[stem] == 1:
                    text = "completely incorrect words"
                else:
                    text = "First segment" if stem == "001" else "Second segment"
                return [types.SimpleNamespace(text=text)], None

        fake_torch = types.SimpleNamespace(
            cuda=types.SimpleNamespace(is_available=lambda: False),
            inference_mode=lambda: contextlib.nullcontext(),
        )
        fake_whisper = types.SimpleNamespace(WhisperModel=FakeWhisper)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reference = root / "reference.wav"
            reference.write_bytes(b"placeholder")
            script = root / "segments.txt"
            script.write_text("First segment.\n\nSecond segment.", encoding="utf-8")
            output = root / "output"
            worker = ChatterboxRenderWorker(
                {"reference_audio": str(reference)}, script, output, "en", "cpu", "wav",
                0.5, 0.5, 0.8, 1.2, 0.05, 1.0, True, 1, 2, True, None, False,
            )
            statuses = []
            completed = []
            failures = []
            worker.segment_status.connect(lambda index, status: statuses.append((index, status)))
            worker.completed.connect(completed.append)
            worker.failed.connect(failures.append)
            chatterbox_module._CHATTERBOX_MODEL_CACHE.clear()
            chatterbox_module._CHATTERBOX_ASR_CACHE.clear()
            real_replace = os.replace
            simulated_lock = {"raised": False}

            def replace_with_one_locked_file(source, destination):
                destination = Path(destination)
                if (destination.name == "002.wav" and destination.exists()
                        and not simulated_lock["raised"]):
                    simulated_lock["raised"] = True
                    raise PermissionError("simulated audio player lock")
                return real_replace(source, destination)

            with patch.dict(sys.modules, {"torch": fake_torch, "faster_whisper": fake_whisper}), \
                    patch.object(
                        chatterbox_module, "import_chatterbox_multilingual", return_value=FakeTTS
                    ), patch.object(chatterbox_module, "BUSY_FILE_RETRY_SECONDS", 0.01), \
                    patch.object(chatterbox_module.os, "replace", replace_with_one_locked_file):
                worker.run()
            self.assertFalse(failures)
            self.assertEqual(completed, [str(output)])
            self.assertEqual(fake_model.generate_calls, 3)
            self.assertIn((2, "Error · Waiting to regenerate"), statuses)
            self.assertTrue(any(index == 2 and status.startswith("Regenerating")
                                for index, status in statuses))
            self.assertTrue(any(index == 2 and status.startswith("File open · Retry")
                                for index, status in statuses))
            self.assertIn((2, "Verified · ASR passed"), statuses)
            with (output / "chatterbox_v3_asr_report.csv").open(
                encoding="utf-8-sig"
            ) as handle:
                report = list(csv.DictReader(handle))
            self.assertEqual(report[1]["attempts"], "2")

            scoped_worker = ChatterboxRenderWorker(
                {"reference_audio": str(reference)}, script, output, "en", "cpu", "wav",
                0.5, 0.5, 0.8, 1.2, 0.05, 1.0, True, 1, 2, True, [2], True,
            )
            scoped_completed = []
            scoped_failures = []
            scoped_worker.completed.connect(scoped_completed.append)
            scoped_worker.failed.connect(scoped_failures.append)
            with patch.dict(sys.modules, {"torch": fake_torch, "faster_whisper": fake_whisper}), \
                    patch.object(
                        chatterbox_module, "import_chatterbox_multilingual", return_value=FakeTTS
                    ):
                scoped_worker.run()
            self.assertFalse(scoped_failures)
            self.assertEqual(scoped_completed, [str(output)])
            self.assertEqual(fake_model.generate_calls, 4)
            with (output / "chatterbox_v3_asr_report.csv").open(
                encoding="utf-8-sig"
            ) as handle:
                merged_report = list(csv.DictReader(handle))
            self.assertEqual(len(merged_report), 2)
            self.assertEqual(merged_report[0]["segment"], "1")
            self.assertEqual(merged_report[1]["segment"], "2")
            self.assertLess(measure_speech_rms_db(output / "001.wav"), -24.0)
            self.assertAlmostEqual(
                measure_speech_rms_db(output / "002.wav"), -20.0, delta=0.8
            )
            chatterbox_module._CHATTERBOX_MODEL_CACHE.clear()
            chatterbox_module._CHATTERBOX_ASR_CACHE.clear()


if __name__ == "__main__":
    unittest.main()
