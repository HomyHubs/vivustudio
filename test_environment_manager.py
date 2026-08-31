import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from environment_manager import choose_cuda_variant, environment_path, local_cache_environment


class EnvironmentManagerTests(unittest.TestCase):
    def test_gpu_series_selects_matching_cuda_runtime(self):
        self.assertEqual(choose_cuda_variant(""), "cpu")
        self.assertEqual(choose_cuda_variant("Intel UHD Graphics"), "cpu")
        self.assertEqual(choose_cuda_variant("NVIDIA GeForce RTX 3060"), "cu128")
        self.assertEqual(choose_cuda_variant("NVIDIA GeForce RTX 4090"), "cu128")
        self.assertEqual(choose_cuda_variant("NVIDIA GeForce RTX 5060 Ti"), "cu130")

    def test_legacy_environment_is_only_reused_for_cuda_130(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / ".conda-env"
            legacy.mkdir()
            (legacy / "python.exe").touch()
            self.assertEqual(environment_path(root, "cu130"), legacy)
            self.assertEqual(environment_path(root, "cu128"), root / ".conda-env-cu128")
            self.assertEqual(environment_path(root, "cpu"), root / ".conda-env-cpu")

    def test_cache_environment_stays_inside_app_folder(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            values = local_cache_environment(root, {})
            self.assertNotIn("HF_HOME", values)
            self.assertEqual(values["PIP_CACHE_DIR"], str(root / "cache" / "pip"))
            self.assertEqual(values["TORCH_HOME"], str(root / "cache" / "torch"))
            self.assertEqual(values["HF_HUB_DISABLE_XET"], "1")


if __name__ == "__main__":
    unittest.main()
