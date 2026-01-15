import importlib

# Delegate package imports to the existing top-level `detection` package.
_pkg = importlib.import_module("detection")
__path__ = getattr(_pkg, "__path__", [])
__all__ = getattr(_pkg, "__all__", [])
