"""Shim module to expose top-level `run_system` as `ivis.run_system`.

This imports the top-level `run_system` module and exposes its `main`
callable so entry points can reference `ivis.run_system:main`.
"""
from importlib import import_module

_mod = import_module("run_system")

def main(argv=None):
    return _mod.main(argv=argv)
