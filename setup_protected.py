from __future__ import annotations

from setuptools import Extension, setup
from Cython.Build import cythonize


setup(
    name="vivu-protected-modules",
    ext_modules=cythonize(
        [
            Extension("app", ["app_protected.py"]),
            Extension("stable_clean_runner", ["stable_clean_runner.py"]),
        ],
        compiler_directives={"language_level": "3", "binding": False},
    ),
)
