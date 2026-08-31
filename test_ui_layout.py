import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QGroupBox,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTabWidget,
)
from PySide6.QtGui import QColor, QPixmap
from chatterbox_v3 import ChatterboxV3Tab

from app import (
    GeminiLogoWorker,
    MainWindow,
    PIPER_REFERENCE_TEXTS,
    ProfileStore,
    VoiceTranscriptWorker,
    create_expanded_gemini_mask,
    create_gemini_shape_mask,
    detect_video_scene_ranges,
    gemini_logo_box,
    gemini_original_source,
    gemini_residual_is_safe,
    gemini_temporal_roi,
    piper_config_language,
    render_voice_design_preview,
    voice_design_audio_filter,
    voice_display_name,
)
from vsr_propainter_runner import balanced_batches, create_rectangular_mask
from stable_clean_runner import build_masks, match_local_color


class UiLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.app = QApplication.instance() or QApplication([])

    def test_tabs_range_and_segment_actions_exist(self):
        with patch.object(MainWindow, "refresh_profiles"):
            window = MainWindow()
        tabs = next(
            candidate
            for candidate in window.findChildren(QTabWidget)
            if candidate.count() >= 1 and candidate.tabText(0) == "Voice List"
        )
        self.assertEqual(
            [tabs.tabText(index) for index in range(tabs.count())],
            ["Voice List", "Voice Clone", "Voice Clone v2", "Voice Clone v3", "Video Effect", "Caption", "Watermark", "Automation", "Tools", "Environment"],
        )
        self.assertIsInstance(window.chatterbox_v3_tab, ChatterboxV3Tab)
        self.assertTrue(window.chatterbox_v3_tab.auto_qa.isChecked())
        self.assertEqual(window.chatterbox_v3_tab.auto_qa.text(), "Auto ASR repair")
        self.assertEqual(window.chatterbox_v3_tab.device.itemText(0), "CUDA GPU")
        self.assertEqual(window.chatterbox_v3_tab.segment_table.columnCount(), 6)
        self.assertEqual(window.chatterbox_v3_tab.add_segments_button.text(), "Add text segments")
        self.assertTrue(window.chatterbox_v3_tab.normalize_audio.isChecked())
        self.assertEqual(
            window.chatterbox_v3_tab.retry_normalize_button.text(),
            "Retry batch normalization",
        )
        self.assertEqual(
            set(window.automation_stage_checks),
            {"voice_clone", "video_effect", "caption", "watermark"},
        )
        self.assertTrue(all(checkbox.isChecked() for checkbox in window.automation_stage_checks.values()))
        self.assertEqual(window.automation_table.columnCount(), 9)
        self.assertEqual(
            [
                window.automation_voice_engine.itemData(index)
                for index in range(window.automation_voice_engine.count())
            ],
            ["original", "v3"],
        )
        self.assertEqual(
            window.automation_voice_engine.itemText(0), "Voice Clone (Original)"
        )
        self.assertEqual(window.automation_voice_engine.itemText(1), "Voice Clone v3")
        self.assertEqual(window.automation_table.horizontalHeaderItem(0).text(), "Script (.txt/.str/.srt)")
        self.assertEqual(window.automation_table.horizontalHeaderItem(4).text(), "Trailer video")
        self.assertEqual(window.automation_table.horizontalHeaderItem(5).text(), "Channel names")
        self.assertEqual(window.automation_table.horizontalHeaderItem(6).text(), "Output folder")
        self.assertEqual(window.automation_table.horizontalHeaderItem(7).text(), "Processing group")
        self.assertEqual(window.automation_table.horizontalHeaderItem(8).text(), "Group name")
        self.assertEqual(window.automation_add_button.text(), "Add automation input")
        self.assertEqual(window.automation_open_output_button.text(), "Open output folder")
        self.assertIsInstance(window.automation_channel, QPlainTextEdit)
        self.assertTrue(hasattr(window.automation_table, "files_dropped"))
        window.on_automation_files_dropped([str(Path("trailer.mp4"))], 0, 4)
        self.assertEqual(window.automation_table.item(0, 4).text(), "trailer.mp4")
        self.assertEqual(window.segment_table.columnCount(), 6)
        self.assertEqual(window.zonos2_segment_table.columnCount(), 5)
        self.assertEqual(window.moss_segment_table.columnCount(), 5)
        self.assertEqual(
            window.selected_moss_checkpoint(),
            "OpenMOSS-Team/MOSS-TTS-Local-Transformer-v1.5",
        )
        self.assertEqual(window.moss_max_new_tokens.value(), 1024)
        self.assertEqual(window.moss_language.currentData(), "en")
        self.assertEqual(len(window.moss_batch_rows), 1)
        second_moss_row = window.add_moss_batch_row("C:/two.txt", "C:/two-output")
        self.assertEqual(len(window.moss_batch_rows), 2)
        self.assertEqual(second_moss_row["input_edit"].text(), "C:/two.txt")
        window.remove_moss_batch_row(second_moss_row)
        self.assertEqual(len(window.moss_batch_rows), 1)
        self.assertIsInstance(window.zonos2_progress, QProgressBar)
        self.assertIsInstance(window.zonos2_log, QPlainTextEdit)
        self.assertTrue(window.zonos2_log.isReadOnly())
        self.assertTrue(window.zonos2_voice.isEditable())
        self.assertEqual(window.caption_mode.currentText(), "Standard")
        self.assertEqual(window.caption_preset.currentText(), "Classic White Orange")
        self.assertTrue(window.caption_burn_video.isChecked())
        self.assertIn("active_color", window.caption_config_preview.toPlainText())
        self.assertIn("Export config JSON", {button.text() for button in window.findChildren(QPushButton)})
        self.assertEqual(window.import_piper_button.text(), "Create clone voices from tts-model")
        self.assertEqual(window.preview_voice_button.text(), "Preview voice")
        self.assertEqual(window.delete_voice_button.text(), "Delete voice")
        self.assertEqual(window.auto_transcript_button.text(), "Auto transcript")
        self.assertEqual(
            [
                window.voice_list_subtabs.tabText(index)
                for index in range(window.voice_list_subtabs.count())
            ],
            ["Profile Manager", "Voice Designer"],
        )
        self.assertEqual(window.voice_design_generate_button.text(), "Generate preview")
        self.assertEqual(window.voice_design_save_button.text(), "Save as new profile")
        self.assertTrue(window.voice_design_gender_lock.isChecked())
        self.assertEqual(window.voice_design_pitch.minimum(), -1.5)
        self.assertEqual(window.voice_design_pitch.maximum(), 1.5)
        self.assertIsInstance(window.voice_list_progress, QProgressBar)
        self.assertIsInstance(window.voice_list_log, QPlainTextEdit)
        self.assertTrue(window.voice_list_log.isReadOnly())
        self.assertIsNot(window.voice_list_progress, window.progress)
        self.assertIsNot(window.voice_list_log, window.log)
        window.active_task_ui = "voice_list"
        window.append_log("Voice List isolated log")
        self.assertIn("Voice List isolated log", window.voice_list_log.toPlainText())
        self.assertNotIn("Voice List isolated log", window.log.toPlainText())
        self.assertEqual(window.default_voice_profile_button.text(), "Set default")
        self.assertEqual(voice_display_name("Piper - adam1"), "adam1")
        self.assertEqual(voice_display_name("Local clone: Piper - adam1"), "adam1")
        self.assertNotIn("Zonos2", [tabs.tabText(index) for index in range(tabs.count())])
        button_texts = {button.text() for button in window.findChildren(QPushButton)}
        self.assertNotIn("Copy settings from OmniVoice", button_texts)
        self.assertIn("Save Settings", button_texts)
        self.assertIn("Load defaults", button_texts)
        self.assertIn("Retry batch normalization", button_texts)
        self.assertEqual(
            window.zonos2_save_settings_button.width(), window.zonos2_load_defaults_button.width()
        )
        self.assertEqual(
            window.normalize_audio.text(),
            "Normalize completed batch after all segments render",
        )
        self.assertEqual(window.speaking_style.isEnabled(), window.use_speaking_style.isChecked())
        self.assertTrue(window.stop_button.text().startswith("Stop"))
        groups = {group.title(): group for group in window.findChildren(QGroupBox)}
        self.assertIn("Render Range", groups)
        self.assertIsNotNone(groups["Render Range"].findChild(QPushButton))
        self.assertEqual(groups["Render Range"].parentWidget().minimumWidth(), 560)
        self.assertEqual(groups["Render Range"].parentWidget().maximumWidth(), 580)
        omnivoice_panel = groups["Voice and Input"].parentWidget().layout()
        self.assertLess(omnivoice_panel.indexOf(groups["Output and Audio"]), omnivoice_panel.indexOf(groups["OmniVoice Configuration"]))
        left_forms = [
            groups[name].layout()
            for name in ("Voice and Input", "OmniVoice Configuration", "Output and Audio", "Render Range")
        ]
        for form in left_forms:
            label_widths = [
                form.itemAt(row, QFormLayout.ItemRole.LabelRole).widget().width()
                for row in range(form.rowCount())
                if form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            ]
            self.assertTrue(label_widths)
            self.assertEqual(set(label_widths), {105})
        range_form = groups["Render Range"].layout()
        overwrite_index = range_form.indexOf(window.overwrite_existing)
        _, overwrite_role = range_form.getItemPosition(overwrite_index)
        render_index = range_form.indexOf(window.render_range_button)
        _, render_role = range_form.getItemPosition(render_index)
        self.assertEqual(overwrite_role, QFormLayout.ItemRole.FieldRole)
        self.assertEqual(render_role, QFormLayout.ItemRole.FieldRole)
        stability_rows = [
            layout
            for layout in window.findChildren(QFormLayout)
            if any(
                layout.itemAt(row, QFormLayout.ItemRole.LabelRole)
                and layout.itemAt(row, QFormLayout.ItemRole.LabelRole).widget().text() == "Stability"
                for row in range(layout.rowCount())
            )
        ]
        self.assertTrue(stability_rows)
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "script.txt"
            script.write_text("First line.\nSecond line.", encoding="utf-8")
            window.input_file.setText(str(script))
            window.refresh_segment_table()
            buttons = window.segment_table.findChildren(QPushButton)
            self.assertEqual(
                {button.accessibleName() for button in buttons},
                {"Play", "Rerun and overwrite", "Delete audio file"},
            )
            self.assertTrue(all(not button.text() and button.width() == 30 for button in buttons))
        window.load_defaults()
        self.assertEqual(window.steps.value(), 32)
        self.assertEqual(window.output_format.currentText(), "wav")
        with tempfile.TemporaryDirectory() as directory:
            window.active_output_dir = None
            window.output_dir.setText(directory)
            old_session = Path(directory) / "voiceover_20200101_000000"
            old_session.mkdir()
            (old_session / "001.wav").write_bytes(b"old")
            self.assertIsNone(window.current_session_dir())
            script = Path(directory) / "new-script.txt"
            script.write_text("New generation.", encoding="utf-8")
            window.input_file.setText(str(script))
            window.refresh_segment_table()
            self.assertEqual(window.segment_table.item(0, 3).text(), "Pending")
            session = window.current_session_dir(create=True)
            self.assertEqual(session.parent, Path(directory))
            self.assertTrue(session.name.startswith("voiceover_"))
            self.assertTrue(session.is_dir())
        window.input_file.setText("C:/script.srt")
        window.output_dir.setText("C:/output")
        window.output_format.setCurrentText("mp3")
        window.preview_count.setValue(1)
        window.cooldown_seconds.setValue(7)
        window.normalize_audio.setChecked(True)
        window.merge_pause.setValue(1.25)
        window.copy_to_zonos2()
        self.assertEqual(window.zonos2_input_file.text(), "C:/script.srt")
        self.assertEqual(window.zonos2_output_dir.text(), "C:/output")
        self.assertEqual(window.zonos2_output_format.currentText(), "mp3")
        self.assertEqual(window.zonos2_preview_count.value(), 1)
        self.assertEqual(window.zonos2_cooldown_seconds.value(), 7)
        self.assertTrue(window.zonos2_normalize_audio.isChecked())
        self.assertEqual(window.zonos2_merge_pause.value(), 1.25)
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "zonos.txt"
            script.write_text("First ZONOS2 line.\nSecond ZONOS2 line.", encoding="utf-8")
            output = Path(directory) / "output"
            output.mkdir()
            session = output / "zonos2_test"
            session.mkdir()
            (session / "001.mp3").write_bytes(b"complete")
            window.zonos2_input_file.setText(str(script))
            window.zonos2_output_dir.setText(str(output))
            window.zonos2_output_format.setCurrentText("mp3")
            window.active_zonos2_output_dir = session
            window.refresh_zonos2_segment_table()
            self.assertEqual(window.zonos2_segment_table.rowCount(), 2)
            self.assertEqual(window.zonos2_segment_table.item(0, 3).text(), "Completed")
            self.assertEqual(window.zonos2_segment_table.item(1, 3).text(), "Pending")
            buttons = window.zonos2_segment_table.findChildren(QPushButton)
            self.assertEqual(
                {button.accessibleName() for button in buttons},
                {"Play", "Rerun and overwrite", "Delete audio file"},
            )
            self.assertEqual(window.zonos2_segment_audio_path(1), session / "001.mp3")
        with tempfile.TemporaryDirectory() as directory:
            scripts_dir = Path(directory) / "scripts"
            with patch("app.app_data_dir", return_value=Path(directory)):
                window.input_file.clear()
                window.segment_text_input.setPlainText(
                    "First pasted paragraph\ncontinued here.\n\nSecond pasted paragraph."
                )
                window.add_omnivoice_text_segments()
                self.assertEqual(window.segment_table.rowCount(), 2)
                self.assertEqual(
                    window.segment_table.item(0, 2).text(),
                    "First pasted paragraph continued here.",
                )
                window.segment_text_input.setPlainText("Third pasted paragraph.")
                window.add_omnivoice_text_segments()
                self.assertEqual(window.segment_table.rowCount(), 3)
                window.zonos2_input_file.clear()
                window.zonos2_segment_text_input.setPlainText("ZONOS one.\n\nZONOS two.")
                window.add_zonos2_text_segments()
                self.assertEqual(window.zonos2_segment_table.rowCount(), 2)
                self.assertTrue((scripts_dir / "omnivoice_segments.txt").is_file())
                self.assertTrue((scripts_dir / "zonos2_segments.txt").is_file())
        window.active_task_ui = "zonos2"
        window.on_progress(2, 5, "ZONOS2 live progress")
        self.assertEqual(window.zonos2_progress.value(), 2)
        self.assertEqual(window.zonos2_progress.maximum(), 5)
        self.assertIn("ZONOS2 live progress", window.zonos2_log.toPlainText())
        self.assertNotIn("ZONOS2 live progress", window.log.toPlainText())
        zonos_bottom_buttons = [
            window.zonos2_preview_button,
            window.zonos2_render_button,
            window.zonos2_stop_button,
            window.zonos2_merge_button,
            window.zonos2_open_output_button,
        ]
        self.assertEqual(
            [button.text() for button in zonos_bottom_buttons],
            [
                "Render preview",
                "Render all segments",
                "Stop ZONOS2 render",
                "Merge numbered audio files",
                "Open output folder",
            ],
        )
        class SpeakerResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return (
                    b'{"speakers":[{"speaker_id":"default:AmericanFemale",'
                    b'"label":"American Female"},{"speaker_id":"default:AmericanMale",'
                    b'"label":"American Male"}]}'
                )

        with patch("urllib.request.urlopen", return_value=SpeakerResponse()):
            window.refresh_zonos2_voices()
        self.assertGreaterEqual(window.zonos2_voice.count(), 3)
        self.assertEqual(window.zonos2_voice.itemData(1), "default:AmericanFemale")
        window.close()

    def test_chatterbox_v3_preloads_when_app_opens(self):
        previous = os.environ.get("QT_QPA_PLATFORM")
        os.environ["QT_QPA_PLATFORM"] = "minimal"
        try:
            with patch.object(MainWindow, "refresh_profiles"), patch.object(
                ChatterboxV3Tab, "start_preload"
            ) as preload, patch.object(MainWindow, "start_moss_preload") as moss_preload:
                window = MainWindow()
            preload.assert_called_once_with()
            moss_preload.assert_not_called()
            window.close()
        finally:
            if previous is None:
                os.environ.pop("QT_QPA_PLATFORM", None)
            else:
                os.environ["QT_QPA_PLATFORM"] = previous

    def test_piper_vietnamese_reference_uses_diacritics_and_config_language(self):
        vietnamese = PIPER_REFERENCE_TEXTS["vi"]
        self.assertIn("Xin chào", vietnamese)
        self.assertIn("giọng đọc mẫu rõ ràng và tự nhiên", vietnamese)
        self.assertIn("đặc điểm riêng", vietnamese)
        self.assertEqual(piper_config_language({"espeak": {"voice": "vi"}}), "vi")
        self.assertEqual(piper_config_language({"espeak": {"voice": "id"}}), "id")
        self.assertEqual(
            piper_config_language({"language": {"code": "en_US"}}), "en"
        )

    def test_profile_store_delete_removes_only_selected_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ProfileStore()
            store.root = Path(directory)
            selected = store.root / "selected"
            selected.mkdir()
            (selected / "profile.json").write_text("{}", encoding="utf-8")
            keep = store.root / "keep"
            keep.mkdir()
            store.delete("selected")
            self.assertFalse(selected.exists())
            self.assertTrue(keep.exists())
            with self.assertRaises(ValueError):
                store.delete("..")

    def test_profile_store_can_overwrite_only_selected_transcript(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ProfileStore()
            store.root = Path(directory)
            selected = store.root / "selected"
            selected.mkdir()
            profile_path = selected / "profile.json"
            profile_path.write_text(
                json.dumps(
                    {
                        "name": "selected",
                        "reference_audio": "reference.wav",
                        "reference_text": "Old transcript",
                        "language": "en",
                    }
                ),
                encoding="utf-8",
            )

            updated = store.update_transcript("selected", "  New transcript  ")

            self.assertEqual(updated["reference_text"], "New transcript")
            self.assertEqual(updated["reference_audio"], "reference.wav")
            self.assertEqual(updated["language"], "en")
            self.assertIn("transcript_updated_at", updated)
            self.assertEqual(store.load("selected")["reference_text"], "New transcript")
            with self.assertRaises(ValueError):
                store.update_transcript("selected", "   ")

    def test_voice_design_filter_and_profile_save(self):
        settings = {
            "pitch_semitones": 1.2,
            "formant_semitones": 0.7,
            "warmth_db": 2.0,
            "brightness_db": -1.0,
            "speed": 0.98,
        }
        audio_filter = voice_design_audio_filter(settings)
        self.assertEqual(audio_filter.count("rubberband="), 1)
        self.assertIn("formant=preserved", audio_filter)
        self.assertIn("transients=mixed", audio_filter)
        self.assertIn("detector=soft", audio_filter)
        self.assertIn("window=short", audio_filter)
        self.assertIn("smoothing=on", audio_filter)
        self.assertIn("pitchq=quality", audio_filter)
        self.assertNotIn("window=long", audio_filter)
        self.assertNotIn("smoothing=off", audio_filter)
        self.assertIn("equalizer=f=320", audio_filter)
        self.assertIn("equalizer=f=2600", audio_filter)
        self.assertIn("lowshelf=f=220:g=2.00", audio_filter)
        self.assertIn("highshelf=f=3500:g=-1.00", audio_filter)
        neutral_filter = voice_design_audio_filter(
            {
                "pitch_semitones": 0.0,
                "formant_semitones": 0.4,
                "warmth_db": 0.8,
                "brightness_db": 0.3,
                "speed": 1.0,
            }
        )
        self.assertNotIn("rubberband=", neutral_filter)

        with tempfile.TemporaryDirectory() as directory:
            store = ProfileStore()
            store.root = Path(directory) / "profiles"
            store.root.mkdir()
            preview = Path(directory) / "preview.wav"
            preview.write_bytes(b"preview audio")
            source = {
                "name": "source",
                "reference_text": "Reference transcript",
                "language": "vi",
            }
            profile = store.save_designed_variant("new-variant", preview, source, settings)
            self.assertEqual(profile["source_profile"], "source")
            self.assertEqual(profile["reference_text"], "Reference transcript")
            self.assertEqual(profile["voice_design"], settings)
            self.assertTrue(Path(profile["reference_audio"]).is_file())
            with self.assertRaises(ValueError):
                store.save_designed_variant("new-variant", preview, source, settings)

    def test_voice_design_ffmpeg_preview_smoke(self):
        import soundfile as sf

        with tempfile.TemporaryDirectory() as directory:
            sample_rate = 24000
            time_axis = np.arange(sample_rate * 2, dtype=np.float32) / sample_rate
            audio = (0.12 * np.sin(2 * np.pi * 180 * time_axis)).astype(np.float32)
            source = Path(directory) / "source.wav"
            destination = Path(directory) / "preview.wav"
            sf.write(source, audio, sample_rate)
            result = render_voice_design_preview(
                source,
                destination,
                {
                    "pitch_semitones": 0.8,
                    "formant_semitones": 0.4,
                    "warmth_db": 1.0,
                    "brightness_db": 0.5,
                    "speed": 1.02,
                },
            )
            info = sf.info(result)
            self.assertEqual(info.samplerate, 24000)
            self.assertGreater(info.duration, 1.5)

    def test_voice_transcript_worker_fills_transcript_result(self):
        worker = VoiceTranscriptWorker(Path("reference.wav"), "en")
        completed = []
        failed = []
        worker.completed.connect(completed.append)
        worker.failed.connect(failed.append)

        with (
            patch("app.apply_settings"),
            patch("app.transcribe_reference", return_value="Generated transcript") as transcribe,
        ):
            worker.run()

        self.assertEqual(completed, ["Generated transcript"])
        self.assertEqual(failed, [])
        transcribe.assert_called_once()

    def test_auto_transcript_validates_audio_without_undefined_pipeline_name(self):
        with patch.object(MainWindow, "refresh_profiles"):
            window = MainWindow()
        window.reference_audio.setText("missing-reference.wav")

        with patch.object(QMessageBox, "critical") as critical:
            window.auto_transcribe_selected_voice()

        critical.assert_called_once()
        error_message = str(critical.call_args.args[2])
        self.assertIn("Select a saved voice", error_message)
        self.assertNotIn("auto_pipeline", error_message)
        window.close()

    def test_save_profile_without_new_name_updates_selected_transcript(self):
        with patch.object(MainWindow, "refresh_profiles"):
            window = MainWindow()
        with tempfile.TemporaryDirectory() as directory:
            window.store.root = Path(directory)
            selected = window.store.root / "selected"
            selected.mkdir()
            (selected / "profile.json").write_text(
                json.dumps(
                    {
                        "name": "selected",
                        "reference_audio": "reference.wav",
                        "reference_text": "Old transcript",
                        "language": "en",
                    }
                ),
                encoding="utf-8",
            )
            window.profile.addItem("selected", "selected")
            window.profile_name.clear()
            window.reference_text.setPlainText("Updated from Save button")

            with (
                patch.object(window, "persist_settings"),
                patch.object(
                    QMessageBox,
                    "question",
                    return_value=QMessageBox.StandardButton.Yes,
                ) as confirm,
                patch.object(QMessageBox, "information"),
            ):
                window.save_profile()

            self.assertEqual(
                window.store.load("selected")["reference_text"],
                "Updated from Save button",
            )
            self.assertIsNone(window.worker)
            self.assertIn("Transcript updated", window.voice_list_status.text())
            confirm.assert_called_once()
        window.close()

    def test_save_profile_does_not_overwrite_when_confirmation_is_declined(self):
        with patch.object(MainWindow, "refresh_profiles"):
            window = MainWindow()
        with tempfile.TemporaryDirectory() as directory:
            window.store.root = Path(directory)
            selected = window.store.root / "selected"
            selected.mkdir()
            (selected / "profile.json").write_text(
                json.dumps(
                    {
                        "name": "selected",
                        "reference_audio": "reference.wav",
                        "reference_text": "Keep this transcript",
                        "language": "en",
                    }
                ),
                encoding="utf-8",
            )
            window.profile.addItem("selected", "selected")
            window.profile_name.clear()
            window.reference_text.setPlainText("Do not save this")

            with (
                patch.object(window, "persist_settings"),
                patch.object(
                    QMessageBox,
                    "question",
                    return_value=QMessageBox.StandardButton.No,
                ),
            ):
                window.save_profile()

            self.assertEqual(
                window.store.load("selected")["reference_text"],
                "Keep this transcript",
            )
        window.close()

    def test_completed_new_profile_clears_name_and_fills_transcript(self):
        with patch.object(MainWindow, "refresh_profiles"):
            window = MainWindow()
        window.active_task_ui = "voice_list"
        window.profile_name.setText("new-voice")
        window.reference_text.clear()
        profile = {
            "name": "new-voice",
            "reference_text": "Transcript generated during profile save.",
        }

        with (
            patch.object(window, "refresh_profiles") as refresh,
            patch.object(QMessageBox, "information"),
        ):
            window.on_profile_completed(profile)

        refresh.assert_called_once_with("new-voice")
        self.assertEqual(window.profile_name.text(), "")
        self.assertEqual(
            window.reference_text.toPlainText(),
            "Transcript generated during profile save.",
        )
        window.close()

    def test_tools_tab_exposes_gemini_trailer_logo_controls(self):
        with patch.object(MainWindow, "refresh_profiles"):
            window = MainWindow()
        sub_tabs = [
            tabs for tabs in window.findChildren(QTabWidget)
            if tabs.count() == 2 and tabs.tabText(0) == "Remove video logo"
        ]
        self.assertEqual(len(sub_tabs), 1)
        self.assertEqual(sub_tabs[0].tabText(1), "Update missed storyboard prompts")
        self.assertEqual(window.tools_status.text(), "Tools ready.")
        self.assertEqual(
            window.tools_trailer_path.placeholderText(),
            "Select a trailer video generated by Gemini",
        )
        self.assertEqual(
            window.missed_storyboard_images_dir.placeholderText(),
            "Select the image folder to check sequence numbers",
        )
        self.assertEqual(
            window.missed_storyboard_prompt_file.placeholderText(),
            "Select the storyboard prompt TXT file",
        )
        self.assertEqual(
            window.missed_storyboard_status.text(),
            "Ready to check the image folder and storyboard prompt.",
        )
        self.assertEqual(window.tools_analyze_button.text(), "Analyze & Preview")
        self.assertEqual(window.tools_logo_size.value(), 15)
        self.assertEqual(window.tools_logo_margin.value(), 10)
        self.assertEqual(
            window.tools_lama_rerun_button.text(), "Rerun LaMa with Current Mask"
        )
        self.assertEqual(
            window.tools_temporal_rerun_button.text(),
            "Run Stable Clean",
        )
        self.assertNotIn(
            "Remove Logo Video",
            {button.text() for button in window.findChildren(QPushButton)},
        )
        obsolete_logo_buttons = {
            "View Mask",
            "View Premium Safe",
            "Use Mask for Watermark",
            "Use Premium Safe for Watermark",
        }
        self.assertTrue(
            obsolete_logo_buttons.isdisjoint(
                {button.text() for button in window.findChildren(QPushButton)}
            )
        )
        self.assertEqual(window.tools_view_temporal_button.text(), "View Stable Clean")
        self.assertEqual(
            window.tools_use_temporal_button.text(),
            "Use Stable Clean for Watermark",
        )
        self.assertEqual(window.missed_storyboard_check_button.text(), "Check Missing Images")
        self.assertEqual(
            window.missed_storyboard_create_button.text(), "Create Selected Prompts TXT"
        )
        self.assertEqual(window.missed_storyboard_open_button.text(), "Open Output Folder")
        self.assertEqual(
            window.missed_storyboard_toggle_table_button.text(), "Hide Number Table"
        )
        self.assertEqual(window.missed_storyboard_number_table.rowCount(), 10)
        self.assertEqual(window.missed_storyboard_number_table.columnCount(), 10)
        self.assertEqual(len(window.missed_storyboard_number_checks), 100)
        self.assertEqual(window.missed_storyboard_number_checks[1].text(), "1")
        self.assertEqual(window.missed_storyboard_number_checks[100].text(), "100")
        window.missed_storyboard_add_row_button.click()
        self.assertEqual(window.missed_storyboard_number_table.rowCount(), 11)
        self.assertEqual(window.missed_storyboard_number_checks[110].text(), "110")
        window.missed_storyboard_toggle_table_button.click()
        self.assertTrue(window.missed_storyboard_number_group.isHidden())
        self.assertEqual(
            window.missed_storyboard_toggle_table_button.text(), "Show Number Table"
        )
        window.missed_storyboard_toggle_table_button.click()
        self.assertFalse(window.missed_storyboard_number_group.isHidden())
        window.tools_trailer_path.setText("C:/video/trailer.mp4")
        self.assertEqual(
            window._tools_output(Path("C:/video/trailer.mp4"), "premium").name,
            "trailer_no_gemini_logo_premium.mp4",
        )
        self.assertEqual(
            window._tools_output(Path("C:/video/trailer.mp4"), "temporal").name,
            "trailer_no_gemini_logo_temporal.mp4",
        )
        x, y, width, height = gemini_logo_box(1920, 1080, 9, 7)
        self.assertGreater(x, 1600)
        self.assertGreater(y, 800)
        self.assertEqual(width % 2, 0)
        self.assertEqual(height % 2, 0)
        self.assertEqual(
            gemini_temporal_roi(1920, 1080, (1704, 864, 72, 72)),
            (1536, 696, 384, 384),
        )
        self.assertFalse(window.tools_lama_rerun_button.isEnabled())
        window.tools_manual_box = (1704, 864, 72, 72)
        window.on_tools_completed("", "", "", "", {"evaluated": "stable"})
        self.assertTrue(window.tools_lama_rerun_button.isEnabled())
        window.close()

    def test_parse_storyboard_prompt_blocks(self):
        text = """1. first prompt
line two

2) second prompt

003: third prompt
still third
"""
        blocks = MainWindow.parse_storyboard_prompt_blocks(text)
        self.assertEqual(sorted(blocks), [1, 2, 3])
        self.assertIn("line two", blocks[1])
        self.assertIn("second prompt", blocks[2])
        self.assertIn("still third", blocks[3])

    def test_gemini_shape_mask_rejects_alpha_background_floor(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "mask.png"
            create_gemini_shape_mask(128, 128, (0, 0, 128, 128), output)
            values = list(Image.open(output).convert("L").getdata())
        white = sum(value > 0 for value in values)
        self.assertGreater(white, 1000)
        self.assertLess(white, 128 * 128 * 0.65)

    def test_visible_gemini_outline_is_not_marked_safe(self):
        self.assertFalse(gemini_residual_is_safe(0.14, 0.12, 0.004))
        self.assertFalse(gemini_residual_is_safe(0.02, 0.02, 0.05))
        self.assertTrue(gemini_residual_is_safe(0.06, 0.07, 0.01))

    def test_generated_gemini_result_resolves_to_original(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            original = root / "trailer.mp4"
            generated = root / "trailer_no_gemini_logo_temporal_2.mp4"
            original.write_bytes(b"original")
            generated.write_bytes(b"generated")
            self.assertEqual(gemini_original_source(generated), original)

    def test_temporal_mask_expands_to_cover_compression_halo(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            exact = root / "exact.png"
            expanded = root / "expanded.png"
            create_gemini_shape_mask(128, 128, (32, 32, 64, 64), exact)
            create_expanded_gemini_mask(exact, expanded, padding=6)
            exact_count = sum(value > 0 for value in Image.open(exact).getdata())
            expanded_count = sum(value > 0 for value in Image.open(expanded).getdata())
            self.assertGreater(expanded_count, exact_count)
            self.assertLess(expanded_count, 128 * 128 // 2)

    def test_temporal_scene_detector_isolates_hard_cuts(self):
        import cv2
        import numpy as np

        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "cuts.mp4"
            writer = cv2.VideoWriter(
                str(video), cv2.VideoWriter_fourcc(*"mp4v"), 24, (160, 96)
            )
            for color in ((10, 20, 30), (220, 30, 20), (20, 220, 230)):
                for _ in range(24):
                    writer.write(np.full((96, 160, 3), color, dtype=np.uint8))
            writer.release()
            self.assertEqual(
                detect_video_scene_ranges(str(video), 72),
                [(0, 24), (24, 48), (48, 72)],
            )

    def test_primary_refine_uses_stable_clean(self):
        worker = GeminiLogoWorker(
            "source.mp4", "mask.mp4", "premium.mp4", "stable.mp4", "lama.mp4",
            9, 7, (100, 100, 48, 48), mode="stable",
        )
        with (
            patch.object(worker, "_run_stable_clean") as stable,
            patch("app.score_gemini_video_residual", return_value={"safe": True}),
        ):
            worker.run()
        stable.assert_called_once_with((100, 100, 48, 48))

    def test_lama_fallback_reads_the_original_video(self):
        source = Path("app.py").read_text(encoding="utf-8")
        start = source.index("    def _run_lama_inpaint(")
        end = source.index("\n    def ", start + 5)
        lama_source = source[start:end]
        self.assertIn("cv2.VideoCapture(self.source)", lama_source)
        self.assertIn('"-i", self.source', lama_source)
        self.assertNotIn("VideoCapture(self.alpha_output)", lama_source)

    def test_stable_clean_uses_lama_anchors_and_bidirectional_flow(self):
        source = Path("stable_clean_runner.py").read_text(encoding="utf-8")
        self.assertIn("choose_anchors", source)
        self.assertIn("forward_weight", source)
        self.assertIn("backward_weight", source)
        self.assertIn("calcOpticalFlowFarneback", source)
        self.assertNotIn("ProPainter", source)
        app_source = Path("app.py").read_text(encoding="utf-8")
        self.assertIn('"--alpha-asset"', app_source)
        self.assertIn('"--anchor-stride", "6"', app_source)

    def test_stable_clean_mask_follows_gemini_shape_not_selection_rectangle(self):
        hard, feather, ring = build_masks(
            (1536, 696, 296, 296), (1702, 862, 74, 74), 256,
            str(Path("assets") / "gemini_bg_96.png"),
        )
        self.assertEqual(float(hard[176, 176]), 1.0)
        self.assertEqual(float(hard[146, 146]), 0.0)
        self.assertLess(int(np.count_nonzero(hard)), 3500)
        self.assertTrue(np.any(feather > 0))
        self.assertTrue(np.any(ring))

    def test_stable_clean_matches_generated_patch_to_current_exposure(self):
        candidate = np.full((64, 64, 3), 190, dtype=np.uint8)
        target = np.full((64, 64, 3), 35, dtype=np.uint8)
        ring = np.zeros((64, 64), dtype=bool)
        ring[4:12, 4:60] = True
        corrected = match_local_color(candidate, target, ring)
        self.assertLessEqual(abs(float(np.median(corrected)) - 35.0), 1.0)

    def test_vsr_watermark_mask_is_expanded_rectangle_not_gemini_shape(self):
        mask = create_rectangular_mask(320, 180, (240, 100, 48, 48))
        self.assertTrue((mask[90:159, 230:299] == 255).all())
        self.assertEqual(int(mask[89, 230]), 0)
        self.assertEqual(int(mask[100, 229]), 0)

    def test_vsr_core_batches_leave_room_for_bidirectional_context(self):
        batches = balanced_batches(1503, 1698, 18)
        containing = [batch for batch in batches if batch[0] <= 1530 < batch[1]]
        self.assertEqual(len(containing), 1)
        core_start, core_end = containing[0]
        self.assertLessEqual(core_end - core_start, 18)
        self.assertLess(max(1503, core_start - 9), 1530)
        self.assertGreater(min(1698, core_end + 9), 1530)

    def test_scene_detection_catches_similar_color_hard_cuts(self):
        source = Path("app.py").read_text(encoding="utf-8")
        self.assertIn("pixel_change >= 0.10 and histogram_change >= 0.30", source)

    def test_missed_storyboard_check_uses_prompt_max_number(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_dir = root / "images"
            image_dir.mkdir()
            for number in (1, 2, 4):
                (image_dir / f"{number:03d}.png").write_bytes(b"x")
            prompt_file = root / "storyboard.txt"
            prompt_file.write_text(
                "1. one\n\n2. two\n\n3. three\n\n4. four\n\n5. five\n\n6. six\n",
                encoding="utf-8",
            )
            with patch.object(MainWindow, "refresh_profiles"):
                window = MainWindow()
            window.missed_storyboard_prompt_file.setText(str(prompt_file))
            window.missed_storyboard_images_dir.setText(str(image_dir))
            self.assertEqual(window.check_missed_storyboard_images(), [3, 5, 6])
            log_text = window.missed_storyboard_log.toPlainText()
            self.assertIn("range 1 -> 6", log_text)
            self.assertIn("Missed images: 3, 5, 6", log_text)
            window.close()

    def test_selected_storyboard_numbers_create_filtered_prompt_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            prompt_file = root / "storyboard.txt"
            prompt_file.write_text(
                "1. First prompt\n\n2. Second prompt line one\nline two\n\n"
                "3. Third prompt\n\n4. Fourth prompt\n",
                encoding="utf-8",
            )
            with patch.object(MainWindow, "refresh_profiles"):
                window = MainWindow()
            window.missed_storyboard_prompt_file.setText(str(prompt_file))
            window.missed_storyboard_number_checks[2].setChecked(True)
            window.missed_storyboard_number_checks[4].setChecked(True)
            window.create_missed_storyboard_prompt_file()
            output = Path(window.missed_storyboard_output)
            self.assertTrue(output.is_file())
            self.assertEqual(output.name, "storyboard_selected_prompts.txt")
            content = output.read_text(encoding="utf-8")
            self.assertIn("2. Second prompt line one\nline two", content)
            self.assertIn("4. Fourth prompt", content)
            self.assertNotIn("1. First prompt", content)
            self.assertNotIn("3. Third prompt", content)
            self.assertEqual(
                window.missed_storyboard_selection_label.text(),
                "Selected: 2 number(s)",
            )
            window.close()

    def test_batch_processing_queue_ui_and_logic(self):
        with patch.object(MainWindow, "refresh_profiles"):
            window = MainWindow()
            
        groups = {group.title(): group for group in window.findChildren(QGroupBox)}
        self.assertIn("Batch Processing Queue", groups)
        
        self.assertIsNotNone(window.batch_scroll)
        self.assertIsNotNone(window.add_row_btn)
        
        self.assertEqual(len(window.batch_rows), 1)
        first_row = window.batch_rows[0]
        self.assertTrue(first_row["view_radio"].isChecked())
        
        window.add_batch_row_clicked()
        self.assertEqual(len(window.batch_rows), 2)
        second_row = window.batch_rows[1]
        self.assertFalse(second_row["view_radio"].isChecked())
        
        first_row["input_edit"].setText("C:/first.srt")
        first_row["output_edit"].setText("C:/first_out")
        self.assertEqual(window.input_file.text(), "C:/first.srt")
        self.assertEqual(window.output_dir.text(), "C:/first_out")
        
        second_row["view_radio"].setChecked(True)
        self.assertEqual(window.input_file.text(), "")
        
        window.remove_batch_row(first_row)
        self.assertEqual(len(window.batch_rows), 1)
        self.assertTrue(second_row["view_radio"].isChecked())
        
        # Height check for 1 row
        self.assertEqual(window.batch_scroll.maximumHeight(), 32 + 8)
        
        # Height check for 2 rows
        window.add_batch_row_clicked()
        self.assertEqual(window.batch_scroll.maximumHeight(), 2 * 32 + 6 + 8)
        
        # Height check for 3 rows
        window.add_batch_row_clicked()
        self.assertEqual(window.batch_scroll.maximumHeight(), 3 * 32 + 12 + 8)
        
        # Height check for 4 rows (should cap/limit to 3.5 rows)
        window.add_batch_row_clicked()
        self.assertEqual(window.batch_scroll.maximumHeight(), int(3.5 * 32 + 3 * 6 + 8))
        
        window.close()

    def test_caption_preview_updates_for_typography_and_highlight(self):
        with patch.object(MainWindow, "refresh_profiles"):
            window = MainWindow()

        original = window.caption_preview.debug_snapshot()
        self.assertIn("Your caption lights up word by word", original)
        self.assertEqual(
            [window.caption_font_family.itemText(index) for index in range(window.caption_font_family.count())],
            [
                "Arial",
                "Segoe UI",
                "Montserrat",
                "Poppins",
                "Anton",
                "Bebas Neue",
                "Impact",
                "Arial Black",
                "Tahoma",
                "Verdana",
            ],
        )
        window.caption_font_family.setCurrentText("Anton")
        window.caption_font_size.setValue(72)
        window.update_caption_preview()
        typography_preview = window.caption_preview.debug_snapshot()
        self.assertNotEqual(original, typography_preview)
        self.assertIn("Anton", typography_preview)
        self.assertIn("72", typography_preview)

        window.caption_highlight_type.setCurrentText("None")
        window.update_caption_preview()
        no_highlight = window.caption_preview.debug_snapshot()
        window.caption_highlight_type.setCurrentText("Active background")
        window.update_caption_preview()
        active_background = window.caption_preview.debug_snapshot()
        window.caption_highlight_type.setCurrentText("Progressive sweep")
        window.update_caption_preview()
        sweep = window.caption_preview.debug_snapshot()
        self.assertNotEqual(no_highlight, active_background)
        self.assertNotEqual(active_background, sweep)
        self.assertIn("Progressive sweep", sweep)
        window.caption_background_mode.setCurrentText("Line box")
        window.caption_corner_radius.setValue(24)
        window.update_caption_preview()
        self.assertIn("radius=24", window.caption_preview.debug_snapshot())
        window.caption_preview.resize(720, 260)
        pixmap = QPixmap(window.caption_preview.size())
        pixmap.fill(QColor("#111821"))
        window.caption_preview.render(pixmap)
        image = pixmap.toImage()
        bg = QColor("#111821").rgb()
        different_pixels = 0
        for y in range(0, image.height(), 8):
            for x in range(0, image.width(), 8):
                if image.pixel(x, y) != bg:
                    different_pixels += 1
        self.assertGreater(different_pixels, 20)
        window.close()

    def test_caption_youtube_auto_position_and_action_layout(self):
        window = MainWindow()
        window.caption_anchor.setCurrentText("Top")
        window.caption_alignment.setCurrentText("Left")
        window.caption_margin_bottom.setValue(12)
        window.caption_youtube_auto.setChecked(True)

        layout = window.caption_config()["layout"]
        self.assertEqual(layout["anchor"], "Bottom")
        self.assertEqual(layout["alignment"], "Center")
        self.assertEqual(layout["margin_bottom"], 96)
        self.assertTrue(layout["youtube_auto_position"])
        self.assertIn("youtube_auto=True", window.caption_preview.debug_snapshot())
        self.assertLess(window.caption_render_button.minimumHeight(), 58)
        window.close()

    def test_caption_source_is_transcribed_instead_of_using_demo_text(self):
        window = MainWindow()
        window.caption_import_file.clear()
        window.caption_video_file.setText(__file__)
        expected = [{"start": 1.0, "end": 2.0, "text": "Real speech", "words": []}]
        with patch.object(window, "transcribe_caption_source", return_value=expected) as transcribe:
            self.assertEqual(window.current_caption_segments(), expected)
        transcribe.assert_called_once_with(Path(__file__))
        window.close()

    def test_caption_status_does_not_force_preview_panel_width(self):
        window = MainWindow()
        self.assertTrue(window.caption_status.wordWrap())
        self.assertEqual(
            window.caption_status.sizePolicy().horizontalPolicy(),
            QSizePolicy.Policy.Ignored,
        )
        window.close()

    def test_caption_ass_renders_one_highlight_layer_per_word(self):
        window = MainWindow()
        window.caption_highlight_type.setCurrentText("Active color")
        window.caption_active_color.setText("#FF8A00")
        config = window.caption_config()
        segments = [{
            "start": 0.0,
            "end": 2.0,
            "text": "Hello world",
            "words": [
                {"text": "Hello", "start": 0.0, "end": 0.8},
                {"text": "world", "start": 0.8, "end": 2.0},
            ],
        }]
        ass = window.segments_to_ass(segments, config)
        dialogue_lines = [line for line in ass.splitlines() if line.startswith("Dialogue:")]
        self.assertEqual(len(dialogue_lines), 2)
        self.assertIn(r"\1c&H008AFF&", ass)
        self.assertIn("0:00:00.00,0:00:00.80", dialogue_lines[0])
        self.assertIn("0:00:00.80,0:00:02.00", dialogue_lines[1])
        window.close()

    def test_caption_highlight_events_have_no_silent_gaps(self):
        window = MainWindow()
        window.caption_highlight_type.setCurrentText("Active color")
        config = window.caption_config()
        segments = [{
            "start": 0.0,
            "end": 3.0,
            "text": "one two three",
            "words": [
                {"text": "one", "start": 0.0, "end": 0.5},
                {"text": "two", "start": 1.0, "end": 1.4},
                {"text": "three", "start": 2.0, "end": 2.5},
            ],
        }]
        dialogue_lines = [
            line for line in window.segments_to_ass(segments, config).splitlines()
            if line.startswith("Dialogue:")
        ]
        self.assertIn("0:00:00.00,0:00:01.00", dialogue_lines[0])
        self.assertIn("0:00:01.00,0:00:02.00", dialogue_lines[1])
        self.assertIn("0:00:02.00,0:00:03.00", dialogue_lines[2])
        window.close()

    def test_caption_highlight_events_do_not_overlap_when_word_timestamps_overlap(self):
        window = MainWindow()
        window.caption_highlight_type.setCurrentText("Active color")
        config = window.caption_config()
        segments = [{
            "start": 10.0,
            "end": 12.0,
            "text": "it is infuriating marcus vale",
            "words": [
                {"text": "it", "start": 10.0, "end": 10.5},
                {"text": "is", "start": 10.2, "end": 10.6},
                {"text": "infuriating", "start": 10.3, "end": 10.9},
                {"text": "marcus", "start": 10.8, "end": 11.1},
                {"text": "vale", "start": 10.7, "end": 11.5},
            ],
        }]
        dialogue_lines = [
            line for line in window.segments_to_ass(segments, config).splitlines()
            if line.startswith("Dialogue:")
        ]

        def to_seconds(value: str) -> float:
            hours, minutes, rest = value.split(":")
            return int(hours) * 3600 + int(minutes) * 60 + float(rest)

        intervals = []
        for line in dialogue_lines:
            _, start, end, *_ = line.split(",", 4)
            intervals.append((to_seconds(start), to_seconds(end)))
        self.assertTrue(all(start < end for start, end in intervals))
        self.assertTrue(all(intervals[i][1] <= intervals[i + 1][0] for i in range(len(intervals) - 1)))
        window.close()

    def test_pro_highlight_keeps_supported_whisper_engine(self):
        window = MainWindow()
        window.caption_engine.setCurrentText("stable-ts")
        window.caption_mode.setCurrentText("Pro Highlight")
        window.update_caption_mode()
        self.assertEqual(window.caption_engine.currentText(), "faster-whisper")
        self.assertTrue(window.caption_word_timing.isChecked())
        self.assertEqual(window.caption_render_engine.currentText(), "ASS karaoke")
        window.close()

    def test_caption_load_defaults_keeps_file_paths(self):
        window = MainWindow()
        window.caption_video_file.setText("C:/media/source.mp4")
        window.caption_import_file.setText("C:/media/source.srt")
        window.caption_output_dir.setText("C:/media/output")
        window.caption_max_words.setValue(11)
        window.caption_burn_video.setChecked(False)

        window.load_default_caption_config()

        self.assertEqual(window.caption_video_file.text(), "C:/media/source.mp4")
        self.assertEqual(window.caption_import_file.text(), "C:/media/source.srt")
        self.assertEqual(window.caption_output_dir.text(), "C:/media/output")
        self.assertEqual(window.caption_max_words.value(), 6)
        self.assertTrue(window.caption_burn_video.isChecked())
        self.assertIsNotNone(window.caption_save_config_button.parent())
        self.assertIsNotNone(window.caption_load_defaults_button.parent())
        window.close()

    def test_saved_caption_configuration_is_restored(self):
        window = MainWindow()
        saved = window.caption_config()
        saved["style"]["font_family"] = "Anton"
        saved["style"]["font_size"] = 77
        saved["layout"]["max_words_per_line"] = 5
        saved["layout"]["youtube_auto_position"] = False
        window.settings["caption_config_json"] = json.dumps(saved)

        self.assertTrue(window.restore_saved_caption_configuration())
        self.assertEqual(window.caption_font_family.currentText(), "Anton")
        self.assertEqual(window.caption_font_size.value(), 77)
        self.assertEqual(window.caption_max_words.value(), 5)
        self.assertFalse(window.caption_youtube_auto.isChecked())
        window.close()

    def test_caption_segments_are_limited_to_selected_word_count(self):
        window = MainWindow()
        segment = {
            "start": 0.0,
            "end": 9.0,
            "text": "one two three four five six seven eight nine",
            "words": [],
        }
        grouped = window.group_caption_segments([segment], max_words=5)
        self.assertEqual([len(item["text"].split()) for item in grouped], [5, 4])
        self.assertEqual(grouped[0]["text"], "one two three four five")
        self.assertEqual(grouped[1]["text"], "six seven eight nine")
        self.assertEqual(grouped[0]["end"], grouped[1]["start"])
        window.close()

    def test_caption_stop_terminates_active_transcription(self):
        window = MainWindow()

        class FakeProcess:
            terminated = False

            def is_alive(self):
                return True

            def terminate(self):
                self.terminated = True

            def join(self, timeout=None):
                pass

        process = FakeProcess()
        window.caption_transcribe_job = process
        window.caption_stop_button.setEnabled(True)
        window.stop_caption_render()

        self.assertTrue(process.terminated)
        self.assertIsNone(window.caption_transcribe_job)
        self.assertTrue(window.caption_cancel_requested)
        self.assertFalse(window.caption_stop_button.isEnabled())
        window.close()

    def test_caption_batch_rows_and_collapsible_groups(self):
        window = MainWindow()
        self.assertEqual(len(window.caption_batch_rows), 1)
        second = window.add_caption_batch_row("C:/video/two.mp4", "", "C:/output")
        self.assertEqual(len(window.caption_batch_rows), 2)
        self.assertEqual(second["source"].text(), "C:/video/two.mp4")
        window.remove_caption_batch_row(second)
        self.assertEqual(len(window.caption_batch_rows), 1)

        caption_groups = [
            group for group in window.findChildren(QGroupBox)
            if group.title() in {"Input and Mode", "Typography", "Colors", "Highlight", "Export"}
        ]
        self.assertEqual(len(caption_groups), 5)
        for group in caption_groups:
            self.assertTrue(group.isCheckable())
        caption_groups[0].setChecked(False)
        self.assertEqual(caption_groups[0].maximumHeight(), 30)
        window.close()

    def test_caption_default_output_folder_uses_source_parent_and_timestamp(self):
        with patch.object(MainWindow, "refresh_profiles"):
            window = MainWindow()
        with tempfile.TemporaryDirectory() as directory:
            source_dir = Path(directory) / "video-list"
            source_dir.mkdir()
            video = source_dir / "clip.mp4"
            video.write_bytes(b"placeholder")
            window.caption_video_file.setText(str(video))
            window.caption_output_dir.clear()
            output_root = window.caption_output_root(create=False)
            self.assertEqual(output_root.parent, source_dir)
            self.assertRegex(output_root.name, r"video-list_caption_exports_\d{8}_\d{6}")
        window.close()



if __name__ == "__main__":
    unittest.main()
