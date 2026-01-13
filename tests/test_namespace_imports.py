import re
from pathlib import Path


IMPORT_RE = re.compile(r"^\s*(from|import)\s+common\b")


def _is_excluded(path: Path) -> bool:
    normalized = str(path).replace("\\", "/")
    if "/ivis/common/" in normalized:
        return True
    if "/src/ivis/common/" in normalized:
        return True
    return False


def test_no_common_imports_in_official_paths():
    root = Path(__file__).resolve().parents[1]
    search_dirs = [
        "src",
        "ingestion",
        "detection",
        "ui",
        "memory",
        "infrastructure",
        "ivis",
    ]
    violations = []
    for rel in search_dirs:
        base = root / rel
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if _is_excluded(path):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for lineno, line in enumerate(text.splitlines(), 1):
                if IMPORT_RE.search(line):
                    violations.append(f"{path}:{lineno}: {line.strip()}")
                    break
    assert not violations, "common.* imports detected:\n" + "\n".join(violations)
