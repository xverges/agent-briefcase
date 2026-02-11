from setuptools import setup

setup(
    name="agent-briefcase",
    version="0.1.0",
    py_modules=["briefcase_sync"],
    entry_points={"console_scripts": ["briefcase-sync=briefcase_sync:main"]},
    python_requires=">=3.8",
)
