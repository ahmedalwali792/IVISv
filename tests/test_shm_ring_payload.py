# FILE: tests/test_shm_ring_payload.py
# ------------------------------------------------------------------------------
import uuid

from memory.shm_ring import ShmRing


def test_shm_ring_payload_length_roundtrip():
    name = f"ivis_test_shm_{uuid.uuid4().hex[:8]}"
    meta = f"{name}_meta"
    ring = ShmRing(name, meta, slot_size=16, slot_count=2, create=True, recreate_on_mismatch=True)
    try:
        payload = b"hello"
        slot, gen = ring.write(payload)
        data = ring.read(slot, gen)
        assert data == payload
        latest, idx, gen_latest = ring.read_latest()
        assert idx == slot
        assert gen_latest == gen
        assert latest == payload
    finally:
        ring.close_unlink(True)
