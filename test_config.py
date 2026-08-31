import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config_store
from config_store import apply_settings, load_settings, save_settings, save_tab_settings


class ConfigTests(unittest.TestCase):
    def test_apply_settings_sets_environment(self):
        values = {
            "hf_token": "hf_test",
            "gemini_api_key": "gemini_test",
            "hf_home": "X:/model-cache",
        }
        with patch.dict(os.environ, {}, clear=True):
            apply_settings(values)
            self.assertEqual(os.environ["HF_TOKEN"], "hf_test")
            self.assertEqual(os.environ["HUGGING_FACE_HUB_TOKEN"], "hf_test")
            self.assertEqual(os.environ["GEMINI_API_KEY"], "gemini_test")
            self.assertEqual(os.environ["GOOGLE_API_KEY"], "gemini_test")
            self.assertEqual(os.environ["HF_HOME"], "X:/model-cache")
            self.assertTrue(os.environ["PIP_CACHE_DIR"].endswith("cache\\pip") or os.environ["PIP_CACHE_DIR"].endswith("cache/pip"))

    def test_blank_model_cache_uses_huggingface_default(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(config_store, "CACHE_DIR", Path("C:/portable-app/cache")):
                apply_settings({"hf_home": ""})
            self.assertNotIn("HF_HOME", os.environ)
            self.assertEqual(os.environ["TORCH_HOME"], str(Path("C:/portable-app/cache") / "torch"))
            self.assertEqual(os.environ["HF_HUB_DISABLE_XET"], "1")

    def test_generation_and_output_settings_are_persisted_locally(self):
        values = {
            "hf_token": "",
            "gemini_api_key": "",
            "hf_home": "",
            "merge_pause": "1.25",
            "steps": "24",
            "normalize_audio": "false",
            "output_format": "mp3",
        }
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "data"
            with patch.object(config_store, "DATA_DIR", data_dir):
                with patch.object(config_store, "LEGACY_DIR", Path(directory) / "legacy"):
                    save_settings(values)
                    loaded = load_settings()
                    self.assertEqual(loaded["merge_pause"], "1.25")
                    self.assertEqual(loaded["steps"], "24")
                    self.assertEqual(loaded["normalize_audio"], "false")
                    self.assertEqual(loaded["output_format"], "mp3")
                    self.assertTrue((data_dir / "settings.json").is_file())

    def test_tab_settings_are_saved_to_only_their_own_file(self):
        values = {
            "hf_token": "hf_env",
            "steps": "24",
            "output_format": "mp3",
            "video_effect_fps": "60",
            "caption_model": "medium",
        }
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "data"
            with patch.object(config_store, "DATA_DIR", data_dir):
                with patch.object(config_store, "LEGACY_DIR", Path(directory) / "legacy"):
                    save_tab_settings("video_effect", values)

                    self.assertTrue((data_dir / "video_effect_config.json").is_file())
                    self.assertFalse((data_dir / "voice_clone_config.json").exists())
                    self.assertFalse((data_dir / "caption_config.json").exists())
                    self.assertFalse((data_dir / "settings.json").exists())

                    loaded = load_settings()
                    self.assertEqual(loaded["video_effect_fps"], "60")
                    self.assertEqual(loaded["steps"], config_store.DEFAULTS["steps"])
                    self.assertEqual(loaded["caption_model"], config_store.DEFAULTS["caption_model"])

                    save_tab_settings("environment", values)
                    self.assertTrue((data_dir / "settings.json").is_file())
                    loaded = load_settings()
                    self.assertEqual(loaded["hf_token"], "hf_env")

    def test_existing_voice_over_settings_seed_compatible_zonos2_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "data"
            data_dir.mkdir()
            (data_dir / "settings.json").write_text(
                '{"output_dir":"X:/voice","output_format":"mp3","preview_count":"1",'
                '"cooldown_seconds":"7","normalize_audio":"true","merge_pause":"1.25",'
                '"language":"en"}',
                encoding="utf-8",
            )
            with patch.object(config_store, "DATA_DIR", data_dir):
                with patch.object(config_store, "LEGACY_DIR", Path(directory) / "legacy"):
                    loaded = load_settings()
            self.assertEqual(loaded["zonos2_output_dir"], "X:/voice")
            self.assertEqual(loaded["zonos2_output_format"], "mp3")
            self.assertEqual(loaded["zonos2_preview_count"], "1")
            self.assertEqual(loaded["zonos2_cooldown_seconds"], "7")
            self.assertEqual(loaded["zonos2_normalize_audio"], "true")
            self.assertEqual(loaded["zonos2_merge_pause"], "1.25")
            self.assertEqual(loaded["zonos2_language"], "en_us")


if __name__ == "__main__":
    unittest.main()
