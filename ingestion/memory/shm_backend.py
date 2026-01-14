# FILE: ingestion/memory/shm_backend.py
# ------------------------------------------------------------------------------
import atexit
import os
import sys

from ingestion.memory.ref import MemoryReference
from memory.shm_ring import ShmRing


class ShmRingBackend:
    name = "shm_ring_v1"

    def __init__(self, shm_name: str, meta_name: str, slot_size: int, slot_count: int):
        self._owner = os.getenv("SHM_OWNER", "1").lower() in ("1", "true", "yes")
        self.ring = ShmRing(
            shm_name,
            meta_name,
            slot_size,
            slot_count,
            create=True,
            recreate_on_mismatch=True,
        )
        atexit.register(self.close)

    def put(self, key, data):
        slot, gen = self.ring.write(data)
        import logging
        logging.getLogger("ingestion").debug("Wrote to SHM: key=%s slot=%s gen=%s bytes=%s", key, slot, gen, len(data))
        return MemoryReference(
            location=str(slot),
            size=len(data),
            backend_type=self.name,
            generation=gen,
        )

    def put_frame(self, key, frame_data):
        slot, gen = self.ring.write(frame_data)
        import logging
        logging.getLogger("ingestion").debug(
            "Wrote frame to SHM: key=%s slot=%s gen=%s bytes=%s", key, slot, gen, frame_data.nbytes
        )
        return MemoryReference(
            location=str(slot),
            size=frame_data.nbytes,
            backend_type=self.name,
            generation=gen,
        )

    def close(self):
        try:
            self.ring.close_unlink(unlink=self._owner)
        except Exception as exc:
            import logging
            logging.getLogger("ingestion").warning("Failed to close SHM ring: %s", exc)
