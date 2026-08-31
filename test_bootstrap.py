import unittest
from pathlib import Path

import bootstrap


class BootstrapTests(unittest.TestCase):
    def test_required_python_is_312(self):
        self.assertEqual(bootstrap.REQUIRED_PYTHON, (3, 12))
        self.assertEqual(bootstrap.TORCH_VERSION, "2.11.0+cu130")
        self.assertEqual(bootstrap.TORCHVISION_VERSION, "0.26.0+cu130")
        self.assertEqual(bootstrap.CUDA_VARIANT, "cu130")

    def test_launcher_creates_python_312_environment(self):
        launcher = Path("Start VoiceOver.bat").read_text(encoding="utf-8")
        self.assertIn("python=3.12", launcher)
        self.assertNotIn("python=3.11", launcher)
        self.assertIn("import pathlib, urllib, unittest, xml.parsers.expat, pip, setuptools", launcher)
        self.assertIn('remove --override-channels -c conda-forge --prefix "%ENV_PREFIX%" --all -y', launcher)


if __name__ == "__main__":
    unittest.main()
