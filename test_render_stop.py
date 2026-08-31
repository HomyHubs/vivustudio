import unittest
from pathlib import Path


class RenderStopTests(unittest.TestCase):
    def test_stop_controls_are_present(self):
        source = Path("app.py").read_text(encoding="utf-8")
        self.assertIn("def request_cancel(self)", source)
        self.assertIn("def stop_current_render(self)", source)
        self.assertIn("manifest.partial.json", source)
        self.assertIn("voice_clone_prompt", source)
        self.assertIn("Skipping completed", source)
        self.assertIn('generation_form.addRow("Stability"', source)
        self.assertIn("OmniVoice checkpoint", source)
        self.assertIn("configure_ffmpeg()", source)
        self.assertIn("OMNIVOICE_MODEL_LOADING", source)
        self.assertIn("already loading in the background", source)
        self.assertIn('QLabel("Merge pause")', source)


if __name__ == "__main__":
    unittest.main()
