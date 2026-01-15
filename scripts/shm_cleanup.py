#!/usr/bin/env python
"""
Best-effort cleanup utility for IVIS shared memory segments.

Usage:
  python scripts/shm_cleanup.py <shm_name> <shm_meta_name>
"""
import sys
from multiprocessing import shared_memory


def _unlink(name: str) -> bool:
    if not name:
        return False
    shm = None
    try:
        shm = shared_memory.SharedMemory(name=name, create=False)
    except FileNotFoundError:
        return False
    except Exception as exc:
        print(f"[SHM] Failed to attach {name}: {exc}")
        return False
    try:
        shm.unlink()
        print(f"[SHM] Unlinked {name}")
        return True
    except FileNotFoundError:
        return False
    except Exception as exc:
        print(f"[SHM] Failed to unlink {name}: {exc}")
        return False
    finally:
        try:
            shm.close()
        except Exception:
            pass


def main(argv):
    if len(argv) < 3:
        print("Usage: python scripts/shm_cleanup.py <shm_name> <shm_meta_name>")
        return 2
    data_name = argv[1]
    meta_name = argv[2]
    _unlink(data_name)
    _unlink(meta_name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
