import os, pathlib, fnmatch, sys

ROOT = pathlib.Path(".").resolve()
OUT = ROOT / "project_snapshot_after_p12.txt"

INCLUDE_EXT = {
    ".py",".toml",".md",".yml",".yaml",".ini",".cfg",".json",".env",".sh",".txt",".sql"
}
INCLUDE_FILES = {
    "pyproject.toml","requirements.txt","requirements-dev.txt","README.md",
    "docker-compose.yml","Dockerfile",".gitignore"
}
EXCLUDE_DIRS = {
    ".git","__pycache__",".pytest_cache",".mypy_cache",".ruff_cache",
    ".venv","venv","env","dist","build",".idea",".vscode","logs"
}
EXCLUDE_GLOBS = [
    "*.pyc","*.pyo","*.pyd","*.so","*.dll","*.dylib","*.png","*.jpg","*.jpeg",
    "*.mp4","*.avi","*.mov","*.mkv","*.onnx","*.pt","*.pth","*.weights",
    "*.db","*.sqlite","*.bin"
]

def should_exclude(path: pathlib.Path) -> bool:
    rel = path.relative_to(ROOT)
    parts = rel.parts
    if any(p in EXCLUDE_DIRS for p in parts):
        return True
    name = path.name
    for g in EXCLUDE_GLOBS:
        if fnmatch.fnmatch(name, g):
            return True
    return False

def is_included_file(path: pathlib.Path) -> bool:
    if path.name in INCLUDE_FILES:
        return True
    if path.suffix.lower() in INCLUDE_EXT:
        return True
    return False

# Gather files
files = []
for p in ROOT.rglob("*"):
    if p.is_dir():
        continue
    if should_exclude(p):
        continue
    if is_included_file(p):
        files.append(p)

files = sorted(files, key=lambda x: str(x.relative_to(ROOT)))

# Write snapshot
with OUT.open("w", encoding="utf-8") as f:
    f.write("### PROJECT SNAPSHOT (after P12)\n")
    f.write(f"ROOT: {ROOT}\n")
    f.write(f"FILES: {len(files)}\n\n")

    # Tree-ish listing
    f.write("### FILE LIST\n")
    for p in files:
        f.write(str(p.relative_to(ROOT)) + "\n")
    f.write("\n")

    # File contents
    f.write("### FILE CONTENTS\n\n")
    for p in files:
        rel = p.relative_to(ROOT)
        f.write("="*120 + "\n")
        f.write(f"FILE: {rel}\n")
        f.write("="*120 + "\n")
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # fallback
            text = p.read_text(encoding="utf-8", errors="replace")
        f.write(text)
        if not text.endswith("\n"):
            f.write("\n")
        f.write("\n")

print(f"✅ Wrote snapshot to: {OUT}")

# import os
# import sys
# from pathlib import Path

# def is_binary_file(path, chunk_size=8192):
#     try:
#         with open(path, 'rb') as f:
#             chunk = f.read(chunk_size)
#         if b'\x00' in chunk:
#             return True
#         # Heuristic: try decode as utf-8, fallback to latin-1 for detection
#         try:
#             chunk.decode('utf-8')
#             return False
#         except UnicodeDecodeError:
#             return False
#     except OSError:
#         return True

# def iter_files(root):
#     for dirpath, dirnames, filenames in os.walk(root):
#         # Skip common non-code folders.
#         dirnames[:] = [d for d in dirnames if d not in {'.git', 'logs'}]
#         for name in sorted(filenames):
#             yield Path(dirpath) / name

# def write_tree(root, out):
#     root = Path(root).resolve()
#     out.write(f"PROJECT ROOT: {root}\n")
#     out.write("\nTREE:\n")
#     for path in sorted(iter_files(root)):
#         rel = path.relative_to(root)
#         out.write(str(rel).replace('\\', '/') + "\n")
#     out.write("\n")

# def write_contents(root, out):
#     root = Path(root).resolve()
#     out.write("FILES:\n")
#     for path in sorted(iter_files(root)):
#         rel = path.relative_to(root)
#         out.write("=" * 80 + "\n")
#         out.write(f"FILE: {str(rel).replace('\\', '/')}\n")
#         out.write("=" * 80 + "\n")
#         try:
#             if is_binary_file(path):
#                 out.write("[SKIPPED: binary or unreadable]\n\n")
#                 continue
#             text = path.read_text(encoding='utf-8')
#         except UnicodeDecodeError:
#             text = path.read_text(encoding='latin-1')
#         except Exception as e:
#             out.write(f"[SKIPPED: {e}]\n\n")
#             continue
#         out.write(text)
#         if not text.endswith("\n"):
#             out.write("\n")
#         out.write("\n")

# def main():
#     root = Path(__file__).resolve().parent
#     output = root / 'project_snapshot.txt'
#     with output.open('w', encoding='utf-8', newline='\n') as out:
#         write_tree(root, out)
#         write_contents(root, out)
#     print(f"Wrote snapshot to {output}")

# if __name__ == '__main__':
#     main()
