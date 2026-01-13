from ingestion.frame.id import FrameIdentity
from ingestion.ipc import _build_contract


class DummyMemoryRef:
    def __init__(self):
        self.backend_type = "shm"
        self.location = "1"
        self.size = 640 * 480 * 3


def test_ingestion_builds_contract_version_int():
    identity = FrameIdentity("s1", 0.0, "fp")
    contract = _build_contract(
        stream_id="s1",
        camera_id="c1",
        frame_identity=identity,
        packet_timestamp=1000,
        memory_ref=DummyMemoryRef(),
        gen=1,
        frame_width=640,
        frame_height=480,
        frame_color="bgr",
    )
    assert contract["contract_version"] == 1
    assert isinstance(contract["contract_version"], int)
