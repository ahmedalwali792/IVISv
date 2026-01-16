from detection.config import Config
from detection.errors.fatal import NonFatalError
from memory.shm_ring import ShmRing

class MemoryReader:
    """
    Stage 3: Reads Raw Bytes Only.
    No decoding, no reshaping here. Just bytes.
    """
    def __init__(self, host="localhost", port=6000):
        self._ring = None
        self._ring_info = {}

    def ensure_ring(self):
        if self._ring is not None:
            return True, dict(self._ring_info), None

        if Config.MEMORY_BACKEND != "shm":
            return False, {}, f"Unsupported memory backend: {Config.MEMORY_BACKEND}"

        slot_size = Config.FRAME_WIDTH * Config.FRAME_HEIGHT * 3
        if Config.SHM_CACHE_SECONDS > 0 and Config.SHM_CACHE_FPS > 0:
            slot_count = max(1, int(Config.SHM_CACHE_SECONDS * Config.SHM_CACHE_FPS))
        else:
            slot_count = max(1, Config.SHM_BUFFER_BYTES // slot_size)

        try:
            self._ring = ShmRing(
                Config.SHM_NAME,
                Config.SHM_META_NAME,
                slot_size,
                slot_count,
                create=False,
            )
            self._ring_info = {
                "shm_name": Config.SHM_NAME,
                "shm_meta_name": Config.SHM_META_NAME,
                "slot_size": slot_size,
                "slot_count": slot_count,
            }
            return True, dict(self._ring_info), None
        except FileNotFoundError:
            self._ring = None
            return False, {
                "shm_name": Config.SHM_NAME,
                "shm_meta_name": Config.SHM_META_NAME,
                "slot_size": slot_size,
                "slot_count": slot_count,
            }, "Shared memory not available yet"
        except Exception as exc:
            self._ring = None
            return False, {}, str(exc)

    def close(self):
        if self._ring is None:
            return
        try:
            self._ring.close()
        except Exception:
            pass
        self._ring = None
        self._ring_info = {}

    def read(self, memory_ref: dict) -> bytes:
        key = memory_ref.get("key")
        if not key:
            raise NonFatalError("Invalid memory reference: missing key")

        if memory_ref.get("backend", "").startswith("shm"):
            ok, _, err = self.ensure_ring()
            if not ok:
                raise NonFatalError(err or "Shared memory not ready")

            try:
                slot = int(key)
            except ValueError:
                raise NonFatalError("Invalid shared memory key")

            gen = memory_ref.get("generation", 0)
            data = self._ring.read(slot, gen)
            if data is None:
                raise NonFatalError("Shared memory miss (evicted or overwritten)")
            if len(data) == 0:
                raise NonFatalError("Empty data received from shared memory")
            return data

        raise NonFatalError("Unsupported memory backend")
