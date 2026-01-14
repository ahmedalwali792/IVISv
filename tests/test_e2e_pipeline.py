# FILE: tests/test_e2e_pipeline.py
# ------------------------------------------------------------------------------
from detection.postprocess.parse import parse_output
from ingestion.frame.id import FrameIdentity
from ingestion.ipc import _build_contract
from ingestion.memory.ref import MemoryReference
from ivis.common.contracts.result_contract import validate_result_contract_v1
from ivis.common.contracts.validators import validate_frame_contract_v1


def _make_frame_contract(index: int) -> dict:
    stream_id = "stream-1"
    camera_id = "cam-1"
    width = 32
    height = 32
    channels = 3
    size = width * height * channels
    identity = FrameIdentity(stream_id, 0.1 * index, f"fp-{index}")
    memory = MemoryReference("memkey", size, "shm_ring_v1", generation=index)
    return _build_contract(
        stream_id,
        camera_id,
        identity,
        1000 + index,
        2000 + index,
        memory,
        memory.generation,
        width,
        height,
        "bgr",
    )


def _make_raw_results() -> dict:
    return {
        "detections": [([1.0, 2.0, 10.0, 20.0], 0.9, 1)],
        "tracks": [{"bbox_xyxy": [1.0, 2.0, 10.0, 20.0], "track_id": 42}],
        "timing": {"inference_ms": 1.2},
    }


def _attach_model(result: dict) -> None:
    result["model"] = {
        "name": "stub-model",
        "version": "0",
        "threshold": 0.5,
        "input_size": [32, 32],
    }


def test_e2e_pipeline_contracts() -> None:
    contracts = [_make_frame_contract(i) for i in range(3)]

    for contract in contracts:
        validate_frame_contract_v1(contract)
        result = parse_output(contract, _make_raw_results())
        _attach_model(result)
        validate_result_contract_v1(result)
        assert result["contract_version"] == 1
        assert result["frame_id"] == contract["frame_id"]
