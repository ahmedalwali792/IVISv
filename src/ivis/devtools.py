# FILE: src/ivis/devtools.py
# ------------------------------------------------------------------------------
import subprocess
import sys


def _run(args):
    cmd = [sys.executable] + args
    raise SystemExit(subprocess.call(cmd))


def lint() -> None:
    _run(["-m", "ruff", "check", "."])


def typecheck() -> None:
    _run(["-m", "mypy", "src"])


def test() -> None:
    _run(["-m", "pytest", "-q"])
