import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import soundfile as sf

from app import (
    MergeWorker,
    NormalizeBatchWorker,
    apply_constant_gain,
    measure_speech_rms_db,
    normalize_completed_batch,
)


class MergeTests(unittest.TestCase):
    def test_merge_variant_ignores_base_voice_files(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "segments"
            source.mkdir()
            (source / "001.wav").write_bytes(b"base")
            (source / "001-a.wav").write_bytes(b"variant")
            worker = MergeWorker(source, "wav", 0, "-a")
            commands = []
            concat_contents = []

            def fake_run(command, **kwargs):
                commands.append(command)
                for part in command:
                    if isinstance(part, str) and part.endswith("concat.txt"):
                        concat_contents.append(Path(part).read_text(encoding="utf-8"))
                Path(command[-1]).write_bytes(b"merged")
                return SimpleNamespace(returncode=0, stderr="")

            with patch("subprocess.run", fake_run):
                worker.run()

            self.assertEqual(len(concat_contents), 1)
            self.assertIn("001-a.wav", concat_contents[0])
            self.assertNotIn("001.wav", concat_contents[0])

    def test_merge_inserts_configured_pause_and_saves_in_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "segments"
            source.mkdir()
            tone = np.zeros(2400, dtype=np.float32)
            sf.write(source / "001.wav", tone, 24000)
            sf.write(source / "002.wav", tone, 24000)

            completed = []
            failed = []
            worker = MergeWorker(source, "wav", 0.45)
            worker.completed.connect(completed.append)
            worker.failed.connect(failed.append)
            worker.run()

            self.assertFalse(failed)
            destination = Path(completed[0])
            self.assertEqual(destination.parent, root)
            self.assertAlmostEqual(sf.info(destination).duration, 0.65, places=2)

    def test_large_merge_uses_short_concat_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "segments"
            source.mkdir()
            for index in range(1, 190):
                (source / f"{index:03d}.wav").write_bytes(b"x")
            commands = []

            def fake_run(command, **kwargs):
                commands.append(command)
                return SimpleNamespace(returncode=0, stderr="")

            worker = MergeWorker(source, "wav", 0.45)
            with patch("app.subprocess.run", side_effect=fake_run):
                worker.run()

            self.assertLess(max(len(" ".join(map(str, command))) for command in commands), 4000)

    def test_completed_batch_normalization_matches_speech_levels(self):
        with tempfile.TemporaryDirectory() as directory:
            quiet = Path(directory) / "001.wav"
            loud = Path(directory) / "002.wav"
            silence = np.zeros(4800, dtype=np.float32)
            sf.write(quiet, np.concatenate([silence, np.full(24000, 0.03)]), 24000)
            sf.write(loud, np.concatenate([silence, np.full(24000, 0.20)]), 24000)
            normalize_completed_batch([quiet, loud])
            quiet_level = measure_speech_rms_db(quiet)
            loud_level = measure_speech_rms_db(loud)
            self.assertAlmostEqual(quiet_level, loud_level, delta=0.5)
            quiet_audio, _ = sf.read(quiet)
            loud_audio, _ = sf.read(loud)
            self.assertLess(np.sqrt(np.mean(quiet_audio[:3600] ** 2)), 0.001)
            self.assertLess(np.sqrt(np.mean(loud_audio[:3600] ** 2)), 0.001)
            self.assertAlmostEqual(sf.info(quiet).duration, 1.2, places=2)
            originals = Path(directory) / "_original_omnivoice"
            self.assertTrue((originals / "001.wav").is_file())
            self.assertTrue((originals / "002.wav").is_file())
            report = Path(directory) / "loudness_before_after.csv"
            with report.open(encoding="utf-8-sig", newline="") as report_file:
                rows = list(csv.DictReader(report_file))
            self.assertEqual([row["file"] for row in rows], ["001.wav", "002.wav"])
            self.assertIn("original_speech_rms_db", rows[0])

    def test_completed_batch_skips_files_already_near_target(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "001.wav"
            sf.write(path, np.full(24000, 0.1, dtype=np.float32), 24000)
            with patch("app.measure_speech_rms_db", return_value=-20.2):
                with patch("app.apply_constant_gain") as apply_gain:
                    normalize_completed_batch([path])
            apply_gain.assert_not_called()

    def test_locked_file_keeps_original_and_explains_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "001.wav"
            original = np.full(24000, 0.03, dtype=np.float32)
            sf.write(path, original, 24000)

            with patch("app.os.replace", side_effect=PermissionError("locked")):
                with self.assertRaisesRegex(PermissionError, "Retry batch normalization"):
                    apply_constant_gain(path, 3.0)

            audio, _ = sf.read(path)
            self.assertAlmostEqual(float(np.mean(audio)), 0.03, places=3)
            self.assertFalse((Path(directory) / ".001.batch-normalized.wav").exists())

    def test_retry_worker_preserves_archived_originals(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            path = source / "001.wav"
            sf.write(path, np.full(24000, 0.03, dtype=np.float32), 24000)
            originals = source / "_original_omnivoice"
            originals.mkdir()
            archived = originals / "001.wav"
            sf.write(archived, np.full(24000, 0.2, dtype=np.float32), 24000)
            archived_before = archived.read_bytes()

            completed = []
            failed = []
            worker = NormalizeBatchWorker(source, "wav")
            worker.completed.connect(completed.append)
            worker.failed.connect(failed.append)
            worker.run()

            self.assertFalse(failed)
            self.assertEqual(completed, [str(source)])
            self.assertEqual(archived.read_bytes(), archived_before)


if __name__ == "__main__":
    unittest.main()
