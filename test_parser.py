import tempfile
import unittest
from pathlib import Path

from core import (
    clean_segment_text,
    infer_speaking_direction,
    normalize_omnivoice_instruct,
    parse_input,
    parse_paragraph_segments,
    parse_timestamp,
)


class ParserTests(unittest.TestCase):
    def test_auto_speaking_direction_uses_only_supported_attributes(self):
        self.assertEqual(
            infer_speaking_direction("She whispered softly.", "Dramatic cinematic narration"),
            "low pitch, whisper",
        )

    def test_unsupported_direction_is_safely_removed(self):
        self.assertEqual(normalize_omnivoice_instruct("angry and intense"), "")
        self.assertEqual(
            normalize_omnivoice_instruct("elderly, low pitch, dramatic"), "elderly, low pitch"
        )

    def test_four_digit_fraction(self):
        self.assertAlmostEqual(parse_timestamp("00:00:15,2170"), 15.217)

    def test_srt_blocks(self):
        content = """1
00:00:00,0000 --> 00:00:01,2500
Hello world.

2
00:00:01,3500 --> 00:00:03,0000
Second line.
Continued.
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.srt"
            path.write_text(content, encoding="utf-8")
            segments = parse_input(path)
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[1].text, "Second line. Continued.")
        self.assertAlmostEqual(segments[0].duration, 1.25)

    def test_builder_numbering_is_removed_from_segments(self):
        self.assertEqual(clean_segment_text("001. First clean segment."), "First clean segment.")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.txt"
            path.write_text("1. First line.\n2. Second line.\nNo number.", encoding="utf-8")
            segments = parse_input(path)
        self.assertEqual([segment.text for segment in segments], ["First line.", "Second line.", "No number."])

    def test_pasted_paragraphs_become_segments(self):
        self.assertEqual(
            parse_paragraph_segments("1. First line\ncontinued.\n\n2. Second paragraph.\n\n\nThird."),
            ["First line continued.", "Second paragraph.", "Third."],
        )


if __name__ == "__main__":
    unittest.main()
