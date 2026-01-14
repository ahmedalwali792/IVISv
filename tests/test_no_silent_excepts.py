import re
from pathlib import Path


SILENT_EXCEPT_RE = re.compile(r"except Exception:\s*\n\s*pass")


def test_no_silent_exception_pass_in_main_paths():
    root = Path(__file__).resolve().parents[1]
    for rel in ("ingestion", "detection", "ui"):
        base = root / rel
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert not SILENT_EXCEPT_RE.search(text), f"Silent except/pass found in {path}"
