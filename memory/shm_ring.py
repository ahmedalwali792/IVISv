# FILE: memory/shm_ring.py
# ------------------------------------------------------------------------------
import os
import struct
import time
import atexit
import tempfile
from typing import Optional
from multiprocessing import shared_memory
import logging

try:
    from memory.errors.fatal import BackendInitializationError
except Exception:
    class BackendInitializationError(Exception):
        pass


MAGIC = b"IVIS"
VERSION = 1
HEADER_FMT = "<4sIIII"
HEADER_SIZE = struct.calcsize(HEADER_FMT)
PAYLOAD_LEN_FMT = "<I"
PAYLOAD_LEN_SIZE = struct.calcsize(PAYLOAD_LEN_FMT)


class _Mutex:
    """Cross-platform mutex.

    On Windows uses a named mutex via ctypes. On POSIX platforms uses a file lock
    in the system temp directory (via fcntl.flock). The file-based lock keeps a
    file descriptor open for the lifetime of the mutex object.
    """

    def __init__(self, name: str):
        self.name = name
        self._handle = None
        self._is_windows = os.name == "nt"
        if self._is_windows:
            import ctypes

            self._ctypes = ctypes
            # Create a named mutex (NULL security, not owned initially)
            self._handle = self._ctypes.windll.kernel32.CreateMutexW(None, False, name)
        else:
            # POSIX: use a lock file in the temp directory
            self._lock_dir = tempfile.gettempdir()
            self._lock_path = os.path.join(self._lock_dir, f"{name}.lock")
            # open file in append+binary so it is shareable and persists
            # keep the file descriptor as the handle for fcntl locks
            self._handle = open(self._lock_path, "a+b")

    def __enter__(self):
        if self._is_windows and self._handle:
            # WAIT_INFINITE = 0xFFFFFFFF
            self._ctypes.windll.kernel32.WaitForSingleObject(self._handle, 0xFFFFFFFF)
        elif self._handle:
            # local import to avoid failing on Windows where fcntl is absent
            import fcntl

            fcntl.flock(self._handle, fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._is_windows and self._handle:
            self._ctypes.windll.kernel32.ReleaseMutex(self._handle)
        elif self._handle:
            import fcntl

            try:
                fcntl.flock(self._handle, fcntl.LOCK_UN)
            except Exception:
                # best-effort unlock
                pass

    def __del__(self):
        try:
            if not self._is_windows and self._handle:
                try:
                    self._handle.close()
                except Exception:
                    pass
        except Exception:
            pass


logger = logging.getLogger("ivis.shm_ring")


class ShmRing:
    def __init__(
        self,
        data_name: str,
        meta_name: str,
        slot_size: int,
        slot_count: int,
        create: bool = False,
        recreate_on_mismatch: bool = True,
    ):
        self.data_name = data_name
        self.meta_name = meta_name
        self.slot_size = slot_size
        self.slot_count = slot_count
        self._mutex = _Mutex(f"{data_name}_mutex")
        self._owner = create
        self._payload_offset = HEADER_SIZE + (slot_count * 4)
        self._has_payload_lengths = False

        meta_size = HEADER_SIZE + (slot_count * 4) + (slot_count * PAYLOAD_LEN_SIZE)
        if create:
            try:
                self.data = shared_memory.SharedMemory(name=data_name, create=True, size=slot_size * slot_count)
                self.meta = shared_memory.SharedMemory(name=meta_name, create=True, size=meta_size)
                self._has_payload_lengths = self.meta.size >= (self._payload_offset + (slot_count * PAYLOAD_LEN_SIZE))
                self._init_meta()
            except FileExistsError:
                self._warn_existing()
                self.data = shared_memory.SharedMemory(name=data_name, create=False)
                self.meta = shared_memory.SharedMemory(name=meta_name, create=False)
                self._has_payload_lengths = self.meta.size >= (self._payload_offset + (slot_count * PAYLOAD_LEN_SIZE))
                try:
                    self._validate_meta()
                except BackendInitializationError:
                    if not recreate_on_mismatch:
                        raise
                    self._warn_recreate()
                    self._cleanup()
                    self.data = shared_memory.SharedMemory(name=data_name, create=True, size=slot_size * slot_count)
                    self.meta = shared_memory.SharedMemory(name=meta_name, create=True, size=meta_size)
                    self._has_payload_lengths = self.meta.size >= (self._payload_offset + (slot_count * PAYLOAD_LEN_SIZE))
                    self._init_meta()
        else:
            self.data = shared_memory.SharedMemory(name=data_name, create=False)
            self.meta = shared_memory.SharedMemory(name=meta_name, create=False)
            self._has_payload_lengths = self.meta.size >= (self._payload_offset + (slot_count * PAYLOAD_LEN_SIZE))
            self._validate_meta()

        self.data_buf = self.data.buf
        self.meta_buf = self.meta.buf

        # If this process created the segments, try to unlink them on clean exit
        if self._owner:
            try:
                atexit.register(self.close_unlink, True)
            except Exception:
                logger.warning("Failed to register atexit handler for shm cleanup")

    def _init_meta(self):
        struct.pack_into(
            HEADER_FMT,
            self.meta.buf,
            0,
            MAGIC,
            VERSION,
            self.slot_size,
            self.slot_count,
            0,
        )
        for i in range(self.slot_count):
            struct.pack_into("<I", self.meta.buf, HEADER_SIZE + (i * 4), 0)
        if self._has_payload_lengths:
            for i in range(self.slot_count):
                struct.pack_into(PAYLOAD_LEN_FMT, self.meta.buf, self._payload_offset + (i * PAYLOAD_LEN_SIZE), 0)

    def _validate_meta(self):
        magic, version, slot_size, slot_count, _ = struct.unpack_from(HEADER_FMT, self.meta.buf, 0)
        if magic != MAGIC or version != VERSION:
            raise BackendInitializationError("Shared memory header mismatch")
        if slot_size != self.slot_size or slot_count != self.slot_count:
            raise BackendInitializationError("Shared memory layout mismatch")

    def _get_write_index(self) -> int:
        _, _, _, _, idx = struct.unpack_from(HEADER_FMT, self.meta_buf, 0)
        return idx

    def _set_write_index(self, idx: int) -> None:
        magic, version, slot_size, slot_count, _ = struct.unpack_from(HEADER_FMT, self.meta_buf, 0)
        struct.pack_into(HEADER_FMT, self.meta_buf, 0, magic, version, slot_size, slot_count, idx)

    def _get_generation(self, slot: int) -> int:
        return struct.unpack_from("<I", self.meta_buf, HEADER_SIZE + (slot * 4))[0]

    def _set_generation(self, slot: int, gen: int) -> None:
        struct.pack_into("<I", self.meta_buf, HEADER_SIZE + (slot * 4), gen)

    def _get_payload_length(self, slot: int) -> int:
        if not self._has_payload_lengths:
            return self.slot_size
        return struct.unpack_from(PAYLOAD_LEN_FMT, self.meta_buf, self._payload_offset + (slot * PAYLOAD_LEN_SIZE))[0]

    def _set_payload_length(self, slot: int, length: int) -> None:
        if not self._has_payload_lengths:
            return
        struct.pack_into(PAYLOAD_LEN_FMT, self.meta_buf, self._payload_offset + (slot * PAYLOAD_LEN_SIZE), length)

    def _record_bytes(self, count: int) -> None:
        try:
            import ivis_metrics
            ivis_metrics.shm_bytes_copied_total.inc(int(count))
        except Exception:
            pass

    def _record_latency(self, metric_name: str, value_ms: float) -> None:
        try:
            import ivis_metrics
            metric = getattr(ivis_metrics, metric_name, None)
            if metric is not None:
                metric.observe(float(value_ms))
        except Exception:
            pass

    def write(self, data):
        start_ts = time.perf_counter()
        view = memoryview(data)
        if view.ndim != 1:
            view = view.cast("B")
        payload_len = view.nbytes
        if payload_len > self.slot_size:
            raise ValueError(f"Invalid frame size: {payload_len} (expected <= {self.slot_size})")
        if not self._has_payload_lengths and payload_len != self.slot_size:
            raise ValueError(f"Invalid frame size: {payload_len} (expected {self.slot_size})")
        with self._mutex:
            slot = self._get_write_index() % self.slot_count
            gen = (self._get_generation(slot) + 1) & 0xFFFFFFFF
            start = slot * self.slot_size
            end = start + payload_len
            self.data_buf[start:end] = view
            self._set_generation(slot, gen)
            self._set_payload_length(slot, payload_len)
            self._set_write_index(slot + 1)
        self._record_bytes(payload_len)
        self._record_latency("shm_write_latency_ms", (time.perf_counter() - start_ts) * 1000.0)
        logger.debug("SHM write: data_name=%s slot=%s gen=%s bytes=%s", self.data_name, slot, gen, payload_len)
        return slot, gen

    def read(self, slot: int, gen: int):
        start_ts = time.perf_counter()
        if slot < 0 or slot >= self.slot_count:
            return None
        with self._mutex:
            current = self._get_generation(slot)
            if current != gen:
                logger.debug(
                    "SHM read mismatch: data_name=%s slot=%s expected_gen=%s current_gen=%s",
                    self.data_name,
                    slot,
                    gen,
                    current,
                )
                return None
            start = slot * self.slot_size
            payload_len = self._get_payload_length(slot)
            if payload_len <= 0 or payload_len > self.slot_size:
                payload_len = self.slot_size
            end = start + payload_len
            data = bytes(self.data_buf[start:end])
            logger.debug("SHM read: data_name=%s slot=%s gen=%s bytes=%s", self.data_name, slot, gen, len(data))
            self._record_bytes(payload_len)
            self._record_latency("shm_read_latency_ms", (time.perf_counter() - start_ts) * 1000.0)
            return data

    def read_latest(self):
        start_ts = time.perf_counter()
        with self._mutex:
            idx = (self._get_write_index() - 1) % self.slot_count
            gen = self._get_generation(idx)
            start = idx * self.slot_size
            payload_len = self._get_payload_length(idx)
            if payload_len <= 0 or payload_len > self.slot_size:
                payload_len = self.slot_size
            end = start + payload_len
            data = bytes(self.data_buf[start:end])
            logger.debug("SHM read_latest: data_name=%s slot=%s gen=%s bytes=%s", self.data_name, idx, gen, len(data))
            self._record_bytes(payload_len)
            self._record_latency("shm_read_latency_ms", (time.perf_counter() - start_ts) * 1000.0)
            return data, idx, gen

    def close(self):
        self.close_unlink(unlink=False)

    def close_unlink(self, unlink: bool = False):
        try:
            self.data.close()
        except Exception:
            pass
        try:
            self.meta.close()
        except Exception:
            pass
        if unlink:
            try:
                self.data.unlink()
            except Exception:
                pass
            try:
                self.meta.unlink()
            except Exception:
                pass

    @staticmethod
    def exists(data_name: str, meta_name: str) -> bool:
        data = None
        meta = None
        try:
            data = shared_memory.SharedMemory(name=data_name, create=False)
            meta = shared_memory.SharedMemory(name=meta_name, create=False)
            return True
        except FileNotFoundError:
            return False
        finally:
            if data is not None:
                try:
                    data.close()
                except Exception:
                    pass
            if meta is not None:
                try:
                    meta.close()
                except Exception:
                    pass

    def _warn_existing(self) -> None:
        logger.warning("Existing shared memory detected: %s, %s", self.data_name, self.meta_name)

    def _warn_recreate(self) -> None:
        logger.warning(
            "Recreating shared memory due to mismatch: %s, %s", self.data_name, self.meta_name
        )

    def _cleanup(self):
        try:
            self.data.close()
        except Exception:
            pass
        try:
            self.meta.close()
        except Exception:
            pass
        try:
            self.data.unlink()
        except Exception:
            pass
        try:
            self.meta.unlink()
        except Exception:
            pass
