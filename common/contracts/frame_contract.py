# FILE: common/contracts/frame_contract.py
# ------------------------------------------------------------------------------
from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class FrameMemoryRef:
    backend: str
    key: str
    size: int
    generation: int

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "FrameMemoryRef":
        if not isinstance(payload, dict):
            raise ValueError("memory must be a dict")
        backend = payload.get("backend")
        key = payload.get("key")
        size = payload.get("size")
        generation = payload.get("generation")
        if not isinstance(backend, str) or not backend:
            raise ValueError("memory.backend must be a non-empty string")
        if not isinstance(key, str) or not key:
            raise ValueError("memory.key must be a non-empty string")
        if not isinstance(size, int) or size < 0:
            raise ValueError("memory.size must be a non-negative int")
        if not isinstance(generation, int):
            raise ValueError("memory.generation must be an int")
        return cls(
            backend=backend,
            key=key,
            size=size,
            generation=generation,
        )


@dataclass(frozen=True)
class FrameContractV1:
    contract_version: int
    frame_id: str
    stream_id: str
    camera_id: str
    pts: float
    timestamp_ms: int
    mono_ms: int
    memory: FrameMemoryRef
    frame_width: int
    frame_height: int
    frame_channels: int
    frame_dtype: str
    frame_color_space: str

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "FrameContractV1":
        if not isinstance(payload, dict):
            raise ValueError("contract must be a dict")
        contract_version = payload.get("contract_version")
        if isinstance(contract_version, bool):
            contract_version = None
        if isinstance(contract_version, str):
            normalized = contract_version.strip()
            if normalized.lower() == "v1":
                normalized = "1"
            if normalized.isdigit():
                contract_version = int(normalized)
        if contract_version != 1:
            raise ValueError("contract_version must be int 1")
        frame_id = payload.get("frame_id")
        stream_id = payload.get("stream_id")
        camera_id = payload.get("camera_id")
        if not isinstance(frame_id, str) or not frame_id:
            raise ValueError("frame_id must be a non-empty string")
        if not isinstance(stream_id, str) or not stream_id:
            raise ValueError("stream_id must be a non-empty string")
        if not isinstance(camera_id, str) or not camera_id:
            raise ValueError("camera_id must be a non-empty string")
        pts = payload.get("pts")
        if not isinstance(pts, (int, float)):
            raise ValueError("pts must be a number")
        timestamp_ms = payload.get("timestamp_ms")
        mono_ms = payload.get("mono_ms")
        if not isinstance(timestamp_ms, int):
            raise ValueError("timestamp_ms must be an int (ms)")
        if not isinstance(mono_ms, int):
            raise ValueError("mono_ms must be an int (ms)")
        memory = FrameMemoryRef.from_dict(payload.get("memory"))
        frame_width = payload.get("frame_width")
        frame_height = payload.get("frame_height")
        frame_channels = payload.get("frame_channels")
        frame_dtype = payload.get("frame_dtype")
        frame_color_space = payload.get("frame_color_space")
        if not isinstance(frame_width, int) or frame_width <= 0:
            raise ValueError("frame_width must be a positive int")
        if not isinstance(frame_height, int) or frame_height <= 0:
            raise ValueError("frame_height must be a positive int")
        if not isinstance(frame_channels, int) or frame_channels <= 0:
            raise ValueError("frame_channels must be a positive int")
        if not isinstance(frame_dtype, str) or not frame_dtype:
            raise ValueError("frame_dtype must be a non-empty string")
        if not isinstance(frame_color_space, str) or not frame_color_space:
            raise ValueError("frame_color_space must be a non-empty string")
        return cls(
            contract_version=contract_version,
            frame_id=frame_id,
            stream_id=stream_id,
            camera_id=camera_id,
            pts=float(pts),
            timestamp_ms=timestamp_ms,
            mono_ms=mono_ms,
            memory=memory,
            frame_width=frame_width,
            frame_height=frame_height,
            frame_channels=frame_channels,
            frame_dtype=frame_dtype,
            frame_color_space=frame_color_space,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "frame_id": self.frame_id,
            "stream_id": self.stream_id,
            "camera_id": self.camera_id,
            "pts": self.pts,
            "timestamp_ms": self.timestamp_ms,
            "mono_ms": self.mono_ms,
            "memory": {
                "backend": self.memory.backend,
                "key": self.memory.key,
                "size": self.memory.size,
                "generation": self.memory.generation,
            },
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
            "frame_channels": self.frame_channels,
            "frame_dtype": self.frame_dtype,
            "frame_color_space": self.frame_color_space,
        }
