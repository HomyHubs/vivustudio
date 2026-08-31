from setuptools import Extension, setup
from Cython.Build import cythonize

setup(
    name="remove-logo-protected",
    ext_modules=cythonize(
        [Extension("remove_logo_tool", ["remove_logo_tool.py"])],
        compiler_directives={"language_level": "3", "binding": False},
    ),
)
