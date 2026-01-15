"""Top-level ivis package (shims to existing project layout).

This package exposes the existing top-level packages under the
`ivis.` namespace so the project can be installed with a `src/` layout
without requiring extensive file moves. Each subpackage `ivis.<name>` is
implemented as a thin shim that delegates to the existing top-level package
with the same name by forwarding the import path.
"""

__all__ = ["ingestion", "detection", "ui", "common", "memory", "infrastructure"]
