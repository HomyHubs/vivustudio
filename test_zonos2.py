import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import numpy as np

from app import Zonos2Worker


class FakeResponse:
    headers = {"X-Audio-Sample-Rate": "44100"}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return np.zeros(128, dtype="<f4").tobytes()


class SpeakerResponse(FakeResponse):
    def read(self):
        return b'{"id":"session:local-clone"}'


class Zonos2Tests(unittest.TestCase):
    def test_worker_uses_isolated_http_server_and_writes_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "script.txt"
            script.write_text("Xin chao\nHello", encoding="utf-8")
            output = root / "output"
            worker = Zonos2Worker(
                "http://localhost:1919",
                script,
                output,
                "wav",
                "raw",
                1.0,
                42,
                True,
                "default:AmericanFemale",
            )
            requests = []

            def fake_urlopen(request, timeout):
                requests.append(json.loads(request.data))
                return FakeResponse()

            with patch("urllib.request.urlopen", fake_urlopen):
                worker.run()

            self.assertEqual(len(requests), 2)
            self.assertFalse(requests[0]["text_normalization"])
            self.assertEqual(requests[0]["seed"], 42)
            self.assertEqual(requests[1]["seed"], 43)
            self.assertEqual(requests[0]["temperature"], 1.15)
            self.assertEqual(requests[0]["topk"], 106)
            self.assertEqual(requests[0]["min_p"], 0.18)
            self.assertEqual(requests[0]["repetition_penalty"], 1.2)
            self.assertEqual(requests[0]["speaker_embedding_id"], "default:AmericanFemale")
            self.assertTrue((output / "001.wav").is_file())
            self.assertTrue((output / "manifest.json").is_file())

    def test_worker_supports_preview_range_and_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "script.txt"
            script.write_text("one\ntwo\nthree", encoding="utf-8")
            output = root / "output"
            output.mkdir()
            (output / "002.wav").write_bytes(b"complete")
            worker = Zonos2Worker(
                "http://localhost:1919",
                script,
                output,
                "wav",
                "en_us",
                1.0,
                42,
                True,
                "",
                start_position=2,
                end_position=3,
            )
            requests = []

            def fake_urlopen(request, timeout):
                requests.append(json.loads(request.data))
                return FakeResponse()

            with patch("urllib.request.urlopen", fake_urlopen):
                worker.run()

            self.assertEqual([request["text"] for request in requests], ["three"])
            self.assertTrue((output / "003.wav").is_file())

    def test_worker_caches_local_reference_before_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "script.txt"
            script.write_text("Xin chao", encoding="utf-8")
            reference = root / "reference.wav"
            reference.write_bytes(b"reference audio")
            worker = Zonos2Worker(
                "http://localhost:1919",
                script,
                root / "output",
                "wav",
                "raw",
                1.0,
                42,
                True,
                reference_audio=str(reference),
                session_id="test-session",
            )
            requests = []

            def fake_urlopen(request, timeout):
                requests.append(request)
                return SpeakerResponse() if request.full_url.endswith("/tts/speakers") else FakeResponse()

            with patch("urllib.request.urlopen", fake_urlopen):
                worker.run()

            self.assertEqual(len(requests), 2)
            self.assertEqual(requests[0].headers["X-tts-session-id"], "test-session")
            generation = json.loads(requests[1].data)
            self.assertEqual(generation["speaker_embedding_id"], "session:local-clone")

    def test_worker_reports_unavailable_server_without_python_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "script.txt"
            script.write_text("Xin chao", encoding="utf-8")
            worker = Zonos2Worker(
                "http://localhost:1919", script, root / "output", "wav", "raw", 1.0, 42, True
            )
            failures = []
            worker.failed.connect(failures.append)

            with patch(
                "urllib.request.urlopen",
                side_effect=urllib.error.URLError(ConnectionRefusedError()),
            ):
                worker.run()

            self.assertEqual(len(failures), 1)
            self.assertIn("Cannot connect to the ZONOS2 server", failures[0])
            self.assertNotIn("Traceback", failures[0])


if __name__ == "__main__":
    unittest.main()
