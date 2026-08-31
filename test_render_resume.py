import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from app import RenderWorker, next_audio_variant_suffix


class FakeOmniVoice:
    loads = 0
    prompts = 0
    generates = 0
    instructions = []

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        cls.loads += 1
        return cls()

    def create_voice_clone_prompt(self, *args, **kwargs):
        type(self).prompts += 1
        return object()

    def generate(self, **kwargs):
        type(self).generates += 1
        type(self).instructions.append(kwargs.get("instruct"))
        self.assert_prompt_reused(kwargs)
        return [np.zeros(240, dtype=np.float32)]

    @staticmethod
    def assert_prompt_reused(kwargs):
        if "voice_clone_prompt" not in kwargs or "ref_audio" in kwargs:
            raise AssertionError("Reusable voice prompt was not used.")


class RenderResumeTests(unittest.TestCase):
    def test_new_voice_variant_uses_next_available_suffix(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "001-a.wav").write_bytes(b"first variant")
            self.assertEqual(next_audio_variant_suffix(output, 2, "wav"), "-b")

    def test_resume_skips_existing_and_reuses_voice_prompt(self):
        FakeOmniVoice.loads = FakeOmniVoice.prompts = FakeOmniVoice.generates = 0
        FakeOmniVoice.instructions = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "script.txt"
            input_path.write_text("one\ntwo\nthree\n", encoding="utf-8")
            output_dir = root / "output"
            output_dir.mkdir()
            (output_dir / "001.wav").write_bytes(b"already complete")
            worker = RenderWorker(
                {"reference_audio": "reference.wav", "reference_text": "reference"},
                input_path,
                output_dir,
                "k2-fsa/OmniVoice",
                8,
                False,
                "wav",
                device_mode="cpu",
                reload_every=2,
                normalize_audio=False,
                speaking_style="Dramatic cinematic narration",
            )
            progress_positions = []
            worker.progress.connect(
                lambda current, total, message: progress_positions.append(
                    (current, total, message)
                )
            )

            fake_module = SimpleNamespace(OmniVoice=FakeOmniVoice)
            with patch.dict(sys.modules, {"omnivoice": fake_module}):
                worker.run()

            manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest), 3)
            self.assertEqual(FakeOmniVoice.generates, 2)
            self.assertEqual(FakeOmniVoice.loads, 2)
            self.assertEqual(FakeOmniVoice.prompts, 2)
            self.assertEqual(FakeOmniVoice.instructions, ["low pitch", "low pitch"])
            segment_messages = [
                current
                for current, _, message in progress_positions
                if message in {"two", "three"}
            ]
            self.assertEqual(segment_messages, [2, 3])
            self.assertNotIn(0, [current for current, _, _ in progress_positions])

if __name__ == "__main__":
    unittest.main()
